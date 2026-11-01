#!/usr/bin/env python3
"""
Label outcomes for stored scan results — WP1 of the Accuracy Roadmap.

Runs locally against Aiven PostgreSQL. Never runs on Render.

Reads DATABASE_URL from the environment. Never reads or writes .env.

Usage:
    python scripts/label_outcomes.py --dry-run --limit 100
    python scripts/label_outcomes.py --limit 500
    python scripts/label_outcomes.py              # label all eligible signals

Flags:
    --dry-run     Print label distribution and count, write nothing to DB
    --limit N     Process at most N signals (after dedup)
    --notional N  Notional position size for charge calculation (default 25000)
"""

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from sqlalchemy import desc, func

sys.path.insert(0, '.')
from models.database import get_session, SignalLabel, Base
from models.scan_report import ScanResult, ScanReport
from utils.helpers import calculate_net_pnl

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MIN_SCORE = 50
MAX_HOLD_DAYS = 15
CHUNK_SIZE = 10
BATCH_SIZE = 200
DEFAULT_NOTIONAL = 25000


def _ns_symbol(symbol: str) -> str:
    """Ensure .NS suffix for yfinance."""
    return symbol if symbol.endswith('.NS') else f'{symbol}.NS'


def get_eligible_signals(session, limit: Optional[int] = None):
    """
    Query scan results eligible for labeling:
    - total_score >= MIN_SCORE
    - entry_price, stop_loss, target all present
    - Not already labeled (no SignalLabel row for this scan_result_id)
    - Dedup: highest-score per symbol per calendar day
    """
    # Fetch all eligible results ordered by symbol, date, score desc
    query = (
        session.query(ScanResult, ScanReport.timestamp)
        .join(ScanReport, ScanResult.scan_report_id == ScanReport.id)
        .filter(ScanResult.total_score >= MIN_SCORE)
        .filter(ScanResult.entry_price.isnot(None))
        .filter(ScanResult.stop_loss.isnot(None))
        .filter(ScanResult.target.isnot(None))
        .outerjoin(SignalLabel, SignalLabel.scan_result_id == ScanResult.id)
        .filter(SignalLabel.id.is_(None))
        .order_by(ScanResult.symbol, ScanReport.timestamp, desc(ScanResult.total_score))
    )

    # Fetch extra to allow for dedup if limit is set
    fetch_limit = (limit * 10) if limit else None
    if fetch_limit:
        query = query.limit(fetch_limit)

    results = query.all()

    # Dedup: highest score per symbol per calendar day (first row wins due to sort)
    seen = set()
    deduped = []
    for sr, ts in results:
        signal_day = ts.date() if hasattr(ts, 'date') else ts
        key = (sr.symbol, signal_day)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((sr, ts))

    if limit:
        deduped = deduped[:limit]

    return deduped


def apply_labeling_rules(
    symbol: str,
    entry_price: float,
    stop_price: float,
    target1_price: float,
    signal_date: date,
    df: pd.DataFrame,
    notional: float,
) -> Optional[dict]:
    """
    Pure labeling logic (Appendix C). Takes OHLCV bars as a DataFrame and
    returns a SignalLabel-compatible dict, or None if data is unusable.

    Rules:
    1. Gap down through stop at open → exit at open (STOP)
    2. Both stop and target touched same day → STOP (conservative)
    3. Only stop touched → exit at stop (STOP)
    4. Only target touched → exit at target (TARGET)
    5. Timeout after MAX_HOLD_DAYS → exit at close (TIMEOUT)
    """
    entry_price = float(entry_price)
    stop_price = float(stop_price)
    target1_price = float(target1_price)

    risk_per_share = entry_price - stop_price
    if risk_per_share <= 0:
        return None

    if df is None or df.empty or len(df) < 1:
        return None

    required = {'Open', 'High', 'Low', 'Close'}
    if not required.issubset(set(df.columns)):
        return None

    # Initialize tracking
    exit_price = None
    exit_date = None
    outcome = 'NO_DATA'
    days_held = 0
    path = []
    mfe_r = 0.0
    mae_r = 0.0

    trading_days = 0
    for idx, row in df.iterrows():
        trading_days += 1
        if trading_days > MAX_HOLD_DAYS:
            break

        open_price = float(row['Open'])
        high_price = float(row['High'])
        low_price = float(row['Low'])
        close_price = float(row['Close'])

        # Track path in R units (relative to entry)
        high_r = (high_price - entry_price) / risk_per_share
        low_r = (low_price - entry_price) / risk_per_share
        close_r = (close_price - entry_price) / risk_per_share
        path.append([round(high_r, 4), round(low_r, 4), round(close_r, 4)])

        # Update MFE/MAE
        mfe_r = max(mfe_r, high_r)
        mae_r = min(mae_r, low_r)

        # Rule 1: gap down through stop at open → exit at open (STOP)
        if open_price <= stop_price:
            exit_price = open_price
            exit_date = idx
            outcome = 'STOP'
            days_held = trading_days
            break

        # Rule 2: both stop and target touched same day → stop wins (conservative)
        stop_touched = low_price <= stop_price
        target_touched = high_price >= target1_price

        if stop_touched and target_touched:
            exit_price = stop_price
            exit_date = idx
            outcome = 'STOP'
            days_held = trading_days
            break

        # Rule 3: only stop touched → exit at stop (STOP)
        if stop_touched:
            exit_price = stop_price
            exit_date = idx
            outcome = 'STOP'
            days_held = trading_days
            break

        # Rule 4: only target touched → exit at target (TARGET)
        if target_touched:
            # If gapped above target, exit at open; else at target
            exit_price = target1_price if open_price < target1_price else open_price
            exit_date = idx
            outcome = 'TARGET'
            days_held = trading_days
            break

    # Rule 5: timeout after MAX_HOLD_DAYS trading days → exit at close (TIMEOUT)
    if exit_price is None:
        last_idx = min(trading_days - 1, len(df) - 1)
        exit_price = float(df['Close'].iloc[last_idx])
        exit_date = df.index[last_idx]
        outcome = 'TIMEOUT'
        days_held = trading_days

    # Calculate R metrics
    r_gross = round((exit_price - entry_price) / risk_per_share, 4)

    # r_net: net P&L after charges divided by total risk rupees
    quantity = max(1, int(notional / entry_price))
    net_pnl, charges = calculate_net_pnl(
        entry_price, exit_price, quantity,
        partially_exited=False,
    )
    total_risk_rupees = risk_per_share * quantity
    r_net = round(net_pnl / total_risk_rupees, 4) if total_risk_rupees > 0 else 0.0

    return {
        'symbol': symbol,
        'entry_price': entry_price,
        'stop_price': stop_price,
        'target1_price': target1_price,
        'outcome': outcome,
        'days_to_outcome': days_held,
        'r_gross': r_gross,
        'r_net': r_net,
        'mfe_r': round(mfe_r, 4),
        'mae_r': round(mae_r, 4),
        'path_json': json.dumps(path) if path else None,
        'exit_price': exit_price,
        'exit_date': exit_date,
    }


def label_signal(scan_result, signal_timestamp, notional: float) -> Optional[dict]:
    """
    Apply labeling rules (Appendix C) to a single scan result.

    Fetches daily bars via yfinance, then delegates to apply_labeling_rules.
    Returns a dict with all SignalLabel fields, or None if data is unavailable.
    """
    symbol = scan_result.symbol
    entry_price = float(scan_result.entry_price)
    stop_price = float(scan_result.stop_loss)
    target1_price = float(scan_result.target)
    signal_date = signal_timestamp.date() if hasattr(signal_timestamp, 'date') else signal_timestamp

    # Fetch daily bars starting from the day after signal date
    start_date = signal_date + timedelta(days=1)
    end_date = start_date + timedelta(days=45)  # ~15 trading days + weekends buffer

    try:
        df = yf.download(
            _ns_symbol(symbol),
            start=start_date,
            end=end_date,
            progress=False,
            auto_adjust=True,
        )
    except Exception as e:
        logger.warning(f"yfinance download failed for {symbol}: {e}")
        return None

    label_data = apply_labeling_rules(
        symbol=symbol,
        entry_price=entry_price,
        stop_price=stop_price,
        target1_price=target1_price,
        signal_date=signal_date,
        df=df,
        notional=notional,
    )
    if label_data is None:
        return None

    return {
        'scan_result_id': scan_result.id,
        'symbol': label_data['symbol'],
        'signal_date': signal_date,
        'entry_price': label_data['entry_price'],
        'stop_price': label_data['stop_price'],
        'target1_price': label_data['target1_price'],
        'outcome': label_data['outcome'],
        'days_to_outcome': label_data['days_to_outcome'],
        'r_gross': label_data['r_gross'],
        'r_net': label_data['r_net'],
        'mfe_r': label_data['mfe_r'],
        'mae_r': label_data['mae_r'],
        'path_json': label_data['path_json'],
    }


def main():
    parser = argparse.ArgumentParser(description='Label scan result outcomes (WP1)')
    parser.add_argument('--dry-run', action='store_true', help='Print stats, write nothing')
    parser.add_argument('--limit', type=int, default=None, help='Max signals to process')
    parser.add_argument('--notional', type=float, default=DEFAULT_NOTIONAL, help='Notional position size (default 25000)')
    args = parser.parse_args()

    with get_session() as session:
        signals = get_eligible_signals(session, limit=args.limit)
        logger.info(f"Found {len(signals)} eligible signals for labeling")

        if args.dry_run:
            logger.info(f"DRY RUN: Would label {len(signals)} signals (not writing to DB)")
            return

        labeled = 0
        failed = 0
        batch = []
        outcome_counts = {'TARGET': 0, 'STOP': 0, 'TIMEOUT': 0, 'NO_DATA': 0}

        for scan_result, signal_timestamp in signals:
            try:
                label_data = label_signal(scan_result, signal_timestamp, args.notional)
                if label_data is None:
                    failed += 1
                    continue

                batch.append(SignalLabel(**label_data))
                labeled += 1
                outcome_counts[label_data['outcome']] = outcome_counts.get(label_data['outcome'], 0) + 1

                if len(batch) >= BATCH_SIZE:
                    session.add_all(batch)
                    session.commit()
                    logger.info(f"Committed batch of {len(batch)} labels (cumulative: {labeled})")
                    batch = []

            except Exception as e:
                logger.error(f"Error labeling scan_result {scan_result.id}: {e}")
                failed += 1
                continue

        # Commit remaining
        if batch:
            session.add_all(batch)
            session.commit()
            logger.info(f"Committed final batch of {len(batch)} labels")

        logger.info(
            f"Labeling complete: {labeled} labeled, {failed} failed. "
            f"Outcomes: {outcome_counts}"
        )


if __name__ == '__main__':
    main()
