"""
Utility helper functions
"""

from datetime import datetime
import pytz
import logging

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')


def get_ist_now():
    """Get current time in IST"""
    return datetime.now(IST)


def is_market_hours():
    """Check if currently in market hours"""
    now = get_ist_now()

    # Weekend check
    if now.weekday() >= 5:
        return False

    # Market hours: 9:15 AM - 3:30 PM
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

    return market_open <= now <= market_close


def is_trading_hours():
    """Check if in safe trading window (avoid first/last 15 min)"""
    now = get_ist_now()

    if now.weekday() >= 5:
        return False

    # Safe trading: 9:30 AM - 3:15 PM
    safe_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    safe_end = now.replace(hour=15, minute=15, second=0, microsecond=0)

    return safe_start <= now <= safe_end


def format_currency(amount):
    """Format amount as Indian currency"""
    if amount is None:
        return "₹0.00"
    return f"₹{amount:,.2f}"


def format_percentage(value):
    """Format value as percentage"""
    if value is None:
        return "0.00%"
    return f"{value:+.2f}%"


def get_market_status_message():
    """Get human-readable market status"""
    now = get_ist_now()

    if now.weekday() >= 5:
        return "Market Closed (Weekend)"

    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

    if now < market_open:
        mins_to_open = int((market_open - now).total_seconds() / 60)
        return f"Market Opens in {mins_to_open} min"
    elif now > market_close:
        return "Market Closed"
    else:
        mins_to_close = int((market_close - now).total_seconds() / 60)
        return f"Market Open ({mins_to_close} min remaining)"

def calculate_net_pnl(
    entry_price: float,
    exit_price: float,
    quantity: int,
    partially_exited: bool = False,
    partial_exit_price: float = None,
    partial_exit_qty: int = None,
    same_day_exit: bool = False,
) -> tuple:
    """
    Calculate real net P&L after Groww equity delivery charges.
    Supports dual-leg partial exits.

    Pure math — no DB or model dependency. Shared by TradingBrain and
    PortfolioManager so neither needs to instantiate the other.

    Returns:
        Tuple of (net_pnl, total_charges)
    """
    if partially_exited and partial_exit_price is not None and partial_exit_qty is not None:
        buy_turnover = entry_price * quantity
        sell_turnover_1 = partial_exit_price * partial_exit_qty
        sell_turnover_2 = exit_price * (quantity - partial_exit_qty)
        sell_turnover = sell_turnover_1 + sell_turnover_2
        gross_pnl = (
            (partial_exit_price - entry_price) * partial_exit_qty
            + (exit_price - entry_price) * (quantity - partial_exit_qty)
        )

        brokerage_buy = min(20.0, buy_turnover * 0.001)
        brokerage_sell_1 = min(20.0, sell_turnover_1 * 0.001)
        brokerage_sell_2 = min(20.0, sell_turnover_2 * 0.001)
        brokerage_sell = brokerage_sell_1 + brokerage_sell_2
        dp = 23.60 if same_day_exit else 23.60 * 2  # Two sell transactions on different days
    else:
        buy_turnover = entry_price * quantity
        sell_turnover = exit_price * quantity
        gross_pnl = (exit_price - entry_price) * quantity

        brokerage_buy = min(20.0, buy_turnover * 0.001)
        brokerage_sell = min(20.0, sell_turnover * 0.001)
        dp = 23.60  # Single sell transaction

    stt = (buy_turnover + sell_turnover) * 0.001
    exchange = (buy_turnover + sell_turnover) * 0.0000297
    stamp = buy_turnover * 0.00015
    sebi_ipft = (buy_turnover + sell_turnover) * 0.000002
    gst = (brokerage_buy + brokerage_sell + exchange + sebi_ipft + dp) * 0.18

    total_charges = round(
        brokerage_buy
        + brokerage_sell
        + stt
        + exchange
        + stamp
        + sebi_ipft
        + dp
        + gst,
        2,
    )
    net_pnl = round(gross_pnl - total_charges, 2)
    return net_pnl, total_charges


def calc_return_pct(total_capital, realized_pnl) -> float:
    """Realized return (%) on contributed capital.

    total_capital only ever moves by realized P&L and top-ups, so
    contributed capital == total_capital - realized_pnl. This stays correct
    after top-ups and needs no INITIAL_CAPITAL env var.
    """
    realized = realized_pnl or 0.0
    base = (total_capital or 0.0) - realized
    if base <= 0:
        return 0.0
    return round(realized / base * 100, 4)


def resolve_base_threshold(patterns, pattern_thresholds, floor) -> int:
    """Entry-score threshold before market-regime scaling.

    The highest threshold among the detected patterns wins. `floor`
    (MIN_CONFIDENCE_SCORE) is a global minimum no pattern may undercut, and is
    the threshold when no known pattern was detected.
    """
    custom = [pattern_thresholds[p] for p in (patterns or []) if p in pattern_thresholds]
    return max(custom + [floor])


