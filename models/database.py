"""
Database models for AI Trading Bot
Using SQLAlchemy ORM with PostgreSQL
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import json

Base = declarative_base()


class Trade(Base):
    """Individual trade record"""
    __tablename__ = 'trades'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)

    # Entry details
    entry_date = Column(DateTime, nullable=False,
                        default=datetime.now, index=True)
    entry_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_score = Column(Integer)  # Setup quality score (0-100)

    # Risk management
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
            'stop_loss': self.stop_loss,
            'target': self.target,
            'target_2': self.target_2,       # NEW
            'target_3': self.target_3,       # NEW
            'partially_exited': self.partially_exited,   # NEW
            'partial_exit_price': self.partial_exit_price,  # NEW
            'partial_exit_qty': self.partial_exit_qty,      # NEW
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
            'hold_duration_days': self.hold_duration_days
        }


class Portfolio(Base):
    """Portfolio snapshot at each point in time"""
    __tablename__ = 'portfolio'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)

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

    last_updated = Column(DateTime, default=datetime.now)

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

    created_at = Column(DateTime, default=datetime.now)

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
    created_at = Column(DateTime, default=datetime.now)

    accuracy = Column(Float, nullable=True)

    def __repr__(self):
        return f"<MLModel {self.model_name} - {'Active' if self.is_active else 'Inactive'}>"


class EmailLog(Base):
    """Track sent emails"""
    __tablename__ = 'email_log'

    id = Column(Integer, primary_key=True)
    email_type = Column(String(50), nullable=False)  # ENTRY, EXIT, SUMMARY
    trade_id = Column(Integer, nullable=True)

    sent_at = Column(DateTime, default=datetime.now)
    subject = Column(Text)
    status = Column(String(20), default='SENT')  # SENT, FAILED

    def __repr__(self):
        return f"<Email {self.email_type} @ {self.sent_at}>"


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

    _engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(_engine)

    _SessionLocal = sessionmaker(bind=_engine)

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
            ('target_2', 'FLOAT'),               # NEW — stretch target
            ('target_3', 'FLOAT'),               # NEW — aggressive target
            ('partially_exited', 'BOOLEAN'),     # NEW — partial exit flag
            ('partial_exit_price', 'FLOAT'),     # NEW — price at partial exit
            ('partial_exit_qty', 'INTEGER'),     # NEW — qty exited at T1
            ('partial_exit_date', 'TIMESTAMP'),  # NEW — when partial exit happened
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
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"[Migration] Schema migration warning (safe to ignore if Postgres handles it): {e}"
        )


def get_session():
    """Get a new database session"""
    global _SessionLocal
    if _SessionLocal is None:
        init_database()
    return _SessionLocal()


def get_engine():
    """Get the database engine"""
    global _engine
    if _engine is None:
        init_database()
    return _engine
