from types import SimpleNamespace as NS

import pytest

from core.risk_manager import RiskManager
from utils.helpers import calc_open_risk


def T(entry, stop, qty, partial=None):
    return NS(entry_price=entry, stop_loss=stop, quantity=qty,
              partially_exited=partial is not None, partial_exit_qty=partial)


def test_open_risk_basic_and_empty():
    assert calc_open_risk([]) == 0.0
    assert calc_open_risk([T(100, 94, 50)]) == 300.0


def test_stop_above_entry_adds_no_risk_and_does_not_offset_others():
    # breakeven/trailing trade must not reduce the total
    assert calc_open_risk([T(100, 94, 50), T(100, 106, 50)]) == 300.0


def test_partial_exit_uses_remaining_quantity():
    assert calc_open_risk([T(100, 94, 100, partial=50)]) == 300.0


STATE = dict(positions_count=2, available_capital=100000.0, total_capital=100000.0)
POS = dict(investment=20000.0, risk_amount=1500.0)


def make(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, str(v))
    return RiskManager()


def test_trade_allowed_when_heat_within_limit(monkeypatch):
    rm = make(monkeypatch, VOLATILE_MARKET_MODE='true', MAX_POSITIONS=30)
    ok, _ = rm.validate_trade(dict(STATE, open_risk_amount=8000.0), POS)   # 8,000 + 1,500 <= 10,000
    assert ok


def test_trade_rejected_when_heat_would_exceed_limit(monkeypatch):
    rm = make(monkeypatch, VOLATILE_MARKET_MODE='true', MAX_POSITIONS=30)
    ok, reason = rm.validate_trade(dict(STATE, open_risk_amount=9000.0), POS)  # 10,500 > 10,000
    assert not ok and 'Portfolio risk limit' in reason


def test_missing_open_risk_key_is_backward_compatible(monkeypatch):
    rm = make(monkeypatch, VOLATILE_MARKET_MODE='true', MAX_POSITIONS=30)
    ok, _ = rm.validate_trade(dict(STATE), POS)
    assert ok


def test_cap_is_configurable_by_env(monkeypatch):
    rm = make(monkeypatch, VOLATILE_MARKET_MODE='true', MAX_POSITIONS=30, MAX_PORTFOLIO_RISK=0.05)
    ok, reason = rm.validate_trade(dict(STATE, open_risk_amount=4000.0), POS)  # 5,500 > 5,000
    assert not ok and '5%' in reason


def test_high_max_positions_is_safe_because_heat_binds_first(monkeypatch):
    # even with MAX_POSITIONS=50, a book already carrying 10% risk takes no new trade
    rm = make(monkeypatch, VOLATILE_MARKET_MODE='true', MAX_POSITIONS=50)
    ok, _ = rm.validate_trade(dict(STATE, positions_count=6, open_risk_amount=10000.0), POS)
    assert not ok