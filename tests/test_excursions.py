"""
Unit tests for update_excursions() (WP3).
Pure function — no database or yfinance needed.
"""

import pytest
from utils.helpers import update_excursions


class TestUpdateExcursions:
    def test_initial_mae_mfe_from_entry(self):
        """First price update: MAE and MFE both equal unrealized P&L %."""
        mae, mfe = update_excursions(entry_price=100.0, current_price=105.0)
        assert mae == 5.0
        assert mfe == 5.0

    def test_mfe_updates_on_new_high(self):
        """MFE increases when price makes a new favorable high."""
        mae, mfe = update_excursions(entry_price=100.0, current_price=102.0,
                                     current_mae_pct=-1.0, current_mfe_pct=2.0)
        assert mae == -1.0  # unchanged, current is better
        assert mfe == 2.0   # unchanged, 2.0 > current unrealized

    def test_mae_updates_on_new_low(self):
        """MAE decreases (more adverse) when price makes a new adverse low."""
        mae, mfe = update_excursions(entry_price=100.0, current_price=97.0,
                                     current_mae_pct=-1.0, current_mfe_pct=3.0)
        assert mae == -3.0  # new low: -3% < -1%
        assert mfe == 3.0   # unchanged

    def test_mae_stays_at_worst_point(self):
        """MAE doesn't recover when price comes back toward entry."""
        mae, mfe = update_excursions(entry_price=100.0, current_price=99.0,
                                     current_mae_pct=-5.0, current_mfe_pct=0.0)
        assert mae == -5.0  # stays at worst
        assert mfe == 0.0   # unchanged

    def test_zero_entry_price_returns_current(self):
        """Invalid entry price: returns current values unchanged."""
        mae, mfe = update_excursions(entry_price=0.0, current_price=100.0,
                                     current_mae_pct=-2.0, current_mfe_pct=3.0)
        assert mae == -2.0
        assert mfe == 3.0

    def test_zero_current_price_returns_current(self):
        """Invalid current price: returns current values unchanged."""
        mae, mfe = update_excursions(entry_price=100.0, current_price=0.0,
                                     current_mae_pct=-2.0, current_mfe_pct=3.0)
        assert mae == -2.0
        assert mfe == 3.0

    def test_default_current_values_zero(self):
        """No prior MAE/MFE: starts from current unrealized P&L %."""
        mae, mfe = update_excursions(entry_price=100.0, current_price=95.0)
        assert mae == -5.0
        assert mfe == -5.0  # unrealized is negative, so both are -5%

    def test_rounding_to_4_decimals(self):
        """Results rounded to 4 decimal places."""
        mae, mfe = update_excursions(entry_price=100.0, current_price=100.12345)
        assert mae == 0.1235
        assert mfe == 0.1235
