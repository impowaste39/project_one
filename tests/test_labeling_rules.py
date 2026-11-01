"""
Unit tests for the pure labeling logic (WP1).

Tests use synthetic OHLCV bars so no yfinance or database is needed.
Covers: target first, stop first, same-day ambiguity → stop, gap down through stop,
timeout at 15 trading days, missing data.
"""

import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, '.')
from scripts.label_outcomes import apply_labeling_rules, _ns_symbol


def _make_bar(open_p, high, low, close):
    """Create a single-row DataFrame with OHLC columns."""
    return pd.DataFrame(
        [{'Open': open_p, 'High': high, 'Low': low, 'Close': close}]
    )


def _build_df(bars):
    """Build a DataFrame from a list of (open, high, low, close) tuples."""
    rows = [{'Open': o, 'High': h, 'Low': l, 'Close': c} for o, h, l, c in bars]
    return pd.DataFrame(rows)


class TestNsSymbol:
    def test_adds_ns_suffix(self):
        assert _ns_symbol('RELIANCE') == 'RELIANCE.NS'

    def test_keeps_existing_ns(self):
        assert _ns_symbol('RELIANCE.NS') == 'RELIANCE.NS'


class TestTargetFirst:
    """Price hits target before stop → TARGET."""

    def test_target_first(self):
        # entry=100, stop=94, target=108. Day 1: high reaches 108.
        df = _build_df([
            (100.0, 108.0, 99.0, 107.0),  # high touches target
        ])
        result = apply_labeling_rules(
            symbol='TEST.NS',
            entry_price=100.0,
            stop_price=94.0,
            target1_price=108.0,
            signal_date=date(2026, 1, 5),
            df=df,
            notional=25000,
        )
        assert result is not None
        assert result['outcome'] == 'TARGET'
        assert result['days_to_outcome'] == 1
        assert result['r_gross'] == pytest.approx((108.0 - 100.0) / (100.0 - 94.0), abs=0.0001)


class TestStopFirst:
    """Price hits stop before target → STOP."""

    def test_stop_first(self):
        # entry=100, stop=94, target=108. Day 1: low reaches 94.
        df = _build_df([
            (100.0, 101.0, 94.0, 95.0),  # low touches stop
        ])
        result = apply_labeling_rules(
            symbol='TEST.NS',
            entry_price=100.0,
            stop_price=94.0,
            target1_price=108.0,
            signal_date=date(2026, 1, 5),
            df=df,
            notional=25000,
        )
        assert result is not None
        assert result['outcome'] == 'STOP'
        assert result['days_to_outcome'] == 1


class TestSameDayAmbiguity:
    """Both stop and target touched same day → STOP (conservative)."""

    def test_same_day_stop_and_target(self):
        # entry=100, stop=94, target=108. Day 1: low 93, high 109 → both touched.
        df = _build_df([
            (100.0, 109.0, 93.0, 100.0),
        ])
        result = apply_labeling_rules(
            symbol='TEST.NS',
            entry_price=100.0,
            stop_price=94.0,
            target1_price=108.0,
            signal_date=date(2026, 1, 5),
            df=df,
            notional=25000,
        )
        assert result is not None
        assert result['outcome'] == 'STOP'


class TestGapDownThroughStop:
    """Open at or below stop → exit at open (STOP)."""

    def test_gap_down_through_stop(self):
        # entry=100, stop=94, target=108. Day 1: open 92 (below stop).
        df = _build_df([
            (92.0, 95.0, 90.0, 94.0),  # gap down open
        ])
        result = apply_labeling_rules(
            symbol='TEST.NS',
            entry_price=100.0,
            stop_price=94.0,
            target1_price=108.0,
            signal_date=date(2026, 1, 5),
            df=df,
            notional=25000,
        )
        assert result is not None
        assert result['outcome'] == 'STOP'
        assert result['exit_price'] == 92.0  # exit at open, not stop


class TestTimeout:
    """No exit after 15 trading days → TIMEOUT at close."""

    def test_timeout_at_15_days(self):
        # entry=100, stop=94, target=108. Price drifts sideways for 15 days.
        bars = [(100.0, 101.0, 99.0, 100.0)] * 15
        df = _build_df(bars)
        result = apply_labeling_rules(
            symbol='TEST.NS',
            entry_price=100.0,
            stop_price=94.0,
            target1_price=108.0,
            signal_date=date(2026, 1, 5),
            df=df,
            notional=25000,
        )
        assert result is not None
        assert result['outcome'] == 'TIMEOUT'
        assert result['days_to_outcome'] == 15


class TestMissingData:
    """Empty or missing data → None."""

    def test_empty_dataframe(self):
        df = _build_df([])
        result = apply_labeling_rules(
            symbol='TEST.NS',
            entry_price=100.0,
            stop_price=94.0,
            target1_price=108.0,
            signal_date=date(2026, 1, 5),
            df=df,
            notional=25000,
        )
        assert result is None

    def test_missing_columns(self):
        df = pd.DataFrame([{'Open': 100.0, 'Close': 100.0}])  # missing High/Low
        result = apply_labeling_rules(
            symbol='TEST.NS',
            entry_price=100.0,
            stop_price=94.0,
            target1_price=108.0,
            signal_date=date(2026, 1, 5),
            df=df,
            notional=25000,
        )
        assert result is None

    def test_invalid_risk(self):
        # stop >= entry → invalid
        df = _build_df([(100.0, 101.0, 99.0, 100.0)])
        result = apply_labeling_rules(
            symbol='TEST.NS',
            entry_price=100.0,
            stop_price=100.0,  # equal to entry → zero risk
            target1_price=108.0,
            signal_date=date(2026, 1, 5),
            df=df,
            notional=25000,
        )
        assert result is None


class TestPathAndExcursions:
    """MFE/MAE and path_json are recorded correctly."""

    def test_mfe_mae_and_path(self):
        # entry=100, stop=94 (risk=6), target=108
        # Day 1: high=105 (+5/6=0.83R), low=97 (-3/6=-0.5R)
        # Day 2: high=110 (+10/6=1.67R), low=96 (-4/6=-0.67R), close=109 → target hit
        df = _build_df([
            (100.0, 105.0, 97.0, 104.0),
            (104.0, 110.0, 96.0, 109.0),  # high touches target
        ])
        result = apply_labeling_rules(
            symbol='TEST.NS',
            entry_price=100.0,
            stop_price=94.0,
            target1_price=108.0,
            signal_date=date(2026, 1, 5),
            df=df,
            notional=25000,
        )
        assert result is not None
        assert result['outcome'] == 'TARGET'
        assert result['mfe_r'] == pytest.approx(1.67, abs=0.01)
        assert result['mae_r'] == pytest.approx(-0.67, abs=0.01)
        assert result['path_json'] is not None
        path = __import__('json').loads(result['path_json'])
        assert len(path) == 2
        # Day 1: high_r = 5/6 = 0.8333, low_r = -3/6 = -0.5
        assert path[0][0] == pytest.approx(0.8333, abs=0.01)
        assert path[0][1] == pytest.approx(-0.5, abs=0.01)
