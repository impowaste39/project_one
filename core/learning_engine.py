"""
Learning Engine
Self-improvement through trade analysis and ML optimization
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from datetime import datetime, timedelta
import logging
import pickle
import pytz

from models.database import Trade, LearningMetrics, MLModel
from models.scan_report import PatternOccurrence, ScanResult, ScanReport

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')

class LearningEngine:
    """Self-improvement and trade analysis engine"""

    def __init__(self, db_session=None):
        self.db = db_session
        self.pattern_stats = {}
        if db_session:
            self.load_pattern_statistics()

    def load_pattern_statistics(self):
        """Load historical pattern performance from database"""
        try:
            metrics = self.db.query(LearningMetrics).all()

            for metric in metrics:
                self.pattern_stats[metric.pattern] = {
                    'total_trades': metric.total_trades,
                    'wins': metric.wins,
                    'losses': metric.losses,
                    'win_rate': metric.win_rate,
                    'avg_win_pct': metric.avg_win_pct,
                    'avg_loss_pct': metric.avg_loss_pct,
                    'expectancy': metric.expectancy
                }

            logger.info(
                f"Loaded statistics for {len(self.pattern_stats)} patterns")

        except Exception as e:
            logger.error(f"Error loading pattern statistics: {e}")

    def analyze_completed_trade(self, trade: Trade) -> dict:
        """
        Deep analysis of a completed trade

        Returns:
            Dict with insights and learning points
        """
        insights = []
        learning_points = []

        # Calculate metrics
        profit_pct = trade.profit_loss_pct or 0
        hold_duration = trade.hold_duration_days or 0
        r_multiple = trade.r_multiple or 0

        pattern = trade.pattern or 'unknown'

        if trade.profit_loss and trade.profit_loss > 0:
            # Winning trade analysis
            insights.append(f"✅ Profitable trade: +{profit_pct:.2f}%")
            insights.append(f"✅ Pattern '{pattern}' worked as expected")
            insights.append(f"✅ R-multiple: {r_multiple:.2f}R")

            learning_points.append(
                f"Pattern '{pattern}' continues to show edge")

            if hold_duration <= 5:
                learning_points.append(
                    "Quick profit realization - trend was strong")
        else:
            # Losing trade analysis
            insights.append(f"❌ Loss: {profit_pct:.2f}%")
            insights.append(f"❌ Pattern '{pattern}' failed this time")

            if r_multiple and abs(r_multiple) >= 1:
                learning_points.append("Full stop loss hit - respect the stop")
            else:
                learning_points.append("Exited early - review exit criteria")

            if hold_duration > 7:
                learning_points.append(
                    "Held too long - consider tighter time stops")

        # Update pattern statistics
        self.update_pattern_statistics(pattern, trade, profit_pct, r_multiple)

        return {
            'insights': insights,
            'learning_points': learning_points,
            'profit_pct': profit_pct,
            'hold_duration': hold_duration,
            'r_multiple': r_multiple,
            'pattern': pattern
        }

    def update_pattern_statistics(self, pattern: str, trade: Trade,
                                  profit_pct: float, r_multiple: float):
        """Update running statistics for a pattern"""
        if pattern not in self.pattern_stats:
            self.pattern_stats[pattern] = {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'avg_win_pct': 0,
                'avg_loss_pct': 0,
                'expectancy': 0
            }

        stats = self.pattern_stats[pattern]
        stats['total_trades'] += 1

        if trade.profit_loss and trade.profit_loss > 0:
            stats['wins'] += 1
            if stats['wins'] > 0:
                stats['avg_win_pct'] = (
                    (stats['avg_win_pct'] * (stats['wins'] - 1) +
                     profit_pct) / stats['wins']
                )
        else:
            stats['losses'] += 1
            if stats['losses'] > 0:
                stats['avg_loss_pct'] = (
                    (stats['avg_loss_pct'] * (stats['losses'] - 1) +
                     abs(profit_pct)) / stats['losses']
                )

        if stats['total_trades'] > 0:
            stats['win_rate'] = (stats['wins'] / stats['total_trades']) * 100

        # Calculate expectancy
        stats['expectancy'] = (
            (stats['win_rate'] / 100) * stats['avg_win_pct'] -
            ((100 - stats['win_rate']) / 100) * stats['avg_loss_pct']
        )

        # Save to database
        self.save_pattern_statistics(pattern, stats)

        logger.info(f"Updated stats for '{pattern}': "
                    f"{stats['total_trades']} trades, "
                    f"{stats['win_rate']:.1f}% win rate")

    def save_pattern_statistics(self, pattern: str, stats: dict):
        """Persist pattern statistics to database"""
        try:
            metric = self.db.query(LearningMetrics).filter_by(
                pattern=pattern).first()

            if metric:
                metric.total_trades = stats['total_trades']
                metric.wins = stats['wins']
                metric.losses = stats['losses']
                metric.win_rate = stats['win_rate']
                metric.avg_win_pct = stats['avg_win_pct']
                metric.avg_loss_pct = stats['avg_loss_pct']
                metric.expectancy = stats['expectancy']
                metric.last_updated = datetime.now(IST).replace(tzinfo=None)
            else:
                metric = LearningMetrics(
                    pattern=pattern,
                    total_trades=stats['total_trades'],
                    wins=stats['wins'],
                    losses=stats['losses'],
                    win_rate=stats['win_rate'],
                    avg_win_pct=stats['avg_win_pct'],
                    avg_loss_pct=stats['avg_loss_pct'],
                    expectancy=stats['expectancy'],
                    last_updated=datetime.now(IST).replace(tzinfo=None)
                )
                self.db.add(metric)

            self.db.commit()

        except Exception as e:
            logger.error(f"Error saving pattern statistics: {e}")
            self.db.rollback()

    def retrain_ml_model(self, trading_brain):
        """
        Retrain ML model with latest trade data.
        Requires minimum 20 closed trades (lowered from 50 for faster learning).
        """
        try:
            trades = self.db.query(Trade).filter(
                Trade.status == 'CLOSED').all()

            # Lowered from 50 → 20 so ML starts learning sooner
            if len(trades) < 20:
                logger.info(
                    f"Not enough trades for retraining ({len(trades)}/20 required)")
                return False

            # Prepare training data
            X = []
            y = []

            for trade in trades:
                features = [
                    trade.rsi if trade.rsi is not None else 50.0,
                    trade.macd if trade.macd is not None else 0.0,
                    trade.volume_ratio if trade.volume_ratio is not None else 1.0,
                    trade.atr if trade.atr is not None else 0.0,
                    trade.pattern_count if trade.pattern_count is not None else 1,
                    1 if trade.pattern == 'bullish_ma_crossover' else 0,
                    1 if trade.pattern == 'rsi_oversold_bounce' else 0,
                    1 if trade.pattern == 'macd_bullish_crossover' else 0,
                    1 if trade.pattern == 'breakout_with_volume' else 0,
                    1 if trade.pattern == 'pullback_in_uptrend' else 0,
                ]
                
                label = 1 if trade.profit_loss and trade.profit_loss > 0 else 0

                X.append(features)
                y.append(label)

            X = np.array(X)
            y = np.array(y)

            # Train-test split
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            # Scale features
            trading_brain.scaler.fit(X_train)
            X_train_scaled = trading_brain.scaler.transform(X_train)
            X_test_scaled = trading_brain.scaler.transform(X_test)

            # Train model
            trading_brain.ml_model.fit(X_train_scaled, y_train)

            # Evaluate
            train_score = trading_brain.ml_model.score(X_train_scaled, y_train)
            test_score = trading_brain.ml_model.score(X_test_scaled, y_test)

            logger.info(
                f"Model retrained on {len(trades)} trades — "
                f"Train: {train_score:.2%}, Test: {test_score:.2%}")

            # Save model
            self.save_ml_model(trading_brain, test_score)

            return True

        except Exception as e:
            logger.error(f"Error retraining model: {e}")
            return False

    def save_ml_model(self, trading_brain, accuracy: float = None):
        """Save trained ML model to database"""
        try:
            model_data = pickle.dumps(trading_brain.ml_model)
            scaler_data = pickle.dumps(trading_brain.scaler)

            # Deactivate old models before saving new one
            self.db.query(MLModel).filter_by(
                model_name='pattern_classifier',
                is_active=True
            ).update({'is_active': False})

            # Save new model
            new_model = MLModel(
                model_name='pattern_classifier',
                model_data=model_data,
                scaler_data=scaler_data,
                is_active=True,
                accuracy=accuracy,
                created_at=datetime.now(IST).replace(tzinfo=None)
            )

            self.db.add(new_model)
            self.db.commit()

            logger.info(
                f"ML model saved — accuracy: {accuracy:.2%}" if accuracy else "ML model saved")

        except Exception as e:
            logger.error(f"Error saving model: {e}")
            self.db.rollback()

    def generate_performance_report(self) -> dict:
        """Generate comprehensive performance summary"""
        try:
            trades = self.db.query(Trade).filter(
                Trade.status == 'CLOSED').all()

            if not trades:
                return {'status': 'No trades completed yet', 'total_trades': 0}

            total_trades = len(trades)
            winning_trades = [
                t for t in trades if t.profit_loss and t.profit_loss > 0]
            losing_trades = [
                t for t in trades if t.profit_loss and t.profit_loss <= 0]

            win_rate = (len(winning_trades) / total_trades) * \
                100 if total_trades > 0 else 0

            avg_win = np.mean(
                [t.profit_loss for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([abs(t.profit_loss)
                               for t in losing_trades]) if losing_trades else 0

            total_pnl = sum(t.profit_loss for t in trades if t.profit_loss)

            # Calculate expectancy
            expectancy = 0
            if total_trades > 0:
                expectancy = (win_rate / 100) * avg_win - \
                    ((100 - win_rate) / 100) * avg_loss

            # Best and worst trades
            best_trade = max(trades, key=lambda t: t.profit_loss or 0)
            worst_trade = min(trades, key=lambda t: t.profit_loss or 0)

            return {
                'total_trades': total_trades,
                'wins': len(winning_trades),
                'losses': len(losing_trades),
                'win_rate': round(win_rate, 2),
                'avg_win': round(avg_win, 2),
                'avg_loss': round(avg_loss, 2),
                'total_pnl': round(total_pnl, 2),
                'expectancy': round(expectancy, 2),
                'best_trade': {
                    'symbol': best_trade.symbol,
                    'pnl': best_trade.profit_loss
                } if best_trade else None,
                'worst_trade': {
                    'symbol': worst_trade.symbol,
                    'pnl': worst_trade.profit_loss
                } if worst_trade else None,
                'pattern_performance': dict(self.pattern_stats)
            }

        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {'error': str(e), 'total_trades': 0}

    def generate_learning_insights(self) -> dict:
        """
        Generate comprehensive learning insights for the AI.

        Returns:
            Dict with learning progress, pattern insights, and recommendations
        """
        try:
            # Get pattern statistics from scan data
            cutoff_date = datetime.now(IST).replace(tzinfo=None) - timedelta(days=30)

            # Pattern occurrence analysis
            pattern_occurrences = self.db.query(PatternOccurrence).filter(
                PatternOccurrence.timestamp >= cutoff_date
            ).all()

            pattern_insights = {}
            for occ in pattern_occurrences:
                if occ.pattern not in pattern_insights:
                    pattern_insights[occ.pattern] = {
                        'total_seen': 0,
                        'traded': 0,
                        'avg_score': [],
                        'market_conditions': []
                    }

                stats = pattern_insights[occ.pattern]
                stats['total_seen'] += 1
                if occ.was_traded:
                    stats['traded'] += 1
                if occ.score:
                    stats['avg_score'].append(occ.score)
                if occ.market_trend:
                    stats['market_conditions'].append(occ.market_trend)

            # Calculate averages and insights
            insights = []
            recommendations = []

            for pattern, data in pattern_insights.items():
                trade_rate = (data['traded'] / data['total_seen']
                              * 100) if data['total_seen'] > 0 else 0

                # Generate insights
                if data['total_seen'] >= 10:
                    if trade_rate < 10:
                        insights.append(
                            f"Pattern '{pattern}' appears frequently ({data['total_seen']} times) "
                            f"but rarely meets entry criteria ({trade_rate:.1f}% trade rate)"
                        )
                        recommendations.append(
                            f"Consider lowering confidence threshold for '{pattern}' "
                            f"or reviewing its scoring criteria"
                        )
                    elif trade_rate > 50:
                        insights.append(
                            f"Pattern '{pattern}' has high trade rate ({trade_rate:.1f}%) - "
                            f"strong signal quality"
                        )

            # Analyze rejection reasons
            recent_scans = self.db.query(ScanResult).join(ScanReport).filter(
                ScanReport.timestamp >= cutoff_date,
                ScanResult.decision == 'PASS'
            ).all()

            rejection_counts = {}
            for result in recent_scans:
                reason = result.rejection_reason or 'Unknown'
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

            # Top rejection reason
            if rejection_counts:
                top_rejection = max(
                    rejection_counts.items(), key=lambda x: x[1])
                insights.append(
                    f"Most common rejection reason: '{top_rejection[0]}' "
                    f"({top_rejection[1]} occurrences)"
                )

                if 'insufficient' in top_rejection[0].lower():
                    recommendations.append(
                        "Consider adjusting confidence score threshold - "
                        "many opportunities are close but not meeting criteria"
                    )

            # Get actual trade performance
            trades = self.db.query(Trade).filter(
                Trade.status == 'CLOSED',
                Trade.entry_date >= cutoff_date
            ).all()

            trade_performance = {
                'total_trades': len(trades),
                'wins': len([t for t in trades if t.profit_loss and t.profit_loss > 0]),
                'losses': len([t for t in trades if t.profit_loss and t.profit_loss <= 0])
            }

            if trade_performance['total_trades'] > 0:
                win_rate = (
                    trade_performance['wins'] / trade_performance['total_trades']) * 100
                trade_performance['win_rate'] = round(win_rate, 2)

                if win_rate < 40:
                    recommendations.append(
                        f"Win rate is low ({win_rate:.1f}%). Consider being more selective "
                        "or adjusting entry criteria"
                    )
                elif win_rate > 60:
                    insights.append(
                        f"Strong win rate ({win_rate:.1f}%) - current strategy is working well"
                    )
                    recommendations.append(
                        "Consider slightly lowering threshold to capture more opportunities "
                        "while maintaining quality"
                    )

            return {
                'insights': insights,
                'recommendations': recommendations,
                'pattern_analysis': {
                    pattern: {
                        'total_seen': data['total_seen'],
                        'traded': data['traded'],
                        'trade_rate': round((data['traded'] / data['total_seen'] * 100) if data['total_seen'] > 0 else 0, 2),
                        'avg_score': round(sum(data['avg_score']) / len(data['avg_score']), 2) if data['avg_score'] else 0
                    }
                    for pattern, data in pattern_insights.items()
                },
                'trade_performance': trade_performance,
                'top_rejections': dict(sorted(rejection_counts.items(), key=lambda x: x[1], reverse=True)[:5])
            }

        except Exception as e:
            logger.error(f"Error generating learning insights: {e}")
            return {
                'insights': [],
                'recommendations': [],
                'error': str(e)
            }
