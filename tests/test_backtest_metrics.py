"""
Unit tests for WP2 backtest metrics functions.
Pure functions — no database or yfinance needed.
"""

import pytest
from research.backtest import (
    replay_exit,
    compute_metrics,
    _bootstrap_ci,
    compute_original_stop_r,
    compute_original_target_r,
)


class TestReplayExit:
    def test_target_hit_first(self):
        """Price hits target before stop → TARGET."""
        path = [[1.5, -0.5, 1.0], [2.0, -0.8, 1.8]]  # day 2 high reaches 2.0R target
        exit_r, exit_day, reason = replay_exit(path, stop_r=1.0, target_r=2.0)
        assert reason == 'TARGET'
        assert exit_day == 2
        assert exit_r == 2.0

    def test_stop_hit_first(self):
        """Price hits stop before target → STOP."""
        path = [[0.5, -1.2, 0.3]]  # day 1 low goes below -1.0R stop
        exit_r, exit_day, reason = replay_exit(path, stop_r=1.0, target_r=2.0)
        assert reason == 'STOP'
        assert exit_day == 1
        assert exit_r == -1.0

    def test_same_day_stop_and_target_stop_wins(self):
        """Both stop and target touched same day → STOP (conservative)."""
        path = [[2.0, -1.5, 1.0]]  # high above target, low below stop
        exit_r, exit_day, reason = replay_exit(path, stop_r=1.0, target_r=2.0)
        assert reason == 'STOP'
        assert exit_r == -1.0

    def test_timeout(self):
        """No exit within max_hold_days → TIMEOUT at last close."""
        path = [[0.5, -0.2, 0.4], [0.6, -0.3, 0.5]]  # never hits stop or target
        exit_r, exit_day, reason = replay_exit(path, stop_r=1.0, target_r=2.0, max_hold_days=2)
        assert reason == 'TIMEOUT'
        assert exit_day == 2
        assert exit_r == 0.5

    def test_empty_path(self):
        """Empty path → NO_DATA."""
        exit_r, exit_day, reason = replay_exit([], stop_r=1.0, target_r=2.0)
        assert reason == 'NO_DATA'
        assert exit_r == 0.0
        assert exit_day == 0

    def test_max_hold_days_limit(self):
        """Exit forced at max_hold_days even if path has more days."""
        path = [[0.1, -0.1, 0.0]] * 20  # 20 days, no exit
        exit_r, exit_day, reason = replay_exit(path, stop_r=1.0, target_r=2.0, max_hold_days=5)
        assert reason == 'TIMEOUT'
        assert exit_day == 5


class TestComputeMetrics:
    def test_empty_trades(self):
        """No trades → zero metrics."""
        m = compute_metrics([], notional=25000)
        assert m['n_trades'] == 0
        assert m['expectancy_r'] == 0.0
        assert m['profit_factor'] == 0.0

    def test_all_wins(self):
        """All winning trades."""
        trades = [
            {'r_net': 1.0, 'r_gross': 1.2, 'exit_reason': 'TARGET'},
            {'r_net': 2.0, 'r_gross': 2.2, 'exit_reason': 'TARGET'},
        ]
        m = compute_metrics(trades, notional=25000)
        assert m['n_trades'] == 2
        assert m['win_rate'] == 1.0
        assert m['expectancy_r'] == 1.5
        assert m['profit_factor'] == float('inf')  # no losses

    def test_all_losses(self):
        """All losing trades."""
        trades = [
            {'r_net': -1.0, 'r_gross': -1.0, 'exit_reason': 'STOP'},
            {'r_net': -2.0, 'r_gross': -2.0, 'exit_reason': 'STOP'},
        ]
        m = compute_metrics(trades, notional=25000)
        assert m['n_trades'] == 2
        assert m['win_rate'] == 0.0
        assert m['expectancy_r'] == -1.5
        assert m['profit_factor'] == 0.0

    def test_mixed(self):
        """Mix of wins and losses."""
        trades = [
            {'r_net': 2.0, 'r_gross': 2.2, 'exit_reason': 'TARGET'},
            {'r_net': -1.0, 'r_gross': -1.0, 'exit_reason': 'STOP'},
            {'r_net': 0.5, 'r_gross': 0.6, 'exit_reason': 'TIMEOUT'},
            {'r_net': -0.5, 'r_gross': -0.5, 'exit_reason': 'STOP'},
        ]
        m = compute_metrics(trades, notional=25000)
        assert m['n_trades'] == 4
        assert m['wins'] == 2
        assert m['losses'] == 2
        assert m['win_rate'] == 0.5
        assert m['expectancy_r'] == 0.25  # (2 - 1 + 0.5 - 0.5) / 4

    def test_profit_factor(self):
        """Profit factor = gross profit / gross loss."""
        trades = [
            {'r_net': 3.0, 'r_gross': 3.0, 'exit_reason': 'TARGET'},
            {'r_net': 1.0, 'r_gross': 1.0, 'exit_reason': 'TARGET'},
            {'r_net': -2.0, 'r_gross': -2.0, 'exit_reason': 'STOP'},
        ]
        m = compute_metrics(trades, notional=25000)
        # gross_profit = 4.0, gross_loss = 2.0, PF = 2.0
        assert m['profit_factor'] == 2.0


class TestBootstrapCI:
    def test_positive_ci_excludes_zero(self):
        """All positive values → CI excludes zero → significant."""
        values = [1.0, 1.1, 0.9, 1.2, 0.8] * 50
        lower, upper, significant = _bootstrap_ci(values, n_bootstrap=500)
        assert significant is True
        assert lower > 0

    def test_negative_ci_excludes_zero(self):
        """All negative values → CI excludes zero → significant."""
        values = [-1.0, -1.1, -0.9, -1.2, -0.8] * 50
        lower, upper, significant = _bootstrap_ci(values, n_bootstrap=500)
        assert significant is True
        assert upper < 0

    def test_mixed_ci_includes_zero(self):
        """Mixed values → CI likely includes zero → not significant."""
        values = [1.0, -1.0, 1.0, -1.0] * 100
        lower, upper, significant = _bootstrap_ci(values, n_bootstrap=500)
        assert significant is False
        assert lower < 0 < upper

    def test_insufficient_data(self):
        """Too few values → not significant."""
        lower, upper, significant = _bootstrap_ci([1.0], n_bootstrap=500)
        assert significant is False


class TestRConversion:
    def test_original_stop_r(self):
        """Original stop is always 1R."""
        r = compute_original_stop_r(100.0, 94.0)
        assert r == 1.0

    def test_original_target_r(self):
        """Original target converted to R distance."""
        r = compute_original_target_r(100.0, 94.0, 108.0)
        # risk = 6, target_distance = 8, target_r = 8/6 = 1.333...
        assert r == pytest.approx(1.3333, abs=0.001)

    def test_invalid_risk(self):
        """Zero or negative risk → 0.0."""
        r = compute_original_stop_r(100.0, 100.0)
        assert r == 0.0
        r = compute_original_target_r(100.0, 100.0, 110.0)
        assert r == 0.0
