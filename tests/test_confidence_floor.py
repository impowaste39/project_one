import ast
import os

from utils.helpers import resolve_base_threshold

PT = {'bullish_ma_crossover': 65, 'macd_bullish_crossover': 68, 'pullback_in_uptrend': 72}


def test_floor_below_all_thresholds_changes_nothing():
    assert resolve_base_threshold(['bullish_ma_crossover'], PT, 58) == 65


def test_floor_above_a_pattern_threshold_raises_it():
    assert resolve_base_threshold(['bullish_ma_crossover'], PT, 70) == 70


def test_highest_pattern_threshold_wins():
    assert resolve_base_threshold(['bullish_ma_crossover', 'pullback_in_uptrend'], PT, 58) == 72


def test_no_patterns_or_unknown_patterns_use_the_floor():
    assert resolve_base_threshold([], PT, 58) == 58
    assert resolve_base_threshold(None, PT, 58) == 58
    assert resolve_base_threshold(['not_a_pattern'], PT, 58) == 58


def test_adaptive_lowered_threshold_cannot_go_below_floor():
    adaptive = dict(PT, bullish_ma_crossover=60)   # adaptive rule can lower to 60
    assert resolve_base_threshold(['bullish_ma_crossover'], adaptive, 58) == 60
    assert resolve_base_threshold(['bullish_ma_crossover'], adaptive, 64) == 64


def test_entry_gate_actually_uses_the_helper():
    """Guards against a revert: should_enter_trade must call resolve_base_threshold."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "core", "trading_brain.py")).read()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "should_enter_trade")
    calls = {c.func.id for c in ast.walk(fn)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "resolve_base_threshold" in calls
