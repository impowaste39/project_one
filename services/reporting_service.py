"""
Reporting Service
Handles scan data persistence and retrieval for analysis
"""

import logging
from datetime import datetime, timedelta
import json
import os
import pytz

from models.database import MarketDataCache
from models.scan_report import ScanReport, ScanResult, PatternOccurrence

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')


class ReportingService:
    """Service for saving and retrieving scan data"""

    def __init__(self, db_session=None):
        if db_session is None:
            raise ValueError("ReportingService requires a db_session")
        self.db = db_session
        self.save_enabled = os.getenv(
            'SAVE_SCAN_DATA', 'true').lower() == 'true'
        self.retention_days = int(os.getenv('SCAN_DATA_RETENTION_DAYS', 90))
        self.cache_retention_days = int(os.getenv('MARKET_CACHE_RETENTION_DAYS', 2))

        self.min_score_to_save = int(os.getenv('MIN_SCORE_TO_SAVE', 50))

    def save_scan_report(self, market_context: dict, scan_stats: dict,
                         scan_duration: float) -> ScanReport:
        """
        Save overall scan session metadata

        Args:
            market_context: Market trend and context data
            scan_stats: Statistics about the scan (stocks scanned, opportunities found, etc.)
            scan_duration: How long the scan took in seconds

        Returns:
            ScanReport object
        """
        if not self.save_enabled:
            return None

        try:
            scan_report = ScanReport(
                timestamp=datetime.now(IST).replace(tzinfo=None),
                market_trend=market_context.get('trend'),
                market_strength=market_context.get('strength'),
                nifty_price=market_context.get('nifty_price'),
                nifty_rsi=market_context.get('nifty_rsi'),
                market_breadth=market_context.get('market_breadth'),
                total_stocks_scanned=scan_stats.get('total_scanned', 0),
                opportunities_found=scan_stats.get(
                    'opportunities_found', 0),
                trades_entered=scan_stats.get('trades_entered', 0),
                scan_duration_seconds=scan_duration
            )

            self.db.add(scan_report)
            self.db.commit()
            self.db.refresh(scan_report)

            logger.info(f"Saved scan report: {scan_report.id}")
            return scan_report

        except Exception as e:
            logger.error(f"Error saving scan report: {e}")
            self.db.rollback()
            return None

    def save_scan_result(self, scan_report_id: int, analysis: dict,
                         evaluation: dict) -> ScanResult:
        """
        Save individual stock analysis result

        Only saves stocks scoring >= MIN_SCORE_TO_SAVE (default: 50)
        to reduce database usage while maintaining learning capabilities.

        Args:
            scan_report_id: ID of parent scan report
            analysis: Stock analysis data from market monitor
            evaluation: Evaluation result from trading brain

        Returns:
            ScanResult object or None if filtered out
        """
        if not self.save_enabled or not scan_report_id:
            return None

        # Filter by score - only save meaningful opportunities (storage optimization)
        score = evaluation.get('score', 0)
        if score < self.min_score_to_save:
            # Skip low-scoring stocks to save database space
            # Still track patterns separately via _save_pattern_occurrences
            return None

        try:
            scan_result = ScanResult(
                scan_report_id=scan_report_id,
                symbol=analysis.get('symbol'),
                current_price=analysis.get('current_price'),
                rsi=analysis.get('rsi'),
                macd=analysis.get('macd'),
                volume_ratio=analysis.get('volume_ratio'),
                atr=analysis.get('atr'),
                patterns_detected=json.dumps(analysis.get('patterns', [])),
                pattern_count=analysis.get('pattern_count', 0),
                total_score=evaluation.get('score'),
                technical_score=evaluation.get('technical_score'),
                pattern_score=evaluation.get('pattern_score'),
                market_score=evaluation.get('market_score'),
                ml_score=evaluation.get('ml_score'),
                decision=evaluation.get('decision'),
                rejection_reason=evaluation.get('reason'),
                entry_price=evaluation.get('entry_price'),
                stop_loss=evaluation.get('stop_loss'),
                target=evaluation.get('target_1'),
                rr_ratio=evaluation.get('rr_ratio')
            )

            self.db.add(scan_result)
            self.db.commit()

            # Note: Pattern occurrences are saved separately in app.py
            # to ensure they're tracked even for low-scoring stocks

            return scan_result

        except Exception as e:
            logger.error(
                f"Error saving scan result for {analysis.get('symbol')}: {e}")
            self.db.rollback()
            return None

    def _save_pattern_occurrences(self, analysis: dict, evaluation: dict,
                                  scan_report_id: int):
        """Save pattern occurrence records"""
        try:
            patterns = analysis.get('patterns', [])
            if not patterns:
                return

            # Get market context from scan report
            scan_report = self.db.query(ScanReport).filter_by(
                id=scan_report_id).first()

            if not scan_report:
                return

            for pattern in patterns:
                occurrence = PatternOccurrence(
                    timestamp=datetime.now(IST).replace(tzinfo=None),
                    pattern=pattern,
                    symbol=analysis.get('symbol'),
                    market_trend=scan_report.market_trend,
                    nifty_rsi=scan_report.nifty_rsi,
                    was_traded=(evaluation.get('decision') == 'ENTER'),
                    score=evaluation.get('score')
                )
                self.db.add(occurrence)
            self.db.commit()

        except Exception as e:
            logger.error(f"Error saving pattern occurrences: {e}")
            self.db.rollback()
            return None

    def get_scan_history(self, limit: int = 50) -> list:
        """
        Get recent scan reports

        Args:
            limit: Number of reports to retrieve

        Returns:
            List of ScanReport objects
        """
        try:
            scans = self.db.query(ScanReport).order_by(
                ScanReport.timestamp.desc()
            ).limit(limit).all()

            return [scan.to_dict() for scan in scans]

        except Exception as e:
            logger.error(f"Error retrieving scan history: {e}")
            return []

    def get_scan_details(self, scan_id: int) -> dict:
        """
        Get detailed results for a specific scan

        Args:
            scan_id: Scan report ID

        Returns:
            Dict with scan report and all results
        """
        try:
            scan = self.db.query(ScanReport).filter_by(id=scan_id).first()

            if not scan:
                return None

            results = self.db.query(ScanResult).filter_by(
                scan_report_id=scan_id
            ).all()

            return {
                'scan': scan.to_dict(),
                'results': [r.to_dict() for r in results]
            }

        except Exception as e:
            logger.error(f"Error retrieving scan details: {e}")
            return None

    def get_pattern_statistics(self, days: int = 30) -> dict:
        """
        Get pattern performance statistics

        Args:
            days: Number of days to analyze

        Returns:
            Dict with pattern statistics
        """
        try:
            cutoff_date = datetime.now(IST).replace(tzinfo=None) - timedelta(days=days)

            occurrences = self.db.query(PatternOccurrence).filter(
                PatternOccurrence.timestamp >= cutoff_date
            ).all()

            pattern_stats = {}

            for occ in occurrences:
                if occ.pattern not in pattern_stats:
                    pattern_stats[occ.pattern] = {
                        'total_occurrences': 0,
                        'traded': 0,
                        'avg_score': 0,
                        'scores': []
                    }

                stats = pattern_stats[occ.pattern]
                stats['total_occurrences'] += 1
                if occ.was_traded:
                    stats['traded'] += 1
                if occ.score:
                    stats['scores'].append(occ.score)

            # Calculate averages
            for pattern, stats in pattern_stats.items():
                if stats['scores']:
                    stats['avg_score'] = sum(
                        stats['scores']) / len(stats['scores'])
                stats['trade_rate'] = (
                    stats['traded'] / stats['total_occurrences'] * 100) if stats['total_occurrences'] > 0 else 0
                del stats['scores']  # Remove raw scores from output

            return pattern_stats

        except Exception as e:
            logger.error(f"Error calculating pattern statistics: {e}")
            return {}

    def get_rejection_analysis(self, days: int = 7) -> dict:
        """
        Analyze why opportunities are being rejected

        Args:
            days: Number of days to analyze

        Returns:
            Dict with rejection reason breakdown
        """
        try:
            cutoff_date = datetime.now(IST).replace(tzinfo=None) - timedelta(days=days)

            results = self.db.query(ScanResult).join(ScanReport).filter(
                ScanReport.timestamp >= cutoff_date,
                ScanResult.decision == 'PASS'
            ).all()

            rejection_reasons = {}
            score_distribution = []

            for result in results:
                reason = result.rejection_reason or 'Unknown'
                rejection_reasons[reason] = rejection_reasons.get(
                    reason, 0) + 1
                if result.total_score:
                    score_distribution.append(result.total_score)

            avg_rejected_score = sum(
                score_distribution) / len(score_distribution) if score_distribution else 0

            return {
                'total_rejected': len(results),
                'rejection_reasons': rejection_reasons,
                'avg_score_of_rejected': round(avg_rejected_score, 2),
                'score_distribution': {
                    'min': min(score_distribution) if score_distribution else 0,
                    'max': max(score_distribution) if score_distribution else 0,
                    'avg': round(avg_rejected_score, 2)
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing rejections: {e}")
            return {}

    def cleanup_old_data(self):
        """Remove scan data older than retention period"""
        try:
            cutoff_date = datetime.now(IST).replace(tzinfo=None) - timedelta(days=self.retention_days)
            cache_cutoff_date = datetime.now(IST).replace(tzinfo=None) - timedelta(days=self.cache_retention_days)

            # Delete child scan_results first (bulk delete() does NOT cascade)
            old_reports_subq = self.db.query(ScanReport.id).filter(
                ScanReport.timestamp < cutoff_date
            ).subquery()

            self.db.query(ScanResult).filter(
                ScanResult.scan_report_id.in_(old_reports_subq)
            ).delete(synchronize_session=False)

            deleted = self.db.query(ScanReport).filter(
                ScanReport.timestamp < cutoff_date
            ).delete(synchronize_session=False)

            # Delete old pattern occurrences
            self.db.query(PatternOccurrence).filter(
                PatternOccurrence.timestamp < cutoff_date
            ).delete(synchronize_session=False)

            # Delete old market data cache
            self.db.query(MarketDataCache).filter(
                MarketDataCache.timestamp < cache_cutoff_date
            ).delete(synchronize_session=False)

            self.db.commit()

            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old scan reports")

        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            self.db.rollback()
