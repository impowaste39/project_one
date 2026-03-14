"""
Portfolio Manager
Handles trade execution and portfolio management

Improvements in this version:
- Sector correlation guard: max 2 open positions from the same sector
- Weekly loss circuit breaker: stops new entries if week loss exceeds 3% of capital
"""

import logging
import os
from datetime import datetime, timedelta
import json
import pytz

from models.database import Trade, Portfolio, get_session

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')

# =========================================================================
# SECTOR MAP
# Maps each watchlist stock to its sector.
# Used by sector correlation guard — max 2 open positions per sector.
#
# Why this matters:
# If NTPC and NHPC are already open (both 'power') and SJVN shows a great
# setup, we skip it. If Nifty Power index crashes on bad news, you're only
# hit twice — not three times. One news event can't wipe multiple positions.
#
# Stocks not in this map are treated as 'unknown' — no cap applied for them.
# =========================================================================
SECTOR_MAP = {
    # BANKING
    'YESBANK.NS':    'banking',
    'PNB.NS':        'banking',
    'BANKBARODA.NS': 'banking',
    'FEDERALBNK.NS': 'banking',
    'IDFCFIRSTB.NS': 'banking',
    'SBIN.NS':       'banking',
    'UCOBANK.NS':    'banking',
    'CENTRALBK.NS':  'banking',
    'HDFCBANK.NS':   'banking',
    'ICICIBANK.NS':  'banking',
    'KOTAKBANK.NS':  'banking',
    'AXISBANK.NS':   'banking',
    'INDUSINDBK.NS': 'banking',

    # FINANCE / NBFC
    'IRFC.NS':       'finance',
    'RECLTD.NS':     'finance',
    'PFC.NS':        'finance',
    'MANAPPURAM.NS': 'finance',
    'LTF.NS':        'finance',
    'CHOLAFIN.NS':   'finance',
    'BAJFINANCE.NS': 'finance',
    'BAJAJFINSV.NS': 'finance',
    'MUTHOOTFIN.NS': 'finance',
    'SHRIRAMFIN.NS': 'finance',

    # POWER
    'SUZLON.NS':     'power',
    'SJVN.NS':       'power',
    'NTPC.NS':       'power',
    'TATAPOWER.NS':  'power',
    'ADANIPOWER.NS': 'power',
    'NHPC.NS':       'power',
    'IEX.NS':        'power',
    'PTC.NS':        'power',
    'POWERGRID.NS':  'power',

    # OIL & GAS
    'ONGC.NS':       'oil_gas',
    'IOC.NS':        'oil_gas',
    'GAIL.NS':       'oil_gas',
    'BPCL.NS':       'oil_gas',
    'RELIANCE.NS':   'oil_gas',

    # METALS
    'SAIL.NS':       'metals',
    'NMDC.NS':       'metals',
    'NATIONALUM.NS': 'metals',
    'VEDL.NS':       'metals',
    'HINDZINC.NS':   'metals',
    'TATASTEEL.NS':  'metals',
    'JINDALSTEL.NS': 'metals',
    'JSWSTEEL.NS':   'metals',
    'HINDALCO.NS':   'metals',

    # IT
    'WIPRO.NS':      'it',
    'ROUTE.NS':      'it',
    'REDINGTON.NS':  'it',
    'TCS.NS':        'it',
    'INFY.NS':       'it',
    'HCLTECH.NS':    'it',
    'TECHM.NS':      'it',

    # AUTO
    'ASHOKLEY.NS':   'auto',
    'MOTHERSON.NS':  'auto',
    'MARUTI.NS':     'auto',
    'TATAMOTORS.NS': 'auto',
    'BAJAJ-AUTO.NS': 'auto',
    'HEROMOTOCO.NS': 'auto',
    'EICHERMOT.NS':  'auto',

    # CONSUMER / FMCG
    'ITC.NS':        'consumer',
    'NYKAA.NS':      'consumer',
    'EMAMILTD.NS':   'consumer',
    'DABUR.NS':      'consumer',
    'HINDUNILVR.NS': 'consumer',
    'MARICO.NS':     'consumer',
    'BRITANNIA.NS':  'consumer',
    'NESTLEIND.NS':  'consumer',

    # PHARMA
    'BIOCON.NS':     'pharma',
    'AUROPHARMA.NS': 'pharma',
    'GLENMARK.NS':   'pharma',
    'ZYDUSLIFE.NS':  'pharma',
    'SUNPHARMA.NS':  'pharma',
    'CIPLA.NS':      'pharma',
    'DRREDDY.NS':    'pharma',
    'DIVISLAB.NS':   'pharma',

    # INFRA / PSU
    'RVNL.NS':       'infra',
    'NBCC.NS':       'infra',
    'RITES.NS':      'infra',
    'SCI.NS':        'infra',
    'LT.NS':         'infra',
    'ADANIPORTS.NS': 'infra',

    # MID & SMALL
    'BALRAMCHIN.NS': 'midsmall',
    'CASTROLIND.NS': 'midsmall',
    'GRAPHITE.NS':   'midsmall',
}

MAX_POSITIONS_PER_SECTOR = 2


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

    # =========================================================================
    # NEW: SECTOR CORRELATION GUARD
    # Looks up the sector for the incoming symbol and counts how many open
    # trades are already in that sector. Blocks entry if limit is reached.
    #
    # Returns (allowed: bool, reason: str)
    # On any error — allows the trade (guard failures don't block the bot).
    # =========================================================================
    def check_sector_correlation(self, symbol: str) -> tuple:
        """
        Check if adding this symbol would breach the sector concentration limit.

        Returns:
            (allowed: bool, reason: str)
            allowed=True  → sector has room, safe to enter
            allowed=False → sector is full, skip this trade
        """
        try:
            sector = SECTOR_MAP.get(symbol, 'unknown')

            if sector == 'unknown':
                return True, f"Sector unknown for {symbol} — no sector cap applied"

            open_trades = self.db.query(Trade).filter(
                Trade.status == 'OPEN'
            ).all()

            sector_symbols = [
                t.symbol for t in open_trades
                if SECTOR_MAP.get(t.symbol, 'unknown') == sector
            ]
            sector_count = len(sector_symbols)

            if sector_count >= MAX_POSITIONS_PER_SECTOR:
                existing = ', '.join(sector_symbols)
                reason = (
                    f"Sector '{sector}' already has {sector_count}/"
                    f"{MAX_POSITIONS_PER_SECTOR} positions ({existing}) "
                    f"— concentration limit reached"
                )
                logger.info(f"[SectorGuard] {symbol} BLOCKED — {reason}")
                return False, reason

            reason = (
                f"Sector '{sector}': {sector_count}/"
                f"{MAX_POSITIONS_PER_SECTOR} positions — OK"
            )
            logger.debug(f"[SectorGuard] {symbol} ALLOWED — {reason}")
            return True, reason

        except Exception as e:
            logger.error(
                f"[SectorGuard] Error checking sector for {symbol}: {e}")
            return True, f"Sector check error ({e}) — proceeding"

    # =========================================================================
    # NEW: WEEKLY LOSS CIRCUIT BREAKER
    # Sums all closed trade P&L since Monday 00:00 IST.
    # If the loss exceeds WEEKLY_LOSS_LIMIT_PCT (default 3%) of total capital,
    # new entries are blocked until the next Monday.
    #
    # Why 3%? At 1% risk per trade, 3% loss = 3 losing trades in a row.
    # That's a signal to pause, not keep firing. One bad week stays one bad week.
    #
    # Existing open positions continue to be monitored — they can still exit.
    # Only NEW entries are blocked.
    #
    # Configure via Render env var: WEEKLY_LOSS_LIMIT_PCT=3.0
    # =========================================================================
    def check_weekly_loss_circuit_breaker(self) -> tuple:
        """
        Check if weekly losses have exceeded the circuit breaker threshold.

        Returns:
            (allowed: bool, reason: str)
            allowed=True  → within weekly loss limit, safe to enter
            allowed=False → limit breached, no new entries until Monday
        """
        try:
            weekly_loss_limit_pct = float(
                os.getenv('WEEKLY_LOSS_LIMIT_PCT', '3.0'))

            # Monday 00:00 IST — start of current trading week
            now_ist = datetime.now(IST).replace(tzinfo=None)
            days_since_monday = now_ist.weekday()  # Monday=0
            week_start = now_ist.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=days_since_monday)

            week_trades = self.db.query(Trade).filter(
                Trade.status == 'CLOSED',
                Trade.exit_date >= week_start
            ).all()

            if not week_trades:
                return True, "No closed trades this week — circuit breaker inactive"

            week_pnl = sum(
                t.profit_loss for t in week_trades
                if t.profit_loss is not None
            )

            # Only trigger on net loss weeks
            if week_pnl >= 0:
                return (
                    True,
                    f"Week P&L: +₹{week_pnl:.2f} (profitable) — circuit breaker inactive"
                )

            portfolio = self.db.query(Portfolio).order_by(
                Portfolio.timestamp.desc()
            ).first()

            if not portfolio or portfolio.total_capital <= 0:
                return True, "Portfolio unavailable — circuit breaker bypassed"

            loss_pct = abs(week_pnl) / portfolio.total_capital * 100

            if loss_pct >= weekly_loss_limit_pct:
                reason = (
                    f"⚠️ Circuit breaker ACTIVE — week loss ₹{abs(week_pnl):.2f} "
                    f"({loss_pct:.1f}% of ₹{portfolio.total_capital:.0f}) "
                    f"exceeds {weekly_loss_limit_pct}% limit. "
                    f"No new entries until Monday."
                )
                logger.warning(f"[CircuitBreaker] {reason}")
                return False, reason

            remaining_pct = weekly_loss_limit_pct - loss_pct
            reason = (
                f"Week P&L: -₹{abs(week_pnl):.2f} ({loss_pct:.1f}% loss) — "
                f"{remaining_pct:.1f}% headroom before circuit breaker"
            )
            return True, reason

        except Exception as e:
            logger.error(
                f"[CircuitBreaker] Error checking weekly loss: {e}")
            return True, f"Circuit breaker check error ({e}) — proceeding"

    def enter_trade(self, evaluation: dict) -> bool:
        """
        Execute trade entry.
        Runs two guards before entering:
        1. Sector correlation guard (max 2 positions per sector)
        2. Weekly loss circuit breaker (stops if week loss > 3%)

        Args:
            evaluation: Trade evaluation from TradingBrain

        Returns:
            True if trade executed successfully
        """
        symbol = evaluation['symbol']

        # --- GUARD 1: SECTOR CORRELATION ---
        sector_allowed, sector_reason = self.check_sector_correlation(symbol)
        if not sector_allowed:
            logger.info(
                f"[SectorGuard] {symbol} entry blocked: {sector_reason}")
            return False

        # --- GUARD 2: WEEKLY LOSS CIRCUIT BREAKER ---
        circuit_allowed, circuit_reason = self.check_weekly_loss_circuit_breaker()
        if not circuit_allowed:
            logger.warning(
                f"[CircuitBreaker] {symbol} entry blocked: {circuit_reason}")
            return False

        try:
            trade = Trade(
                symbol=symbol,
                entry_date=datetime.now(),
                entry_price=evaluation['entry_price'],
                quantity=evaluation['quantity'],
                entry_score=evaluation['score'],
                stop_loss=evaluation['stop_loss'],
                target=evaluation['target_1'],
                target_2=evaluation.get('target_2'),
                target_3=evaluation.get('target_3'),
                partially_exited=False,
                status='OPEN',
                pattern=evaluation['patterns'][0] if evaluation.get(
                    'patterns') else None,
                confidence_factors=json.dumps(evaluation.get('factors', []))
            )

            self.db.add(trade)

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

            if self.email_service:
                self.email_service.send_trade_entry_email(trade, evaluation)

            sector = SECTOR_MAP.get(symbol, 'unknown')
            position_tier = evaluation.get('position_tier', 'NORMAL')
            logger.info(
                f"Trade entered: {symbol} @ ₹{trade.entry_price} "
                f"| Sector: {sector} | Tier: {position_tier} "
                f"| T1: ₹{trade.target} | T2: ₹{trade.target_2} | T3: ₹{trade.target_3}"
            )
            return True

        except Exception as e:
            logger.error(f"Error entering trade: {e}")
            self.db.rollback()
            return False

    def exit_trade(self, trade: Trade, exit_price: float, exit_reason: str) -> bool:
        """
        Execute trade exit.

        Args:
            trade: Trade object to exit
            exit_price: Exit price
            exit_reason: Reason for exit

        Returns:
            True if trade exited successfully
        """
        try:
            from core.trading_brain import TradingBrain

            gross_pnl = (exit_price - trade.entry_price) * trade.quantity
            profit_loss_pct = (
                (exit_price - trade.entry_price) / trade.entry_price) * 100
            hold_duration = (datetime.now() -
                             trade.entry_date).days if trade.entry_date else 0

            brain = TradingBrain()
            net_pnl, charges = brain.calculate_net_pnl(
                trade.entry_price, exit_price, trade.quantity
            )

            initial_risk = (trade.entry_price -
                            trade.stop_loss) * trade.quantity
            r_multiple = net_pnl / initial_risk if initial_risk > 0 else 0

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
                f"| Gross: ₹{gross_pnl:.2f} | Charges: ₹{charges:.2f} | Net: ₹{net_pnl:.2f}"
            )
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
        Update unrealized P&L for open positions.

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

            portfolio = self.db.query(Portfolio).order_by(
                Portfolio.timestamp.desc()
            ).first()

            if portfolio:
                portfolio.unrealized_pnl = total_unrealized
                self.db.commit()

        except Exception as e:
            logger.error(f"Error updating unrealized P&L: {e}")

    def get_weekly_pnl_summary(self) -> dict:
        """
        Get this week's P&L summary including circuit breaker status.
        Used by EOD Discord summary and /api/admin/system-status endpoint.
        """
        try:
            weekly_loss_limit_pct = float(
                os.getenv('WEEKLY_LOSS_LIMIT_PCT', '3.0'))

            now_ist = datetime.now(IST).replace(tzinfo=None)
            days_since_monday = now_ist.weekday()
            week_start = now_ist.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=days_since_monday)

            week_trades = self.db.query(Trade).filter(
                Trade.status == 'CLOSED',
                Trade.exit_date >= week_start
            ).all()

            week_pnl = sum(
                t.profit_loss for t in week_trades
                if t.profit_loss is not None
            )
            week_wins = sum(
                1 for t in week_trades
                if t.profit_loss and t.profit_loss > 0
            )
            week_losses = len(week_trades) - week_wins

            portfolio = self.db.query(Portfolio).order_by(
                Portfolio.timestamp.desc()
            ).first()
            total_capital = portfolio.total_capital if portfolio else 0

            loss_pct = (
                abs(week_pnl) / total_capital * 100
                if total_capital > 0 and week_pnl < 0
                else 0
            )
            circuit_active = loss_pct >= weekly_loss_limit_pct

            return {
                'week_pnl': round(week_pnl, 2),
                'week_trades': len(week_trades),
                'week_wins': week_wins,
                'week_losses': week_losses,
                'loss_pct_of_capital': round(loss_pct, 2),
                'circuit_breaker_limit_pct': weekly_loss_limit_pct,
                'circuit_breaker_active': circuit_active
            }

        except Exception as e:
            logger.error(f"Error getting weekly P&L summary: {e}")
            return {}