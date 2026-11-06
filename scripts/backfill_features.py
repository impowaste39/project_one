#!/usr/bin/env python3
"""
Backfill features_json for existing signal_labels.
Re-fetches yfinance data for each labeled symbol and computes features.
"""

import json
import logging
import sys
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, '.')
from core.features import build_features
from models.database import get_session, SignalLabel
from models.scan_report import ScanResult, ScanReport

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def backfill_features(limit: int | None = None):
    """Backfill features_json for existing signal_labels."""
    with get_session() as session:
        # Get labeled signals without features_json
        query = (
            session.query(SignalLabel, ScanResult, ScanReport)
            .join(ScanResult, SignalLabel.scan_result_id == ScanResult.id)
            .join(ScanReport, ScanResult.scan_report_id == ScanReport.id)
            .filter(ScanResult.features_json.is_(None))
        )

        if limit:
            query = query.limit(limit)

        rows = query.all()
        logger.info(f"Found {len(rows)} signals without features_json")

        updated = 0
        skipped = 0

        for sl, sr, sr_report in rows:
            try:
                # Build analysis dict from scan_result
                analysis = {
                    'symbol': sl.symbol,
                    'current_price': sl.entry_price,
                    'entry_price': sl.entry_price,
                    'rsi': sl.entry_price and sr.rsi,
                    'macd': sr.macd,
                    'volume_ratio': sr.volume_ratio,
                    'atr': sr.atr,
                    'patterns': json.loads(sr.patterns_detected) if sr.patterns_detected else [],
                    'pattern_count': sr.pattern_count or 0,
                }

                market_context = {
                    'trend': sr_report.market_trend or 'sideways',
                    'strength': sr_report.market_strength or 50.0,
                    'nifty_price': sr_report.nifty_price,
                    'nifty_rsi': sr_report.nifty_rsi,
                    'market_breadth': sr_report.market_breadth,
                }

                features = build_features(analysis, market_context)

                # Update scan_result with features_json
                sr.features_json = json.dumps(features)
                session.add(sr)
                updated += 1

                if updated % 50 == 0:
                    session.commit()
                    logger.info(f"Updated {updated} signals...")

            except Exception as e:
                logger.warning(f"Failed to backfill {sl.symbol}: {e}")
                skipped += 1
                continue

        session.commit()
        logger.info(f"Backfill complete: {updated} updated, {skipped} skipped")
