"""
Trading Brain - AI Decision Engine
Makes intelligent trading decisions using ML and rule-based systems
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import pickle
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class TradingBrain:
    """AI Decision Engine for trading"""

    def __init__(self, db_session=None, risk_manager=None):
        self.db = db_session
        self.risk_manager = risk_manager
        self.ml_model = None
        self.scaler = None
        self.min_confidence_score = int(os.getenv('MIN_CONFIDENCE_SCORE', 70))
        self.load_or_initialize_model()

    def load_or_initialize_model(self):
        """Load existing ML model or create new one"""
        try:
            if self.db:
                from models.database import MLModel
                model_record = self.db.query(MLModel).filter_by(
                    model_name='pattern_classifier',
                    is_active=True
                ).first()

                if model_record:
                    self.ml_model = pickle.loads(model_record.model_data)
                    self.scaler = pickle.loads(model_record.scaler_data)
                    logger.info("ML model loaded from database")
                    return

            # Initialize new model
            self.ml_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            self.scaler = StandardScaler()
            logger.info("New ML model initialized")

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.ml_model = RandomForestClassifier(n_estimators=100)
            self.scaler = StandardScaler()

    def extract_features(self, analysis: dict) -> np.ndarray:
        """Extract ML features from stock analysis"""
        features = [
            analysis.get('rsi', 50),
            analysis.get('macd', 0),
            analysis.get('volume_ratio', 1),
            analysis.get('atr', 0),
            analysis.get('pattern_count', 0),
            1 if 'bullish_ma_crossover' in analysis.get('patterns', []) else 0,
            1 if 'rsi_oversold_bounce' in analysis.get('patterns', []) else 0,
            1 if 'macd_bullish_crossover' in analysis.get(
                'patterns', []) else 0,
            1 if 'breakout_with_volume' in analysis.get('patterns', []) else 0,
            1 if 'pullback_in_uptrend' in analysis.get('patterns', []) else 0,
        ]

        return np.array(features).reshape(1, -1)

    def calculate_setup_score(self, analysis: dict, market_context: dict) -> dict:
        """
        Calculate trading setup quality score (0-100)

        Scoring:
        - Technical indicators: 40 points
        - Pattern strength: 30 points
        - Market context: 20 points
        - ML prediction: 10 points
        """
        score = 0
        factors = []

        # === TECHNICAL INDICATORS SCORE (40 points) ===
        technical_score = 0

        rsi = analysis.get('rsi', 50)
        if pd.notna(rsi):
            if 40 <= rsi <= 60:
                technical_score += 10
                factors.append(f"RSI in healthy zone ({rsi:.1f})")
            elif 30 <= rsi < 40:
                technical_score += 7
                factors.append(f"RSI slightly oversold ({rsi:.1f})")
            elif 60 < rsi <= 70:
                technical_score += 5
                factors.append(f"RSI approaching overbought ({rsi:.1f})")

        # MACD
        if analysis.get('signals', {}).get('macd_cross'):
            technical_score += 10
            factors.append("MACD bullish crossover")
        elif analysis.get('macd', 0) > 0:
            technical_score += 5
            factors.append("MACD positive")

        # Volume
        volume_ratio = analysis.get('volume_ratio', 1)
        if pd.notna(volume_ratio):
            if volume_ratio >= 1.5:
                technical_score += 10
                factors.append(f"Strong volume ({volume_ratio:.2f}x)")
            elif volume_ratio >= 1.2:
                technical_score += 7
                factors.append(f"Good volume ({volume_ratio:.2f}x)")

        # Moving Average Alignment
        if analysis.get('signals', {}).get('ma_crossover'):
            technical_score += 10
            factors.append("Bullish MA crossover")
        elif analysis.get('signals', {}).get('trend_strength'):
            technical_score += 7
            factors.append("Strong trend structure")

        score += technical_score

        # === PATTERN SCORE (30 points) ===
        pattern_score = min(30, analysis.get('pattern_count', 0) * 10)
        score += pattern_score

        if analysis.get('patterns'):
            factors.append(
                f"{analysis['pattern_count']} bullish patterns detected")

        # === MARKET CONTEXT SCORE (20 points) ===
        market_score = 0

        if market_context.get('trend') == 'bullish':
            market_score += 10
            factors.append("Market in uptrend")
        elif market_context.get('trend') == 'sideways':
            market_score += 5

        if market_context.get('market_breadth') == 'positive':
            market_score += 10
            factors.append("Positive market breadth")

        score += market_score

        # === ML PREDICTION SCORE (10 points) ===
        ml_score = 0

        try:
            if self.ml_model and hasattr(self.ml_model, 'classes_'):
                features = self.extract_features(analysis)
                if hasattr(self.scaler, 'mean_'):
                    features_scaled = self.scaler.transform(features)
                    probability = self.ml_model.predict_proba(features_scaled)[
                        0][1]
                    ml_score = probability * 10
                    factors.append(
                        f"ML success probability: {probability:.1%}")
        except Exception as e:
            logger.debug(f"ML prediction skipped: {e}")

        score += ml_score

        return {
            'total_score': min(100, score),
            'technical_score': technical_score,
            'pattern_score': pattern_score,
            'market_score': market_score,
            'ml_score': ml_score,
            'factors': factors,
            'confidence': min(100, score) / 100
        }

    def calculate_entry_exit_levels(self, analysis: dict) -> dict:
        """Calculate entry price, stop loss, and target levels"""
        current_price = analysis['current_price']
        atr = analysis.get('atr', current_price * 0.02)

        if pd.isna(atr) or atr == 0:
            atr = current_price * 0.02

        # Entry: Current market price
        entry_price = current_price

        # Stop Loss: 2x ATR or 5%, whichever is smaller
        atr_stop = current_price - (2 * atr)
        percent_stop = current_price * 0.95
        stop_loss = max(atr_stop, percent_stop)

        # Targets
        risk = entry_price - stop_loss

        target_1 = entry_price + (risk * 1.5)
        target_2 = entry_price + (risk * 2.0)
        target_3 = entry_price + (risk * 3.0)

        risk_percent = ((entry_price - stop_loss) / entry_price) * 100
        reward_1_percent = ((target_1 - entry_price) / entry_price) * 100

        return {
            'entry_price': round(entry_price, 2),
            'stop_loss': round(stop_loss, 2),
            'target_1': round(target_1, 2),
            'target_2': round(target_2, 2),
            'target_3': round(target_3, 2),
            'risk_percent': round(risk_percent, 2),
            'reward_percent': round(reward_1_percent, 2),
            'rr_ratio': round(reward_1_percent / risk_percent, 2) if risk_percent > 0 else 0
        }

    def evaluate_opportunity(self, analysis: dict, market_context: dict,
                             portfolio_state: dict) -> dict:
        """Complete evaluation of a trading opportunity"""
        # Calculate setup score
        score_breakdown = self.calculate_setup_score(analysis, market_context)

        # Calculate entry/exit levels
        levels = self.calculate_entry_exit_levels(analysis)

        # Calculate position size
        position_info = {'quantity': 0, 'investment': 0, 'risk_amount': 0}
        if self.risk_manager:
            position_info = self.risk_manager.calculate_position_size(
                capital=portfolio_state['available_capital'],
                entry_price=levels['entry_price'],
                stop_loss=levels['stop_loss']
            )

        # Decision logic
        trade_worthy = self.should_enter_trade(
            score_breakdown,
            levels,
            portfolio_state,
            position_info
        )

        return {
            'symbol': analysis['symbol'],
            'score': score_breakdown['total_score'],
            'confidence': score_breakdown['confidence'],
            'factors': score_breakdown['factors'],
            'entry_price': levels['entry_price'],
            'stop_loss': levels['stop_loss'],
            'target_1': levels['target_1'],
            'target_2': levels['target_2'],
            'rr_ratio': levels['rr_ratio'],
            'quantity': position_info['quantity'],
            'investment': position_info['investment'],
            'risk_amount': position_info['risk_amount'],
            'trade_worthy': trade_worthy,
            'decision': 'ENTER' if trade_worthy else 'PASS',
            'reason': self.get_decision_reason(trade_worthy, score_breakdown, levels, portfolio_state),
            'patterns': analysis.get('patterns', [])
        }

    def should_enter_trade(self, score_breakdown: dict, levels: dict,
                           portfolio_state: dict, position_info: dict) -> bool:
        """Final decision gate with multiple checks"""
        # Check 1: Score threshold
        if score_breakdown['total_score'] < self.min_confidence_score:
            return False

        # Check 2: Risk-reward ratio
        if levels['rr_ratio'] < 1.5:
            return False

        # Check 3: Portfolio constraints
        if portfolio_state['positions_count'] >= 5:
            return False

        if portfolio_state['available_capital'] < 1000:
            return False

        # Check 4: Position size validation
        if position_info['quantity'] <= 0:
            return False

        if position_info['investment'] > portfolio_state['available_capital'] * 0.30:
            return False

        # All checks passed
        return True

    def get_decision_reason(self, trade_worthy: bool, score_breakdown: dict,
                            levels: dict, portfolio_state: dict) -> str:
        """Generate human-readable decision reason"""
        if trade_worthy:
            return (f"Strong setup (score: {score_breakdown['total_score']}/100) "
                    f"with {levels['rr_ratio']}:1 risk-reward")

        if score_breakdown['total_score'] < self.min_confidence_score:
            return f"Setup quality insufficient (score: {score_breakdown['total_score']}/100)"

        if levels['rr_ratio'] < 1.5:
            return f"Risk-reward too low ({levels['rr_ratio']}:1)"

        if portfolio_state['positions_count'] >= 5:
            return "Maximum positions reached (5/5)"

        if portfolio_state['available_capital'] < 1000:
            return "Insufficient capital"

        return "General constraints not met"

    def check_exit_conditions(self, trade, current_price: float,
                              current_data: pd.DataFrame = None) -> dict:
        """Determine if position should be exited"""
        # Stop Loss Check
        if current_price <= trade.stop_loss:
            return {
                'action': 'EXIT',
                'reason': 'Stop loss hit',
                'exit_type': 'stop_loss',
                'urgency': 'immediate'
            }

        # Target Achievement
        if current_price >= trade.target:
            return {
                'action': 'EXIT',
                'reason': 'Target achieved',
                'exit_type': 'target',
                'urgency': 'immediate'
            }

        # Trailing Stop (after 1:1 risk-reward achieved)
        unrealized_pnl = (current_price - trade.entry_price) * trade.quantity
        initial_risk = (trade.entry_price - trade.stop_loss) * trade.quantity

        if unrealized_pnl >= initial_risk:
            trailing_stop = trade.entry_price + \
                (initial_risk / trade.quantity * 0.5)

            if current_price <= trailing_stop:
                return {
                    'action': 'EXIT',
                    'reason': 'Trailing stop hit (profit protected)',
                    'exit_type': 'trailing_stop',
                    'urgency': 'immediate'
                }

        # Time-based Exit (stagnant losers)
        days_held = (datetime.now() -
                     trade.entry_date).days if trade.entry_date else 0

        if days_held >= 10 and current_price < trade.entry_price:
            return {
                'action': 'EXIT',
                'reason': f'Time decay ({days_held} days with loss)',
                'exit_type': 'time_stop',
                'urgency': 'normal'
            }

        # Max holding period
        if days_held >= 15:
            return {
                'action': 'EXIT',
                'reason': f'Maximum holding period reached ({days_held} days)',
                'exit_type': 'max_duration',
                'urgency': 'normal'
            }

        # No exit condition met
        return {
            'action': 'HOLD',
            'reason': 'All criteria within acceptable range',
            'exit_type': None,
            'urgency': None
        }
