"""
Portfolio Manager
Handles trade execution and portfolio management
"""

import logging
from datetime import datetime
import json

from models.database import Trade, Portfolio, get_session

logger = logging.getLogger(__name__)


class PortfolioManager:
    """Portfolio and trade management"""

    def __init__(self, db_session=None, risk_manager=None, email_service=None):
        self.db = db_session
        self.risk_manager = risk_manager
        self.email_service = email_service

    def get_portfolio_state(self) -> dict:
        """Get current portfolio state"""
        try:
            portfolio = self.db.query(Portfolio).order_by(
                Portfolio.timestamp.desc()
            ).first()

            if not portfolio:
                return {
                    'total_capital': 5000,
                    'available_capital': 5000,
                    'deployed_capital': 0,
                    'unrealized_pnl': 0,
                    'realized_pnl': 0,
                    'positions_count': 0
                }

            # Count open positions
            open_positions = self.db.query(Trade).filter(
                Trade.status == 'OPEN'
            ).count()

            return {
                'total_capital': portfolio.total_capital,
                'available_capital': portfolio.available_capital,
                'deployed_capital': portfolio.deployed_capital,
                'unrealized_pnl': portfolio.unrealized_pnl,
                'realized_pnl': portfolio.realized_pnl,
                'positions_count': open_positions
            }

        except Exception as e:
            logger.error(f"Error getting portfolio state: {e}")
            return {
                'total_capital': 5000,
                'available_capital': 5000,
                'deployed_capital': 0,
                'unrealized_pnl': 0,
                'realized_pnl': 0,
                'positions_count': 0
            }

    def enter_trade(self, evaluation: dict) -> bool:
        """
        Execute trade entry

        Args:
            evaluation: Trade evaluation from TradingBrain

        Returns:
            True if trade executed successfully
        """
        try:
            # Create trade record — now stores target_2 and target_3
            trade = Trade(
                symbol=evaluation['symbol'],
                entry_date=datetime.now(),
                entry_price=evaluation['entry_price'],
                quantity=evaluation['quantity'],
                entry_score=evaluation['score'],
                stop_loss=evaluation['stop_loss'],
                target=evaluation['target_1'],            # T1 = primary exit
                target_2=evaluation.get('target_2'),     # FIX: was missing
                target_3=evaluation.get('target_3'),     # FIX: was missing
                partially_exited=False,                  # FIX: explicit default
                status='OPEN',
                pattern=evaluation['patterns'][0] if evaluation.get(
                    'patterns') else None,
                confidence_factors=json.dumps(evaluation.get('factors', []))
            )

            self.db.add(trade)

            # Update portfolio
            portfolio = self.db.query(Portfolio).order_by(
                Portfolio.timestamp.desc()
            ).first()

            if portfolio:
                new_portfolio = Portfolio(
                    total_capital=portfolio.total_capital,
                    deployed_capital=portfolio.deployed_capital +
                    evaluation['investment'],
                    available_capital=portfolio.available_capital -
                    evaluation['investment'],
                    unrealized_pnl=portfolio.unrealized_pnl,
                    realized_pnl=portfolio.realized_pnl,
                    open_positions=portfolio.open_positions + 1,
                    timestamp=datetime.now()
                )
                self.db.add(new_portfolio)

            self.db.commit()

            # Send email notification
            if self.email_service:
                self.email_service.send_trade_entry_email(trade, evaluation)

            logger.info(
                f"Trade entered: {trade.symbol} @ ₹{trade.entry_price} "
                f"| T1: ₹{trade.target} | T2: ₹{trade.target_2} | T3: ₹{trade.target_3}")
            return True

        except Exception as e:
            logger.error(f"Error entering trade: {e}")
            self.db.rollback()
            return False

    def exit_trade(self, trade: Trade, exit_price: float, exit_reason: str) -> bool:
        """
        Execute trade exit

        Args:
            trade: Trade object to exit
            exit_price: Exit price
            exit_reason: Reason for exit

        Returns:
            True if trade exited successfully
        """
        try:
            from core.trading_brain import TradingBrain

            # Calculate gross P&L
            gross_pnl = (exit_price - trade.entry_price) * trade.quantity
            profit_loss_pct = (
                (exit_price - trade.entry_price) / trade.entry_price) * 100
            hold_duration = (datetime.now() -
                             trade.entry_date).days if trade.entry_date else 0

            # Calculate net P&L after Groww brokerage charges
            brain = TradingBrain()
            net_pnl, charges = brain.calculate_net_pnl(
                trade.entry_price, exit_price, trade.quantity
            )

            # Calculate R-multiple using net P&L for accuracy
            initial_risk = (trade.entry_price -
                            trade.stop_loss) * trade.quantity
            r_multiple = net_pnl / initial_risk if initial_risk > 0 else 0

            # Update trade
            trade.exit_date = datetime.now()
            trade.exit_price = exit_price
            trade.exit_reason = exit_reason
            trade.gross_profit_loss = round(gross_pnl, 2)
            trade.profit_loss = net_pnl
            trade.brokerage_charges = charges
            trade.profit_loss_pct = round(profit_loss_pct, 4)
            trade.r_multiple = round(r_multiple, 4)
            trade.hold_duration_days = hold_duration
            trade.status = 'CLOSED'

            # Update portfolio — FIX: was using undefined 'profit_loss' variable
            # Now correctly uses net_pnl which is defined above
            portfolio = self.db.query(Portfolio).order_by(
                Portfolio.timestamp.desc()
            ).first()

            if portfolio:
                investment = trade.entry_price * trade.quantity

                new_portfolio = Portfolio(
                    total_capital=portfolio.total_capital + net_pnl,
                    deployed_capital=portfolio.deployed_capital - investment,
                    available_capital=portfolio.available_capital + investment + net_pnl,
                    unrealized_pnl=portfolio.unrealized_pnl,
                    realized_pnl=portfolio.realized_pnl + net_pnl,
                    open_positions=max(0, portfolio.open_positions - 1),
                    timestamp=datetime.now()
                )
                self.db.add(new_portfolio)

            self.db.commit()

            logger.info(
                f"Trade exited: {trade.symbol} @ ₹{exit_price} "
                f"| Gross: ₹{gross_pnl:.2f} | Charges: ₹{charges:.2f} | Net: ₹{net_pnl:.2f}")
            return True

        except Exception as e:
            logger.error(f"Error exiting trade: {e}")
            self.db.rollback()
            return False

    def get_open_trades(self) -> list:
        """Get all open trades"""
        try:
            return self.db.query(Trade).filter(Trade.status == 'OPEN').all()
        except Exception as e:
            logger.error(f"Error getting open trades: {e}")
            return []

    def get_trade_history(self, limit: int = 50) -> list:
        """Get trade history"""
        try:
            return self.db.query(Trade).order_by(
                Trade.entry_date.desc()
            ).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting trade history: {e}")
            return []

    def update_unrealized_pnl(self, current_prices: dict):
        """
        Update unrealized P&L for open positions

        Args:
            current_prices: Dict mapping symbol to current price
        """
        try:
            open_trades = self.get_open_trades()
            total_unrealized = 0

            for trade in open_trades:
                price = current_prices.get(trade.symbol)
                if price:
                    unrealized = (price - trade.entry_price) * trade.quantity
                    total_unrealized += unrealized

            # Update portfolio
            portfolio = self.db.query(Portfolio).order_by(
                Portfolio.timestamp.desc()
            ).first()

            if portfolio:
                portfolio.unrealized_pnl = total_unrealized
                self.db.commit()

        except Exception as e:
            logger.error(f"Error updating unrealized P&L: {e}")
