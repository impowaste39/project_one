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

    def calculate_net_pnl(self, entry_price: float, exit_price: float,
                          quantity: int) -> tuple:
        """
        Calculate real net P&L after Groww equity delivery charges.

        Groww delivery fee structure (NSE):
          - Brokerage:       min(₹20, 0.1%) per leg (buy + sell)
          - STT:             0.1% on buy + sell turnover
          - Exchange charge: 0.00297% on buy + sell turnover
          - Stamp duty:      0.015% on buy side only
          - SEBI + IPFT:     0.0002% on buy + sell turnover
          - DP charge:       ₹23.60 on sell (₹20 + 18% GST)
          - GST (18%):       on (brokerage + exchange + SEBI/IPFT + DP)

        Returns:
            Tuple of (net_pnl, total_charges) both rounded to 2 dp
        """
        buy_turnover = entry_price * quantity
        sell_turnover = exit_price * quantity
        gross_pnl = (exit_price - entry_price) * quantity

        # Brokerage: min(₹20, 0.1%) per leg
        brokerage_buy = min(20.0, buy_turnover * 0.001)
        brokerage_sell = min(20.0, sell_turnover * 0.001)

        # STT: 0.1% on both sides
        stt = (buy_turnover + sell_turnover) * 0.001

        # Exchange transaction charges: 0.00297% both sides
        exchange = (buy_turnover + sell_turnover) * 0.0000297

        # Stamp duty: 0.015% buy side only
        stamp = buy_turnover * 0.00015

        # SEBI turnover fee + IPFT: 0.0001% + 0.0001% = 0.0002% both sides
        sebi_ipft = (buy_turnover + sell_turnover) * 0.000002

        # DP charges on sell: ₹20 + 18% GST = ₹23.60
        dp = 23.60

        # GST 18% on (brokerage + exchange charges + SEBI/IPFT + DP)
        gst = (brokerage_buy + brokerage_sell +
               exchange + sebi_ipft + dp) * 0.18

        total_charges = round(
            brokerage_buy + brokerage_sell + stt + exchange +
            stamp + sebi_ipft + dp + gst, 2
        )
        net_pnl = round(gross_pnl - total_charges, 2)

        return net_pnl, total_charges

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

        # Stochastic Oversold + RSI confirmation — now scores properly
        # Previously detected (11,818 hits) but contributed 0 pts. Fixed.
        if 'stochastic_oversold' in analysis.get('patterns', []):
            rsi_val = analysis.get('rsi', 50)
            if pd.notna(rsi_val) and rsi_val < 45:
                # Stochastic oversold + RSI confirming weakness = high-quality reversal signal
                technical_score += 8
                factors.append(
                    f"Stochastic oversold + RSI confirmation ({rsi_val:.1f})")
            else:
                technical_score += 4
                factors.append("Stochastic oversold (weak RSI confirmation)")

        # Moving Average Alignment
        if analysis.get('signals', {}).get('ma_crossover'):
            technical_score += 10
            factors.append("Bullish MA crossover")
        elif analysis.get('signals', {}).get('trend_strength'):
            technical_score += 7
            factors.append("Strong trend structure")

        score += technical_score

        # === CONTEXT BONUS (replaces demoted noise patterns — capped at 5 pts) ===
        # strong_uptrend and above_all_mas were removed from pattern_count to
        # prevent score inflation, but they do carry real information as context.
        context_bonus = 0
        if analysis.get('signals', {}).get('strong_uptrend_context'):
            context_bonus += 3
            factors.append("Confirmed uptrend structure (HH+HL)")
        if analysis.get('signals', {}).get('above_all_mas_context'):
            context_bonus += 2
            factors.append("Price above SMA20 & SMA50")
        score += min(5, context_bonus)

        # === PATTERN SCORE (45 points) ===
        pattern_score = min(45, analysis.get('pattern_count', 0) * 15)
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
        elif market_context.get('trend') == 'bearish':
            market_score -= 5  # Active penalty for bearish conditions
            factors.append("Market in downtrend (penalty applied)")

        if market_context.get('market_breadth') == 'positive':
            market_score += 10
            factors.append("Positive market breadth")

        # India VIX volatility penalty
        vix_vol = market_context.get('market_volatility', 'normal')
        if vix_vol == 'extreme':
            market_score -= 10
            factors.append("India VIX extreme (war regime penalty)")
        elif vix_vol == 'high':
            market_score -= 5
            factors.append("India VIX elevated (volatility penalty)")

        score += max(0, market_score)  # Don't let market score go below 0

        # === ML PREDICTION SCORE (10 points) ===
        ml_score = 0

        try:
            if self.ml_model and hasattr(self.ml_model, 'classes_'):
                # Trained model path — uses real learned probabilities
                features = self.extract_features(analysis)
                if hasattr(self.scaler, 'mean_'):
                    features_scaled = self.scaler.transform(features)
                    probability = self.ml_model.predict_proba(features_scaled)[
                        0][1]
                    ml_score = probability * 10
                    factors.append(
                        f"ML success probability: {probability:.1%}")
            else:
                # Heuristic fallback when ML model is untrained (< 50 closed trades).
                # Uses RSI zone + volume confirmation as a proxy until real data exists.
                rsi = analysis.get('rsi', 50)
                vol = analysis.get('volume_ratio', 1.0)
                if pd.notna(rsi) and pd.notna(vol):
                    if 38 <= rsi <= 62 and vol >= 1.3:
                        ml_score = 7
                        factors.append(
                            "Heuristic: RSI in range + strong volume")
                    elif 35 <= rsi <= 65 and vol >= 1.1:
                        ml_score = 4
                        factors.append(
                            "Heuristic: RSI acceptable + moderate volume")
                    elif 30 <= rsi <= 70:
                        ml_score = 2
                        factors.append("Heuristic: RSI in broad range")
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

        # Stop Loss: 2x ATR or 8%, whichever is smaller
        atr_stop = current_price - (2 * atr)
        percent_stop = current_price * 0.92
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

        # Decision logic — pass symbol and market_context for duplicate/trend checks
        trade_worthy = self.should_enter_trade(
            score_breakdown,
            levels,
            portfolio_state,
            position_info,
            symbol=analysis['symbol'],
            market_context=market_context
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
            'reason': self.get_decision_reason(trade_worthy, score_breakdown, levels,
                                               portfolio_state, analysis['symbol'],
                                               market_context),
            'patterns': analysis.get('patterns', [])
        }

    def should_enter_trade(self, score_breakdown: dict, levels: dict,
                           portfolio_state: dict, position_info: dict,
                           symbol: str = None,
                           market_context: dict = None) -> bool:
        """Final decision gate with multiple checks"""
        market_context = market_context or {}

        # Check 0a: Dynamic score threshold based on market trend.
        # Bearish market: raise bar to 75/80 to protect capital while still
        # allowing the rarest setups through so the learning engine gets data.
        # A hard block would starve the AI of real trade outcomes.
        trend = market_context.get('trend', 'sideways')
        market_strength = market_context.get('strength', 50)
        if trend == 'bearish':
            effective_threshold = 80 if market_strength > 5 else 75
        else:
            effective_threshold = self.min_confidence_score  # 65 standard

        if score_breakdown['total_score'] < effective_threshold:
            return False

        # Check 0b: Duplicate symbol guard — one open position per symbol max.
        # Fixes the ADANIPOWER ×4 bug where the 5-min scanner entered the same
        # stock on every cycle because only total position count was checked.
        if symbol and self.db:
            from models.database import Trade
            existing = self.db.query(Trade).filter(
                Trade.symbol == symbol,
                Trade.status == 'OPEN'
            ).first()
            if existing:
                logger.debug(
                    f"Duplicate guard: {symbol} already held — skipping")
                return False

        # Check 1: Risk-reward ratio
        if levels['rr_ratio'] < 1.45:
            return False

        # Check 2: Portfolio constraints
        max_pos = int(os.getenv('MAX_POSITIONS', 7))
        if portfolio_state['positions_count'] >= max_pos:
            return False

        if portfolio_state['available_capital'] < 1000:
            return False

        # Check 3: Position size validation
        if position_info['quantity'] <= 0:
            return False

        if position_info['investment'] > portfolio_state['available_capital'] * 0.30:
            return False

        # All checks passed
        return True

    def get_decision_reason(self, trade_worthy: bool, score_breakdown: dict,
                            levels: dict, portfolio_state: dict,
                            symbol: str = None,
                            market_context: dict = None) -> str:
        """Generate human-readable decision reason"""
        market_context = market_context or {}
        trend = market_context.get('trend', 'sideways')
        market_strength = market_context.get('strength', 50)

        if trade_worthy:
            return (f"Strong setup (score: {score_breakdown['total_score']}/100) "
                    f"with {levels['rr_ratio']}:1 risk-reward")

        # Bearish dynamic threshold
        if trend == 'bearish':
            effective_threshold = 80 if market_strength > 5 else 75
            if score_breakdown['total_score'] < effective_threshold:
                return (f"Bearish market — score {score_breakdown['total_score']}/100 "
                        f"below elevated threshold ({effective_threshold})")

        if score_breakdown['total_score'] < self.min_confidence_score:
            return f"Setup quality insufficient (score: {score_breakdown['total_score']}/100)"

        if levels['rr_ratio'] < 1.45:
            return f"Risk-reward too low ({levels['rr_ratio']}:1)"

        max_pos = int(os.getenv('MAX_POSITIONS', 7))
        if portfolio_state['positions_count'] >= max_pos:
            return f"Maximum positions reached ({max_pos}/{max_pos})"

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

        # Time-based Exit (stagnant losers) — tightened for volatile market
        # Reduced from 10 to 7 days: war conditions make decisions arrive faster
        days_held = (datetime.now() -
                     trade.entry_date).days if trade.entry_date else 0

        if days_held >= 7 and current_price < trade.entry_price:
            return {
                'action': 'EXIT',
                'reason': f'Time decay ({days_held} days with loss)',
                'exit_type': 'time_stop',
                'urgency': 'normal'
            }

        # Max holding period — tightened from 15 to 12 days
        if days_held >= 12:
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
