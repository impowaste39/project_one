"""
Risk Manager
Handles position sizing and risk calculations
"""

import os
import logging

logger = logging.getLogger(__name__)


class RiskManager:
    """Risk management and position sizing"""

    def __init__(self):
        self.max_risk_per_trade = float(
            os.getenv('RISK_PER_TRADE', 0.02))  # 2% default
        self.max_positions = int(os.getenv('MAX_POSITIONS', 5))
        self.max_portfolio_risk = 0.10  # 10% max total portfolio risk

    def calculate_position_size(self, capital: float, entry_price: float,
                                stop_loss: float) -> dict:
        """
        Calculate position size based on risk

        Args:
            capital: Available capital
            entry_price: Entry price
            stop_loss: Stop loss price

        Returns:
            Dict with quantity and investment details
        """
        if stop_loss >= entry_price:
            logger.warning("Stop loss must be below entry price")
            return {'quantity': 0, 'investment': 0, 'risk_amount': 0}

        # Risk per share
        risk_per_share = entry_price - stop_loss

        # Max risk amount (2% of capital)
        max_risk = capital * self.max_risk_per_trade

        # Position size based on risk
        quantity = int(max_risk / risk_per_share)

        # Ensure we don't invest more than 30% of capital in one trade
        max_investment = capital * 0.30
        max_shares_by_investment = int(max_investment / entry_price)

        # Take the smaller of the two
        quantity = min(quantity, max_shares_by_investment)

        # Minimum 1 share
        quantity = max(1, quantity)

        investment = quantity * entry_price
        risk_amount = quantity * risk_per_share

        return {
            'quantity': quantity,
            'investment': round(investment, 2),
            'risk_amount': round(risk_amount, 2),
            'risk_percent': round((risk_amount / capital) * 100, 2)
        }

    def validate_trade(self, portfolio_state: dict, position_info: dict) -> tuple:
        """
        Validate if trade meets risk criteria

        Args:
            portfolio_state: Current portfolio state
            position_info: Position sizing info

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check max positions
        if portfolio_state['positions_count'] >= self.max_positions:
            return False, f"Maximum positions reached ({self.max_positions})"

        # Check available capital
        if position_info['investment'] > portfolio_state['available_capital']:
            return False, "Insufficient capital"

        # Check minimum investment
        if position_info['investment'] < 500:
            return False, "Investment too small (min ₹500)"

        # Check risk amount
        if position_info['risk_amount'] > portfolio_state['available_capital'] * self.max_risk_per_trade:
            return False, "Risk exceeds limit"

        return True, "Trade validated"

    def calculate_portfolio_risk(self, open_trades: list,
                                 portfolio_total: float) -> dict:
        """
        Calculate total portfolio risk from open positions

        Args:
            open_trades: List of open trade objects
            portfolio_total: Total portfolio value

        Returns:
            Dict with risk metrics
        """
        total_risk = 0

        for trade in open_trades:
            risk = (trade.entry_price - trade.stop_loss) * trade.quantity
            total_risk += risk

        risk_percent = (total_risk / portfolio_total) * \
            100 if portfolio_total > 0 else 0

        return {
            'total_risk': round(total_risk, 2),
            'risk_percent': round(risk_percent, 2),
            'risk_capacity': round(self.max_portfolio_risk * 100 - risk_percent, 2)
        }
