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
    # now = get_ist_now()

    # # Weekend check
    # if now.weekday() >= 5:
    #     return False

    # # Market hours: 9:15 AM - 3:30 PM
    # market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    # market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

    # return market_open <= now <= market_close
    return True  # Force it to True for testing


def is_trading_hours():
    """Check if in safe trading window (avoid first/last 15 min)"""
    # now = get_ist_now()

    # if now.weekday() >= 5:
    #     return False

    # # Safe trading: 9:30 AM - 3:15 PM
    # safe_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    # safe_end = now.replace(hour=15, minute=15, second=0, microsecond=0)

    # return safe_start <= now <= safe_end
    return True  # Force it to True for testing


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

    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

    if now < market_open:
        mins_to_open = int((market_open - now).total_seconds() / 60)
        return f"Market Opens in {mins_to_open} min"
    elif now > market_close:
        # For testing, return "Testing Mode (Market Open)"
        return "Market Open (Testing Mode)"
    else:
        mins_to_close = int((market_close - now).total_seconds() / 60)
        return f"Market Open ({mins_to_close} min remaining)"
