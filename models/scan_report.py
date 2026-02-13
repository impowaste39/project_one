"""
Scan Report Models
Track every market scan for analysis and learning
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import json

from models.database import Base


class ScanReport(Base):
    """Overall scan session metadata"""
    __tablename__ = 'scan_reports'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False,
                       default=datetime.now, index=True)

    # Market context at scan time
    market_trend = Column(String(20))  # bullish, bearish, sideways
    market_strength = Column(Float)
    nifty_price = Column(Float)
    nifty_rsi = Column(Float)
    market_breadth = Column(String(20))  # positive, negative

    # Scan statistics
    total_stocks_scanned = Column(Integer, default=0)
    opportunities_found = Column(Integer, default=0)
    trades_entered = Column(Integer, default=0)

    # Timing
    scan_duration_seconds = Column(Float)

    # Relationship to individual results
    results = relationship(
        "ScanResult", back_populates="scan_report", cascade="all, delete-orphan")

    def __repr__(self):
        return "<ScanReport {} - {} opps>".format(self.timestamp, self.opportunities_found)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'market_trend': self.market_trend,
            'market_strength': self.market_strength,
            'nifty_price': self.nifty_price,
            'total_stocks_scanned': self.total_stocks_scanned,
            'opportunities_found': self.opportunities_found,
            'trades_entered': self.trades_entered,
            'scan_duration_seconds': self.scan_duration_seconds
        }


class ScanResult(Base):
    """Individual stock analysis result from a scan"""
    __tablename__ = 'scan_results'

    id = Column(Integer, primary_key=True)
    scan_report_id = Column(Integer, ForeignKey(
        'scan_reports.id'), nullable=False, index=True)

    # Stock identification
    symbol = Column(String(20), nullable=False, index=True)
    current_price = Column(Float)

    # Technical indicators
    rsi = Column(Float)
    macd = Column(Float)
    volume_ratio = Column(Float)
    atr = Column(Float)

    # Pattern detection
    patterns_detected = Column(Text)  # JSON array of pattern names
    pattern_count = Column(Integer, default=0)

    # Scoring
    total_score = Column(Integer)
    technical_score = Column(Integer)
    pattern_score = Column(Integer)
    market_score = Column(Integer)
    ml_score = Column(Float)

    # Decision
    decision = Column(String(10))  # ENTER, PASS
    rejection_reason = Column(Text)

    # Entry levels (if calculated)
    entry_price = Column(Float)
    stop_loss = Column(Float)
    target = Column(Float)
    rr_ratio = Column(Float)

    # Relationship
    scan_report = relationship("ScanReport", back_populates="results")

    def __repr__(self):
        return "<ScanResult {} - Score: {} - {}>".format(self.symbol, self.total_score, self.decision)

    def to_dict(self):
        return {
            'id': self.id,
            'scan_report_id': self.scan_report_id,
            'symbol': self.symbol,
            'current_price': self.current_price,
            'rsi': self.rsi,
            'macd': self.macd,
            'volume_ratio': self.volume_ratio,
            'patterns_detected': json.loads(self.patterns_detected) if self.patterns_detected else [],
            'pattern_count': self.pattern_count,
            'total_score': self.total_score,
            'decision': self.decision,
            'rejection_reason': self.rejection_reason,
            'rr_ratio': self.rr_ratio
        }


class PatternOccurrence(Base):
    """Track when patterns appear and their context"""
    __tablename__ = 'pattern_occurrences'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False,
                       default=datetime.now, index=True)

    # Pattern info
    pattern = Column(String(100), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)

    # Market context when pattern appeared
    market_trend = Column(String(20))
    nifty_rsi = Column(Float)

    # Pattern outcome (if traded)
    was_traded = Column(Boolean, default=False)
    trade_id = Column(Integer, nullable=True)
    trade_outcome = Column(String(10))  # WIN, LOSS, OPEN

    # Pattern quality at detection
    score = Column(Integer)

    def __repr__(self):
        return "<PatternOccurrence {} on {}>".format(self.pattern, self.symbol)
