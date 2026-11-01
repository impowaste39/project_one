"""
Database models for AI Trading Bot
Using SQLAlchemy ORM with PostgreSQL
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from datetime import datetime
import pytz
import os
import json

IST = pytz.timezone('Asia/Kolkata')

def _ist_now():
    return datetime.now(IST).replace(tzinfo=None)

Base = declarative_base()


class Trade(Base):
    """Individual trade record"""
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)

    # Entry details
    entry_date = Column(DateTime, nullable=False,
                        default=_ist_now, index=True)
    entry_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_score = Column(Integer)  # Setup quality score (0-100)

    # Risk management
    initial_stop_loss = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=False)
    target = Column(Float, nullable=False)       # Target 1 (primary)
    target_2 = Column(Float, nullable=True)      # Target 2 (stretch) — NEW
    target_3 = Column(Float, nullable=True)      # Target 3 (aggressive) — NEW

    # Partial exit tracking — NEW
    partially_exited = Column(Boolean, default=False, nullable=True)
    partial_exit_price = Column(Float, nullable=True)
    partial_exit_qty = Column(Integer, nullable=True)
    partial_exit_date = Column(DateTime, nullable=True)

    # Exit details
    exit_date = Column(DateTime, nullable=True)
    exit_price = Column(Float, nullable=True)
    exit_reason = Column(Text, nullable=True)

    # Results
    profit_loss = Column(Float, nullable=True)        # Net P&L after charges
    gross_profit_loss = Column(Float, nullable=True)  # Raw P&L before charges
    brokerage_charges = Column(Float, nullable=True)  # Total charges paid
    profit_loss_pct = Column(Float, nullable=True)
    r_multiple = Column(Float, nullable=True)         # Profit/Loss in R units

    # Status
    status = Column(String(20), nullable=False,
                    default='OPEN', index=True)  # OPEN, CLOSED

    # Analysis
    pattern = Column(String(100), nullable=True)
    confidence_factors = Column(Text, nullable=True)   # JSON string
    market_context = Column(Text, nullable=True)       # JSON string

    # Timing
    hold_duration_days = Column(Integer, nullable=True)

    # ML Features
    rsi = Column(Float, nullable=True)
    macd = Column(Float, nullable=True)
    volume_ratio = Column(Float, nullable=True)
    atr = Column(Float, nullable=True)
    pattern_count = Column(Integer, nullable=True)

    # Execution tracking (WP3) — nullable, populated offline/by owner
    alert_price = Column(Float, nullable=True)   # price at alert time
    fill_price = Column(Float, nullable=True)    # price owner actually filled at
    slippage_pct = Column(Float, nullable=True)  # (fill - alert) / alert * 100
    mae_pct = Column(Float, nullable=True)       # max adverse excursion %
    mfe_pct = Column(Float, nullable=True)       # max favorable excursion %

    def __repr__(self):
        return f"<Trade {self.symbol} @ ₹{self.entry_price} - {self.status}>"

    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'entry_date': self.entry_date.isoformat() if self.entry_date else None,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'entry_score': self.entry_score,
            'initial_stop_loss': self.initial_stop_loss,
            'stop_loss': self.stop_loss,
            'target': self.target,
            'target_2': self.target_2,
            'target_3': self.target_3,
            'partially_exited': self.partially_exited,
            'partial_exit_price': self.partial_exit_price,
            'partial_exit_qty': self.partial_exit_qty,
            'exit_date': self.exit_date.isoformat() if self.exit_date else None,
            'exit_price': self.exit_price,
            'exit_reason': self.exit_reason,
            'profit_loss': self.profit_loss,
            'gross_profit_loss': self.gross_profit_loss,
            'brokerage_charges': self.brokerage_charges,
            'profit_loss_pct': self.profit_loss_pct,
            'r_multiple': self.r_multiple,
            'status': self.status,
            'pattern': self.pattern,
            'hold_duration_days': self.hold_duration_days,
            'rsi': self.rsi,
            'macd': self.macd,
            'volume_ratio': self.volume_ratio,
            'atr': self.atr,
            'pattern_count': self.pattern_count,
            'alert_price': self.alert_price,
            'fill_price': self.fill_price,
            'slippage_pct': self.slippage_pct,
            'mae_pct': self.mae_pct,
            'mfe_pct': self.mfe_pct,
        }


class Portfolio(Base):
    """Portfolio snapshot at each point in time"""
    __tablename__ = 'portfolio'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=_ist_now, index=True)

    total_capital = Column(Float, nullable=False)
    deployed_capital = Column(Float, nullable=False)
    available_capital = Column(Float, nullable=False)

    unrealized_pnl = Column(Float, default=0)
    realized_pnl = Column(Float, default=0)
    total_return_pct = Column(Float, default=0)

    open_positions = Column(Integer, default=0)

    def __repr__(self):
        return f"<Portfolio ₹{self.total_capital} - {self.timestamp}>"

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'total_capital': self.total_capital,
            'deployed_capital': self.deployed_capital,
            'available_capital': self.available_capital,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'total_return_pct': self.total_return_pct,
            'open_positions': self.open_positions
        }


class LearningMetrics(Base):
    """Pattern and strategy performance metrics"""
    __tablename__ = 'learning_metrics'

    id = Column(Integer, primary_key=True)
    pattern = Column(String(100), nullable=False, unique=True, index=True)

    total_trades = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)

    win_rate = Column(Float, default=0)
    avg_win_pct = Column(Float, default=0)
    avg_loss_pct = Column(Float, default=0)
    avg_hold_days = Column(Float, default=0)

    expectancy = Column(Float, default=0)  # Expected return per trade

    last_updated = Column(DateTime, default=_ist_now)

    def __repr__(self):
        return f"<Metrics {self.pattern}: {self.win_rate:.1f}% WR>"


class MarketDataCache(Base):
    """Cache market data to reduce API calls"""
    __tablename__ = 'market_data_cache'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)

    indicators = Column(Text, nullable=True)  # JSON string

    created_at = Column(DateTime, default=_ist_now)

    def __repr__(self):
        return f"<MarketData {self.symbol} @ {self.timestamp}>"


class MLModel(Base):
    """Store trained ML models"""
    __tablename__ = 'ml_models'

    id = Column(Integer, primary_key=True)
    model_name = Column(String(100), nullable=False)
    model_data = Column(LargeBinary, nullable=False)   # Pickled model
    scaler_data = Column(LargeBinary, nullable=True)   # Pickled scaler

    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_ist_now)

    accuracy = Column(Float, nullable=True)

    def __repr__(self):
        return f"<MLModel {self.model_name} - {'Active' if self.is_active else 'Inactive'}>"


class EmailLog(Base):
    """Track sent emails"""
    __tablename__ = 'email_log'

    id = Column(Integer, primary_key=True)
    email_type = Column(String(50), nullable=False)  # ENTRY, EXIT, SUMMARY
    trade_id = Column(Integer, nullable=True)

    sent_at = Column(DateTime, default=_ist_now)
    subject = Column(Text)
    status = Column(String(20), default='SENT')  # SENT, FAILED

    def __repr__(self):
        return f"<Email {self.email_type} @ {self.sent_at}>"


class SignalLabel(Base):
    """Labeled outcome for a scan signal — foundation for ML training and backtesting.

    One row per scan_result_id (unique). Populated offline by scripts/label_outcomes.py,
    never on Render.
    """
    __tablename__ = 'signal_labels'

    id = Column(Integer, primary_key=True)
    scan_result_id = Column(Integer, nullable=False, unique=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    signal_date = Column(DateTime, nullable=False, index=True)  # naive IST
    entry_price = Column(Float, nullable=False)
    stop_price = Column(Float, nullable=False)
    target1_price = Column(Float, nullable=False)

    outcome = Column(String(12), nullable=False, index=True)  # TARGET | STOP | TIMEOUT | NO_DATA
    days_to_outcome = Column(Integer, nullable=False)
    r_gross = Column(Float, nullable=False)      # (exit - entry) / (entry - stop)
    r_net = Column(Float, nullable=False)        # r_gross minus charges for notional
    mfe_r = Column(Float, nullable=False)        # max favorable excursion in R
    mae_r = Column(Float, nullable=False)        # max adverse excursion in R
    path_json = Column(Text, nullable=True)      # up to 15 daily [high_r, low_r, close_r]
    labeled_at = Column(DateTime, nullable=False, default=_ist_now)  # naive IST

    def __repr__(self):
        return f"<SignalLabel {self.symbol} {self.outcome} R={self.r_net:.2f}>"

    def to_dict(self):
        return {
            'id': self.id,
            'scan_result_id': self.scan_result_id,
            'symbol': self.symbol,
            'signal_date': self.signal_date.isoformat() if self.signal_date else None,
            'entry_price': self.entry_price,
            'stop_price': self.stop_price,
            'target1_price': self.target1_price,
            'outcome': self.outcome,
            'days_to_outcome': self.days_to_outcome,
            'r_gross': self.r_gross,
            'r_net': self.r_net,
            'mfe_r': self.mfe_r,
            'mae_r': self.mae_r,
            'path_json': self.path_json,
            'labeled_at': self.labeled_at.isoformat() if self.labeled_at else None,
        }


class DailyWatchlist(Base):
    """Daily dynamic watchlist — symbols selected during pre-market scan.

    Populated at 8:45 AM IST by premarket_scan_job. Used by scan_market_job
    during market hours instead of the fixed custom watchlist.
    """
    __tablename__ = 'daily_watchlist'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    rank_score = Column(Float, nullable=False)
    rs_score = Column(Float, nullable=True)
    proximity = Column(Float, nullable=True)
    vol_ratio = Column(Float, nullable=True)
    scan_date = Column(DateTime, nullable=False, index=True)  # naive IST date
    created_at = Column(DateTime, nullable=False, default=_ist_now)  # naive IST

    def __repr__(self):
        return f"<DailyWatchlist {self.symbol} score={self.rank_score:.1f}>"

    def to_dict(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'rank_score': self.rank_score,
            'rs_score': self.rs_score,
            'proximity': self.proximity,
            'vol_ratio': self.vol_ratio,
            'scan_date': self.scan_date.isoformat() if self.scan_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# Database initialization
_engine = None
_SessionLocal = None


def init_database():
    """Initialize database connection and create tables"""
    global _engine, _SessionLocal

    try:
        from models.scan_report import ScanReport, ScanResult, PatternOccurrence
    except ImportError:
        pass

    database_url = os.getenv('DATABASE_URL', 'sqlite:///trading_bot.db')

    # Fix for Render PostgreSQL URL format - use psycopg (v3) driver
    if database_url.startswith('postgres://'):
        database_url = database_url.replace(
            'postgres://', 'postgresql+psycopg://', 1)
    elif database_url.startswith('postgresql://') and '+' not in database_url:
        database_url = database_url.replace(
            'postgresql://', 'postgresql+psycopg://', 1)

    connect_args = {}
    if database_url.startswith('postgres') or database_url.startswith('postgresql'):
        connect_args = {
            "connect_timeout": 15,
            "keepalives": 1,
            "keepalives_idle": 20,   # send keepalive after 20s idle (was 30)
            "keepalives_interval": 5,
            "keepalives_count": 3
        }

    _engine = create_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=25,    # recycle before Aiven drops idle TCP ~30s (was 120)
        pool_timeout=15,
        pool_size=5,        # steady-state — real Aiven limit is 20, confirmed via console
        max_overflow=3,     # burst ceiling 8 total — comfortable headroom under 20
        connect_args=connect_args
    )
    Base.metadata.create_all(_engine)

    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)

    # Run migrations to add new columns to existing databases
    _migrate_database(_engine)

    return _engine, _SessionLocal


def _migrate_database(engine):
    """
    Idempotent schema migrations.
    Safely adds missing columns on every startup.
    """
    from sqlalchemy import text, inspect as sa_inspect
    try:
        insp = sa_inspect(engine)
        existing_cols = {c['name'] for c in insp.get_columns('trades')}

        # All new columns with their types
        new_columns = [
            ('gross_profit_loss', 'FLOAT'),
            ('brokerage_charges', 'FLOAT'),
            ('initial_stop_loss', 'FLOAT'),
            ('target_2', 'FLOAT'),
            ('target_3', 'FLOAT'),
            ('partially_exited', 'BOOLEAN'),
            ('partial_exit_price', 'FLOAT'),
            ('partial_exit_qty', 'INTEGER'),
            ('partial_exit_date', 'TIMESTAMP'),
            ('rsi', 'FLOAT'),
            ('macd', 'FLOAT'),
            ('volume_ratio', 'FLOAT'),
            ('atr', 'FLOAT'),
            ('pattern_count', 'INTEGER'),
            ('alert_price', 'FLOAT'),
            ('fill_price', 'FLOAT'),
            ('slippage_pct', 'FLOAT'),
            ('mae_pct', 'FLOAT'),
            ('mfe_pct', 'FLOAT'),
        ]

        with engine.connect() as conn:
            for col_name, col_type in new_columns:
                if col_name not in existing_cols:
                    conn.execute(
                        text(
                            f'ALTER TABLE trades ADD COLUMN {col_name} {col_type}')
                    )
                    conn.commit()
                    import logging
                    logging.getLogger(__name__).info(
                        f"[Migration] Added column trades.{col_name}"
                    )

        # Create daily_watchlist table if not exists
        existing_tables = {t['name'] for t in insp.get_table_names()}
        if 'daily_watchlist' not in existing_tables:
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS daily_watchlist (
                        id SERIAL PRIMARY KEY,
                        symbol VARCHAR(20) NOT NULL,
                        rank_score FLOAT NOT NULL,
                        rs_score FLOAT,
                        proximity FLOAT,
                        vol_ratio FLOAT,
                        scan_date TIMESTAMP NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_daily_watchlist_symbol
                    ON daily_watchlist (symbol)
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_daily_watchlist_scan_date
                    ON daily_watchlist (scan_date)
                """))
                conn.commit()
                import logging
                logging.getLogger(__name__).info(
                    "[Migration] Created table daily_watchlist"
                )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"[Migration] Schema migration warning (safe to ignore if Postgres handles it): {e}"
        )


@contextmanager
def get_session():
    """
    FIX #5: Context-manager session — always commits or rolls back, always closes.

    Usage:
        with get_session() as session:
            session.query(Trade).filter_by(status='OPEN').all()

    The connection is returned to the pool the moment the `with` block exits,
    keeping live connections well under Aiven's 5-connection limit.
    """
    global _SessionLocal
    if _SessionLocal is None:
        init_database()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_engine():
    """Get the database engine"""
    global _engine
    if _engine is None:
        init_database()
    return _engine
