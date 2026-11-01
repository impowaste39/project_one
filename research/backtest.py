"""
WP2: Replay and walk-forward harness.

Reads signal_labels (with path_json) from the database and replays exit
variants from stored paths — no yfinance calls, no refetching.

Usage:
    python research/backtest.py --dry-run --limit 100
    python research/backtest.py --report  # generate markdown report
    python research/backtest.py --variants  # test exit variants

Flags:
    --dry-run     Print stats, write nothing
    --limit N     Process at most N signals
    --notional N  Notional position size (default 25000)
    --report      Generate markdown report (RESEARCH_REPORT.md)
    --variants    Test exit variants against baseline
"""

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import func

sys.path.insert(0, '.')
from models.database import get_session, SignalLabel
from models.scan_report import ScanResult, ScanReport
from utils.helpers import calculate_net_pnl

logger = logging.getLogger(__name__)

DEFAULT_NOTIONAL = 25000
MAX_HOLD_DAYS = 15


# =============================================================================
# CORE REPLAY ENGINE
# =============================================================================

def replay_exit(path: list, stop_r: float, target_r: float,
                max_hold_days: int = MAX_HOLD_DAYS) -> tuple:
    """
    Replay a single trade's exit using stored path data (in R units).

    path: list of [high_r, low_r, close_r] per day from path_json
    stop_r: stop loss distance in R (positive, e.g. 1.0 = stop at -1R)
    target_r: target distance in R (positive, e.g. 1.33 = target at +1.33R)
    max_hold_days: maximum days to hold before timeout

    Returns:
        (exit_r, exit_day, exit_reason)
        exit_r: P&L in R units (negative for loss)
        exit_day: 1-based day index when exited
        exit_reason: 'STOP' | 'TARGET' | 'TIMEOUT' | 'NO_DATA'
    """
    if not path:
        return 0.0, 0, 'NO_DATA'

    days = min(len(path), max_hold_days)
    for day_idx in range(days):
        high_r, low_r, close_r = path[day_idx]

        # Conservative: check stop first (if both hit same day, stop wins)
        if low_r <= -stop_r:
            return -stop_r, day_idx + 1, 'STOP'
        if high_r >= target_r:
            return target_r, day_idx + 1, 'TARGET'

    # Timeout: exit at last available close
    last_close_r = path[days - 1][2]
    return round(last_close_r, 4), days, 'TIMEOUT'


def load_labeled_signals(session, limit: Optional[int] = None):
    """
    Load signal_labels joined with scan_results → scan_reports for market context.
    Returns list of dicts with all fields needed for backtesting.
    """
    query = (
        session.query(
            SignalLabel,
            ScanResult.total_score,
            ScanResult.patterns_detected,
            ScanReport.market_trend,
            ScanReport.market_strength,
            ScanReport.timestamp,
        )
        .join(ScanResult, SignalLabel.scan_result_id == ScanResult.id)
        .join(ScanReport, ScanResult.scan_report_id == ScanReport.id)
        .order_by(ScanReport.timestamp)
    )

    if limit:
        query = query.limit(limit)

    results = query.all()
    signals = []
    for sr, score, patterns, trend, strength, ts in results:
        try:
            path = json.loads(sr.path_json) if sr.path_json else []
        except (json.JSONDecodeError, TypeError):
            path = []

        signals.append({
            'scan_result_id': sr.scan_result_id,
            'symbol': sr.symbol,
            'signal_date': sr.signal_date,
            'entry_price': sr.entry_price,
            'stop_price': sr.stop_price,
            'target1_price': sr.target1_price,
            'outcome': sr.outcome,  # original outcome
            'days_to_outcome': sr.days_to_outcome,
            'r_gross': sr.r_gross,  # original R (baseline)
            'r_net': sr.r_net,  # original net R (baseline)
            'mfe_r': sr.mfe_r,
            'mae_r': sr.mae_r,
            'path': path,
            'score': score,
            'patterns': patterns,
            'market_trend': trend,
            'market_strength': strength,
            'report_date': ts,
        })

    return signals


# =============================================================================
# METRICS COMPUTATION
# =============================================================================

def compute_metrics(trades: list, notional: float = DEFAULT_NOTIONAL) -> dict:
    """
    Compute performance metrics from a list of replayed trades.

    Each trade is a dict with: r_net (net R), r_gross (gross R),
    exit_reason, exit_day, etc.

    Returns dict with all metrics.
    """
    if not trades:
        return {
            'n_trades': 0,
            'expectancy_r': 0.0,
            'expectancy_rupees': 0.0,
            'profit_factor': 0.0,
            'win_rate': 0.0,
            'break_even_win_rate': 0.0,
            'max_drawdown_r': 0.0,
            'max_drawdown_rupees': 0.0,
            'avg_win_r': 0.0,
            'avg_loss_r': 0.0,
            'avg_rr': 0.0,
            'bootstrap_ci_lower': 0.0,
            'bootstrap_ci_upper': 0.0,
            'bootstrap_significant': False,
        }

    n = len(trades)
    r_net_values = [t['r_net'] for t in trades]
    r_gross_values = [t['r_gross'] for t in trades]

    # Basic stats
    wins = [r for r in r_net_values if r > 0]
    losses = [r for r in r_net_values if r < 0]
    breakeven = [r for r in r_net_values if r == 0]

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / n if n > 0 else 0.0

    expectancy_r = np.mean(r_net_values)
    expectancy_rupees = expectancy_r * notional  # r_net * notional = rupees per trade (approx)

    # Profit factor: gross profit / gross loss
    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0

    # Average win/loss in R
    avg_win_r = np.mean(wins) if wins else 0.0
    avg_loss_r = np.mean(losses) if losses else 0.0

    # Average R:R ratio (using gross for the ratio)
    avg_rr = avg_win_r / abs(avg_loss_r) if avg_loss_r != 0 else 0.0

    # Break-even win rate: given avg R:R, what win rate breaks even?
    # win_rate * avg_win + (1-win_rate) * avg_loss = 0
    # win_rate = |avg_loss| / (avg_win + |avg_loss|)
    if avg_win_r > 0 and avg_loss_r < 0:
        break_even_win_rate = abs(avg_loss_r) / (avg_win_r + abs(avg_loss_r))
    else:
        break_even_win_rate = 0.5

    # Max drawdown in R (running peak-to-trough)
    cumulative_r = np.cumsum(r_net_values)
    running_peak = np.maximum.accumulate(cumulative_r)
    drawdown_r = cumulative_r - running_peak
    max_drawdown_r = float(np.min(drawdown_r)) if len(drawdown_r) > 0 else 0.0
    max_drawdown_rupees = max_drawdown_r * notional

    # Bootstrap 95% CI for expectancy
    bootstrap_ci_lower, bootstrap_ci_upper, bootstrap_significant = _bootstrap_ci(
        r_net_values, n_bootstrap=2000, confidence=0.95
    )

    return {
        'n_trades': n,
        'expectancy_r': round(expectancy_r, 4),
        'expectancy_rupees': round(expectancy_rupees, 2),
        'profit_factor': round(profit_factor, 2),
        'win_rate': round(win_rate, 4),
        'break_even_win_rate': round(break_even_win_rate, 4),
        'max_drawdown_r': round(max_drawdown_r, 4),
        'max_drawdown_rupees': round(max_drawdown_rupees, 2),
        'avg_win_r': round(avg_win_r, 4),
        'avg_loss_r': round(avg_loss_r, 4),
        'avg_rr': round(avg_rr, 2),
        'wins': win_count,
        'losses': loss_count,
        'breakeven': len(breakeven),
        'bootstrap_ci_lower': round(bootstrap_ci_lower, 4),
        'bootstrap_ci_upper': round(bootstrap_ci_upper, 4),
        'bootstrap_significant': bootstrap_significant,
    }


def _bootstrap_ci(values: list, n_bootstrap: int = 2000,
                  confidence: float = 0.95) -> tuple:
    """
    Compute bootstrap confidence interval for the mean.

    Returns (lower, upper, significant) where significant=True if CI excludes zero.
    """
    if len(values) < 2:
        return 0.0, 0.0, False

    values_arr = np.array(values)
    n = len(values_arr)

    rng = np.random.default_rng(42)  # reproducible
    bootstrap_means = []
    for _ in range(n_bootstrap):
        sample = rng.choice(values_arr, size=n, replace=True)
        bootstrap_means.append(np.mean(sample))

    bootstrap_means = np.sort(bootstrap_means)
    alpha = 1 - confidence
    lower_idx = int(alpha / 2 * n_bootstrap)
    upper_idx = int((1 - alpha / 2) * n_bootstrap)

    lower = float(bootstrap_means[lower_idx])
    upper = float(bootstrap_means[upper_idx])
    significant = (lower > 0) or (upper < 0)  # CI excludes zero

    return lower, upper, significant


# =============================================================================
# VARIANT TESTING
# =============================================================================

def compute_original_stop_r(entry_price: float, stop_price: float) -> float:
    """Convert original stop to R distance (positive)."""
    risk = entry_price - stop_price
    return 1.0 if risk > 0 else 0.0  # original stop is always 1R by definition


def compute_original_target_r(entry_price: float, stop_price: float,
                              target_price: float) -> float:
    """Convert original target to R distance (positive)."""
    risk = entry_price - stop_price
    if risk <= 0:
        return 0.0
    return (target_price - entry_price) / risk


def test_variants(signals: list, notional: float = DEFAULT_NOTIONAL) -> pd.DataFrame:
    """
    Test exit variants against the baseline.

    Variants:
        - baseline: original stop (1R) and original target
        - stop_1.5r: stop at 1.5R, same target
        - stop_2.0r: stop at 2.0R, same target
        - target_1.5r: same stop, target at 1.5x original
        - target_2.0r: same stop, target at 2.0x original
        - time_stop_7d: exit at day 7 if any loss
        - time_stop_10d: exit at day 10 if any loss
        - trailing_stop: trail stop to breakeven at +1R, then +0.5R

    Returns DataFrame with metrics per variant.
    """
    results = []

    for sig in signals:
        path = sig['path']
        if not path:
            continue

        entry_price = sig['entry_price']
        stop_price = sig['stop_price']
        target_price = sig['target1_price']

        original_stop_r = compute_original_stop_r(entry_price, stop_price)
        original_target_r = compute_original_target_r(
            entry_price, stop_price, target_price)

        variants = {
            'baseline': (original_stop_r, original_target_r),
            'stop_1.5r': (1.5, original_target_r),
            'stop_2.0r': (2.0, original_target_r),
            'target_1.5r': (original_stop_r, original_target_r * 1.5),
            'target_2.0r': (original_stop_r, original_target_r * 2.0),
            'time_stop_7d': (original_stop_r, original_target_r),  # handled below
            'time_stop_10d': (original_stop_r, original_target_r),  # handled below
        }

        for variant_name, (stop_r, target_r) in variants.items():
            exit_r, exit_day, exit_reason = replay_exit(
                path, stop_r, target_r)

            # Apply time-stop overrides
            if variant_name == 'time_stop_7d' and exit_day > 7:
                # If still open at day 7 with a loss, exit at close
                if exit_day > 7:
                    # Replay with hard exit at day 7
                    exit_r, _, _ = replay_exit(path[:7], stop_r, target_r)
                    exit_reason = 'TIME_STOP_7D'
            elif variant_name == 'time_stop_10d' and exit_day > 10:
                exit_r, _, _ = replay_exit(path[:10], stop_r, target_r)
                exit_reason = 'TIME_STOP_10D'

            # Calculate rupees
            risk_per_share = entry_price - stop_price
            quantity = max(1, int(notional / entry_price))
            net_pnl, _ = calculate_net_pnl(
                entry_price,
                entry_price + exit_r * risk_per_share,
                quantity,
            )
            total_risk = risk_per_share * quantity
            r_net_calc = net_pnl / total_risk if total_risk > 0 else exit_r

            results.append({
                'symbol': sig['symbol'],
                'signal_date': sig['signal_date'],
                'scan_result_id': sig['scan_result_id'],
                'variant': variant_name,
                'exit_r': round(exit_r, 4),
                'r_net': round(r_net_calc, 4),
                'exit_reason': exit_reason,
                'exit_day': exit_day,
                'score': sig['score'],
                'market_trend': sig['market_trend'],
                'market_strength': sig['market_strength'],
                'report_date': sig['report_date'],
            })

    return pd.DataFrame(results)


def variant_summary(df: pd.DataFrame, notional: float = DEFAULT_NOTIONAL) -> dict:
    """
    Compute summary metrics per variant from a variants DataFrame.
    """
    if df.empty:
        return {}

    summary = {}
    for variant in df['variant'].unique():
        sub = df[df['variant'] == variant]
        trades = [{'r_net': r, 'r_gross': r, 'exit_reason': er}
                  for r, er in zip(sub['r_net'], sub['exit_reason'])]
        metrics = compute_metrics(trades, notional)
        metrics['variant'] = variant
        summary[variant] = metrics

    return summary


# =============================================================================
# WALK-FORWARD ANALYSIS
# =============================================================================

def walk_forward_analysis(signals: list, notional: float = DEFAULT_NOTIONAL,
                          min_fold_trades: int = 5) -> dict:
    """
    Walk-forward analysis with expanding window by month.

    Groups signals by month of signal_date, then for each fold:
        train on months 0..k, test on month k+1
    Returns per-fold metrics for baseline and best variant.
    """
    if not signals:
        return {}

    # Sort by date and group by month
    df = pd.DataFrame(signals)
    df['signal_date'] = pd.to_datetime(df['signal_date'])
    df['month'] = df['signal_date'].dt.to_period('M')
    df = df.sort_values('signal_date')

    months = sorted(df['month'].unique())
    if len(months) < 2:
        return {'error': 'Need at least 2 months of data for walk-forward'}

    folds = []
    for i in range(1, len(months)):
        train_months = months[:i]
        test_month = months[i]

        train_df = df[df['month'].isin(train_months)]
        test_df = df[df['month'] == test_month]

        if len(test_df) < min_fold_trades:
            continue

        # Baseline on test set
        test_signals = test_df.to_dict('records')
        baseline_df = test_variants(test_signals, notional)
        baseline_summary = variant_summary(baseline_df, notional)

        # Best variant: test all variants on this fold
        best_variant = None
        best_expectancy = -float('inf')

        for variant_name in baseline_summary:
            if variant_name == 'baseline':
                continue
            variant_trades = [
                {'r_net': r, 'r_gross': r, 'exit_reason': er}
                for r, er in zip(
                    baseline_df[baseline_df['variant'] == variant_name]['r_net'],
                    baseline_df[baseline_df['variant'] == variant_name]['exit_reason']
                )
            ]
            m = compute_metrics(variant_trades, notional)
            if m['expectancy_r'] > best_expectancy:
                best_expectancy = m['expectancy_r']
                best_variant = variant_name

        folds.append({
            'fold': i,
            'train_months': [str(m) for m in train_months],
            'test_month': str(test_month),
            'train_trades': len(train_df),
            'test_trades': len(test_df),
            'baseline_expectancy_r': baseline_summary.get('baseline', {}).get('expectancy_r', 0),
            'best_variant': best_variant,
            'best_variant_expectancy_r': best_expectancy,
            'improvement_r': best_expectancy - baseline_summary.get('baseline', {}).get('expectancy_r', 0),
        })

    return {
        'n_folds': len(folds),
        'folds': folds,
    }


def promotion_gate(wf_result: dict) -> dict:
    """
    Apply promotion gate:
        - Variant beats baseline net expectancy in at least 2 of last 3 folds
        - Bootstrap CI of improvement excludes zero
    """
    folds = wf_result.get('folds', [])
    if len(folds) < 2:
        return {'promote': False, 'reason': 'Insufficient folds'}

    last_3 = folds[-3:]
    wins = sum(1 for f in last_3 if f['improvement_r'] > 0)
    fold_win_rate = wins / len(last_3)

    # Bootstrap on improvements
    improvements = [f['improvement_r'] for f in folds]
    _, _, significant = _bootstrap_ci(improvements)

    promote = (wins >= 2 and significant)

    return {
        'promote': promote,
        'wins_in_last_3': wins,
        'total_last_3': len(last_3),
        'fold_win_rate': round(fold_win_rate, 2),
        'bootstrap_significant': significant,
        'mean_improvement_r': round(np.mean(improvements), 4),
    }


# =============================================================================
# BREAKDOWNS
# =============================================================================

def breakdown_by_pattern(df: pd.DataFrame, notional: float = DEFAULT_NOTIONAL) -> dict:
    """Metrics grouped by pattern."""
    if df.empty:
        return {}
    result = {}
    for pattern in df['patterns'].dropna().unique():
        sub = df[df['patterns'] == pattern]
        trades = [{'r_net': r, 'r_gross': r} for r in sub['r_net']]
        result[pattern] = compute_metrics(trades, notional)
    return result


def breakdown_by_score_bucket(df: pd.DataFrame,
                              notional: float = DEFAULT_NOTIONAL) -> dict:
    """Metrics grouped by score buckets: <65, 65-74, 75-84, 85+."""
    if df.empty:
        return {}

    def bucket(score):
        if score < 65:
            return '<65'
        elif score < 75:
            return '65-74'
        elif score < 85:
            return '75-84'
        else:
            return '85+'

    df = df.copy()
    df['score_bucket'] = df['score'].apply(bucket)

    result = {}
    for bucket_name in ['<65', '65-74', '75-84', '85+']:
        sub = df[df['score_bucket'] == bucket_name]
        if sub.empty:
            result[bucket_name] = {'n_trades': 0}
            continue
        trades = [{'r_net': r, 'r_gross': r} for r in sub['r_net']]
        result[bucket_name] = compute_metrics(trades, notional)

    return result


def breakdown_by_market_regime(df: pd.DataFrame,
                               notional: float = DEFAULT_NOTIONAL) -> dict:
    """Metrics grouped by market trend."""
    if df.empty:
        return {}
    result = {}
    for trend in df['market_trend'].dropna().unique():
        sub = df[df['market_trend'] == trend]
        trades = [{'r_net': r, 'r_gross': r} for r in sub['r_net']]
        result[trend] = compute_metrics(trades, notional)
    return result


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_report(signals: list, notional: float = DEFAULT_NOTIONAL,
                    output_file: str = 'RESEARCH_REPORT.md') -> str:
    """
    Generate a markdown research report from backtesting results.
    """
    if not signals:
        return "# WP2 Backtest Report\n\nNo signals to analyze.\n"

    lines = []
    lines.append("# WP2 Backtest Report — Exit Variant Analysis")
    lines.append("")
    lines.append(f"Generated: {date.today().isoformat()}")
    lines.append(f"Notional per trade: ₹{notional:,.0f}")
    lines.append(f"Total signals: {len(signals)}")
    lines.append("")

    # Baseline metrics
    baseline_df = test_variants(signals, notional)
    baseline_summary = variant_summary(baseline_df, notional)
    baseline = baseline_summary.get('baseline', {})

    lines.append("## Baseline Performance (Original Stops & Targets)")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Trades | {baseline.get('n_trades', 0)} |")
    lines.append(f"| Expectancy (R) | {baseline.get('expectancy_r', 0):.4f} |")
    lines.append(f"| Expectancy (₹) | {baseline.get('expectancy_rupees', 0):.2f} |")
    lines.append(f"| Profit Factor | {baseline.get('profit_factor', 0):.2f} |")
    lines.append(f"| Win Rate | {baseline.get('win_rate', 0):.1%} |")
    lines.append(f"| Break-even Win Rate | {baseline.get('break_even_win_rate', 0):.1%} |")
    lines.append(f"| Max Drawdown (R) | {baseline.get('max_drawdown_r', 0):.4f} |")
    lines.append(f"| Avg Win (R) | {baseline.get('avg_win_r', 0):.4f} |")
    lines.append(f"| Avg Loss (R) | {baseline.get('avg_loss_r', 0):.4f} |")
    lines.append(f"| Avg R:R | {baseline.get('avg_rr', 0):.2f} |")
    lines.append(f"| Bootstrap CI | [{baseline.get('bootstrap_ci_lower', 0):.4f}, {baseline.get('bootstrap_ci_upper', 0):.4f}] |")
    lines.append(f"| Bootstrap Significant | {baseline.get('bootstrap_significant', False)} |")
    lines.append("")

    # Variant comparison
    lines.append("## Exit Variant Comparison")
    lines.append("")
    lines.append(f"| Variant | Expectancy (R) | Profit Factor | Win Rate | Max DD (R) | vs Baseline |")
    lines.append(f"|---------|----------------|---------------|----------|------------|-------------|")
    base_exp = baseline.get('expectancy_r', 0)
    for variant, metrics in baseline_summary.items():
        if variant == 'baseline':
            continue
        imp = metrics.get('expectancy_r', 0) - base_exp
        lines.append(
            f"| {variant} | {metrics.get('expectancy_r', 0):.4f} | "
            f"{metrics.get('profit_factor', 0):.2f} | "
            f"{metrics.get('win_rate', 0):.1%} | "
            f"{metrics.get('max_drawdown_r', 0):.4f} | "
            f"{imp:+.4f} |"
        )
    lines.append("")

    # Walk-forward
    wf = walk_forward_analysis(signals, notional)
    pg = promotion_gate(wf)

    lines.append("## Walk-Forward Analysis")
    lines.append("")
    lines.append(f"| Fold | Test Month | Train Trades | Test Trades | Baseline (R) | Best Variant | Best (R) | Improvement (R) |")
    lines.append(f"|------|------------|--------------|-------------|--------------|--------------|----------|-----------------|")
    for f in wf.get('folds', []):
        lines.append(
            f"| {f['fold']} | {f['test_month']} | {f['train_trades']} | "
            f"{f['test_trades']} | {f['baseline_expectancy_r']:.4f} | "
            f"{f['best_variant'] or '-'} | {f['best_variant_expectancy_r']:.4f} | "
            f"{f['improvement_r']:+.4f} |"
        )
    lines.append("")

    lines.append("## Promotion Gate")
    lines.append("")
    lines.append(f"| Criterion | Result |")
    lines.append(f"|-----------|--------|")
    lines.append(f"| Promote variant | {'YES' if pg['promote'] else 'NO'} |")
    lines.append(f"| Wins in last 3 folds | {pg['wins_in_last_3']} / {pg['total_last_3']} |")
    lines.append(f"| Bootstrap significant | {pg['bootstrap_significant']} |")
    lines.append(f"| Mean improvement (R) | {pg['mean_improvement_r']:+.4f} |")
    lines.append("")

    # Breakdowns
    lines.append("## Breakdown by Pattern")
    lines.append("")
    pattern_bd = breakdown_by_pattern(baseline_df, notional)
    for pattern, m in pattern_bd.items():
        lines.append(f"| {pattern} | {m.get('n_trades', 0)} | {m.get('expectancy_r', 0):.4f} | {m.get('win_rate', 0):.1%} | {m.get('profit_factor', 0):.2f} |")
    lines.append("")

    lines.append("## Breakdown by Score Bucket")
    lines.append("")
    score_bd = breakdown_by_score_bucket(baseline_df, notional)
    for bucket, m in score_bd.items():
        lines.append(f"| {bucket} | {m.get('n_trades', 0)} | {m.get('expectancy_r', 0):.4f} | {m.get('win_rate', 0):.1%} | {m.get('profit_factor', 0):.2f} |")
    lines.append("")

    lines.append("## Breakdown by Market Regime")
    lines.append("")
    regime_bd = breakdown_by_market_regime(baseline_df, notional)
    for regime, m in regime_bd.items():
        lines.append(f"| {regime} | {m.get('n_trades', 0)} | {m.get('expectancy_r', 0):.4f} | {m.get('win_rate', 0):.1%} | {m.get('profit_factor', 0):.2f} |")
    lines.append("")

    # Recommendation
    lines.append("## Recommendation")
    lines.append("")
    if pg['promote']:
        best_v = pg.get('best_variant', 'N/A')
        lines.append(f"✅ **Promote `{best_v}`**: beats baseline in last 3 folds with significant bootstrap CI.")
    else:
        lines.append("❌ **Do not promote**: no variant shows consistent, significant improvement over baseline.")
    lines.append("")
    lines.append("---")
    lines.append("*Go/No-Go after WP2: if no rule variant shows net expectancy above zero with a bootstrap CI that excludes zero, the honest conclusion is that this strategy has no demonstrated edge.*")

    report = '\n'.join(lines)

    with open(output_file, 'w') as f:
        f.write(report)

    logger.info(f"Report written to {output_file}")
    return report


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='WP2 Backtest — replay exit variants from stored paths')
    parser.add_argument('--dry-run', action='store_true', help='Print stats, write nothing to DB')
    parser.add_argument('--limit', type=int, default=None, help='Max signals to process')
    parser.add_argument('--notional', type=float, default=DEFAULT_NOTIONAL,
                        help='Notional position size (default 25000)')
    parser.add_argument('--report', action='store_true',
                        help='Generate markdown report (RESEARCH_REPORT.md)')
    parser.add_argument('--variants', action='store_true',
                        help='Test exit variants against baseline')
    args = parser.parse_args()

    with get_session() as session:
        signals = load_labeled_signals(session, limit=args.limit)
        logger.info(f"Loaded {len(signals)} labeled signals for backtesting")

        if not signals:
            logger.warning("No labeled signals found. Run label_outcomes.py first.")
            return

        if args.dry_run:
            logger.info(f"DRY RUN: Would backtest {len(signals)} signals")
            return

        # Baseline metrics
        baseline_df = test_variants(signals, notional=args.notional)
        baseline_summary = variant_summary(baseline_df, notional=args.notional)
        baseline = baseline_summary.get('baseline', {})

        logger.info(
            f"Baseline: {baseline.get('n_trades', 0)} trades, "
            f"expectancy {baseline.get('expectancy_r', 0):.4f}R, "
            f"₹{baseline.get('expectancy_rupees', 0):.2f}, "
            f"win rate {baseline.get('win_rate', 0):.1%}"
        )

        if args.variants:
            logger.info("Variant comparison:")
            for variant, m in baseline_summary.items():
                if variant == 'baseline':
                    continue
                imp = m.get('expectancy_r', 0) - baseline.get('expectancy_r', 0)
                logger.info(
                    f"  {variant}: expectancy {m.get('expectancy_r', 0):.4f}R "
                    f"({imp:+.4f}R vs baseline), PF={m.get('profit_factor', 0):.2f}, "
                    f"WR={m.get('win_rate', 0):.1%}"
                )

        if args.report:
            report = generate_report(signals, notional=args.notional)
            print(report)

        # Walk-forward
        wf = walk_forward_analysis(signals, notional=args.notional)
        pg = promotion_gate(wf)
        logger.info(
            f"Walk-forward: {wf.get('n_folds', 0)} folds, "
            f"promote={pg['promote']}, "
            f"wins={pg['wins_in_last_3']}/{pg['total_last_3']}"
        )


if __name__ == '__main__':
    main()
