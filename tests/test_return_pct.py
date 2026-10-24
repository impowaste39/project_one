from utils.helpers import calc_return_pct


def test_live_numbers_give_about_minus_4_37_pct():
    # total 157,796.72 with realized -7,203.28 -> contributed base 165,000
    assert calc_return_pct(157796.72, -7203.28) == -4.3656


def test_profit():
    assert calc_return_pct(11000.0, 1000.0) == 10.0


def test_topup_does_not_change_realized_return_basis():
    # 10k base, +500 realized; then 90k top-up: 500 / 100k
    assert calc_return_pct(100500.0, 500.0) == 0.5


def test_no_trades_is_zero():
    assert calc_return_pct(165000.0, 0.0) == 0.0


def test_guards_against_zero_or_negative_base_and_none():
    assert calc_return_pct(0, 0) == 0.0
    assert calc_return_pct(None, None) == 0.0
    assert calc_return_pct(-100.0, 50.0) == 0.0
