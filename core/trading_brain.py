"""
Trading Brain - AI Decision Engine
Makes intelligent trading decisions using ML and rule-based systems

Improvements in this version:
- Weekly EMA filter: only enter if price is above 50-week EMA (long-term trend check)
- Position scaling by score: bet bigger only on high-conviction setups
"""

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import pickle
import logging
import os
import pytz
from datetime import datetime
from utils.helpers import calculate_net_pnl

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')

class TradingBrain:
    """AI Decision Engine for trading"""

    def __init__(self, db_session=None, risk_manager=None, data_service=None):
        self.db = db_session
        self.risk_manager = risk_manager
        self.data_service = data_service
        self.ml_model = None
        self.scaler = None
        self.min_confidence_score = int(os.getenv("MIN_CONFIDENCE_SCORE", 70))
        self.reload_ml_model()

    def reload_ml_model(self):
        """Reload existing ML model from database or initialize a new one."""
        try:
            if self.db:
                from models.database import MLModel

                model_record = (
                    self.db.query(MLModel)
                    .filter_by(model_name="pattern_classifier", is_active=True)
                    .first()
                )

                if model_record:
                    self.ml_model = pickle.loads(model_record.model_data)
                    self.scaler = pickle.loads(model_record.scaler_data)
                    logger.info("ML model loaded from database")
                    return

            self.ml_model = RandomForestClassifier(
                n_estimators=100, max_depth=10, random_state=42
            )
            self.scaler = StandardScaler()
            logger.info("New ML model initialized")

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self.ml_model = RandomForestClassifier(n_estimators=100)
            self.scaler = StandardScaler()

    def prime_adaptive_thresholds(self):
        """
        Compute adaptive pattern thresholds ONCE before the scan loop.
        Call this at the start of scan_market_job, not per-stock inside the loop.
        Stores result in self._cached_pattern_thresholds.
        """
        self._cached_pattern_thresholds = {}
        if not self.db:
            return
        try:
            from models.database import Trade
            total_closed = self.db.query(Trade).filter(Trade.status == 'CLOSED').count()
            if total_closed < 10:
                return
            closed_trades = self.db.query(Trade).filter(Trade.status == 'CLOSED').all()
            pattern_stats = {}
            for t in closed_trades:
                if not t.pattern:
                    continue
                if t.pattern not in pattern_stats:
                    pattern_stats[t.pattern] = {'win': 0, 'total': 0}
                pattern_stats[t.pattern]['total'] += 1
                if t.profit_loss is not None and t.profit_loss >= 0:
                    pattern_stats[t.pattern]['win'] += 1
            base_thresholds = {
                'bullish_ma_crossover': 65, 'macd_bullish_crossover': 68,
                'pullback_in_uptrend': 72,  'breakout_with_volume': 70,
                'trend_strength': 72,       'rsi_oversold_bounce': 68,
                'stochastic_oversold': 68,  'strong_momentum': 68,
            }
            for pat, stats in pattern_stats.items():
                if stats['total'] >= 3 and pat in base_thresholds:
                    win_rate = stats['win'] / stats['total']
                    base = base_thresholds[pat]
                    if win_rate > 0.65:
                        self._cached_pattern_thresholds[pat] = max(60, base - 3)
                    elif win_rate < 0.45:
                        self._cached_pattern_thresholds[pat] = min(85, base + 5)
            logger.info(f"[AdaptiveThreshold] Cached {len(self._cached_pattern_thresholds)} pattern thresholds")
        except Exception as e:
            logger.warning(f"[AdaptiveThreshold] Cache build skipped: {e}")

    def is_model_trained(self) -> bool:
        """Safely check if the ML model is trained without triggering NotFittedError crashes"""
        try:
            if not self.ml_model:
                return False
            from sklearn.utils.validation import check_is_fitted
            check_is_fitted(self.ml_model)
            return True
        except Exception:
            return False

    def extract_features(self, analysis: dict) -> np.ndarray:
        """Extract ML features from stock analysis"""
        features = [
            analysis.get("rsi", 50),
            analysis.get("macd", 0),
            analysis.get("volume_ratio", 1),
            analysis.get("atr", 0),
            analysis.get("pattern_count", 0),
            1 if "bullish_ma_crossover" in analysis.get("patterns", []) else 0,
            1 if "rsi_oversold_bounce" in analysis.get("patterns", []) else 0,
            1 if "macd_bullish_crossover" in analysis.get("patterns", []) else 0,
            1 if "breakout_with_volume" in analysis.get("patterns", []) else 0,
            1 if "pullback_in_uptrend" in analysis.get("patterns", []) else 0,
        ]
        return np.array(features).reshape(1, -1)

    def calculate_net_pnl(
        self,
        entry_price: float,
        exit_price: float,
        quantity: int,
        partially_exited: bool = False,
        partial_exit_price: float = None,
        partial_exit_qty: int = None,
    ) -> tuple:
        """
        Delegates to the shared calculate_net_pnl() in utils/helpers.py.
        Kept as an instance method so existing callers (should_enter_trade,
        get_decision_reason, check_exit_conditions) need no changes.
        """
        return calculate_net_pnl(
            entry_price,
            exit_price,
            quantity,
            partially_exited=partially_exited,
            partial_exit_price=partial_exit_price,
            partial_exit_qty=partial_exit_qty,
        )

    # =========================================================================
    # NEW: WEEKLY EMA FILTER
    # Fetches 1-year weekly data and checks if price is above 50-week EMA.
    # If below — stock is in long-term downtrend — skip regardless of daily setup.
    #
    # Why 50-week EMA?
    # It represents ~1 year of trend. Stocks below it are falling knives.
    # Daily patterns can look bullish but bigger trend is against you.
    # We only trade WITH the long-term trend — that's disciplined swing trading.
    #
    # Failure handling: if fetch fails for any reason, filter is bypassed (True)
    # so a network hiccup doesn't block the entire scan.
    # =========================================================================
    def check_weekly_ema_filter(self, symbol: str) -> tuple:
        """
        Check if stock price is above its 50-week EMA
        Returns:
            (passes: bool, reason: str)
            passes=True  → above 50W EMA, safe to enter
            passes=False → below 50W EMA, skip this stock
        """
        try:
            ticker = yf.Ticker(symbol)
            # 6 months of weekly data is enough for a 50W EMA with min_periods=10
            weekly_data = ticker.history(period="6mo", interval="1wk")

            if weekly_data is None or weekly_data.empty or len(weekly_data) < 20:
                logger.debug(
                    f"[WeeklyEMA] {symbol}: insufficient weekly data, bypassing filter"
                )
                return True, "Weekly EMA: insufficient data (bypassed)"

            ema_series = weekly_data["Close"].ewm(span=50, min_periods=10, adjust=False).mean()
            current_price = float(weekly_data["Close"].iloc[-1])
            ema_50w = float(ema_series.iloc[-1])

            # Free memory immediately — don't hold the DataFrame for the rest of evaluation
            del weekly_data, ema_series

            if pd.isna(ema_50w):
                logger.debug(f"[WeeklyEMA] {symbol}: EMA is NaN, bypassing filter")
                return True, "Weekly EMA: unavailable (bypassed)"

            distance_pct = ((current_price - ema_50w) / ema_50w) * 100
            distance_str = f"{distance_pct:.1f}%" if pd.notna(distance_pct) else "n/a"

            if current_price >= ema_50w:
                reason = f"Above 50W EMA ₹{ema_50w:.1f} (+{distance_str})"
                logger.debug(f"[WeeklyEMA] {symbol}: PASS — {reason}")
                return True, reason
            else:
                reason = (
                    f"Below 50W EMA ₹{ema_50w:.1f} ({distance_str}) "
                    f"— long-term downtrend"
                )
                logger.info(f"[WeeklyEMA] {symbol}: BLOCKED — {reason}")
                return False, reason

        except Exception as e:
            logger.warning(
                f"[WeeklyEMA] {symbol}: fetch failed ({e}), bypassing filter"
            )
            return True, "Weekly EMA: fetch error (bypassed)"

    # =========================================================================
    # NEW: POSITION SCALING BY SCORE
    # Same rules, different bet sizes based on conviction.
    #
    # Score 65-74  → 0.75x  CAUTIOUS   (valid setup, not outstanding)
    # Score 75-84  → 1.0x   NORMAL     (solid setup, standard bet)
    # Score 85-100 → 1.5x   HIGH CONVICTION (rare, strong setup, bet bigger)
    #
    # Applied AFTER base risk_manager sizing.
    # Hard cap of 30% available capital always enforced.
    # =========================================================================
    def get_position_size_multiplier(self, score: int) -> tuple:
        """
        Returns (multiplier, tier_label) based on setup score.
        """
        if score >= 85:
            return 1.5, "HIGH CONVICTION"
        elif score >= 75:
            return 1.0, "NORMAL"
        else:
            return 0.75, "CAUTIOUS"

    def calculate_setup_score(self, analysis: dict, market_context: dict) -> dict:
        """
        Calculate trading setup quality score (0-100)

        Scoring:
        - Technical indicators: 40 points
        - Pattern strength: 45 points
        - Market context: 20 points
        - ML prediction: 10 points
        """
        score = 0
        factors = []

        # === TECHNICAL INDICATORS SCORE (40 points) ===
        technical_score = 0

        rsi = analysis.get("rsi", 50)
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

        if analysis.get("signals", {}).get("macd_cross"):
            technical_score += 10
            factors.append("MACD bullish crossover")
        elif analysis.get("macd", 0) > 0:
            technical_score += 5
            factors.append("MACD positive")

        volume_ratio = analysis.get("volume_ratio", 1)
        if pd.notna(volume_ratio):
            if volume_ratio >= 1.5:
                technical_score += 10
                factors.append(f"Strong volume ({volume_ratio:.2f}x)")
            elif volume_ratio >= 1.2:
                technical_score += 7
                factors.append(f"Good volume ({volume_ratio:.2f}x)")

        if "stochastic_oversold" in analysis.get("patterns", []):
            rsi_val = analysis.get("rsi", 50)
            if pd.notna(rsi_val) and rsi_val < 45:
                technical_score += 8
                factors.append(
                    f"Stochastic oversold + RSI confirmation ({rsi_val:.1f})"
                )
            else:
                technical_score += 4
                factors.append("Stochastic oversold (weak RSI confirmation)")

        if analysis.get("signals", {}).get("ma_crossover"):
            technical_score += 10
            factors.append("Bullish MA crossover")
        elif analysis.get("signals", {}).get("trend_strength"):
            technical_score += 7
            factors.append("Strong trend structure")

        score += technical_score

        # === CONTEXT BONUS (capped at 5 pts) ===
        context_bonus = 0
        if analysis.get("signals", {}).get("strong_uptrend_context"):
            context_bonus += 3
            factors.append("Confirmed uptrend structure (HH+HL)")
        if analysis.get("signals", {}).get("above_all_mas_context"):
            context_bonus += 2
            factors.append("Price above SMA20 & SMA50")
        score += min(5, context_bonus)

        # === PATTERN SCORE (45 points) ===
        pattern_score = min(45, analysis.get("pattern_count", 0) * 15)
        score += pattern_score
        if analysis.get("patterns"):
            factors.append(f"{analysis['pattern_count']} bullish patterns detected")

        # === HIGH-QUALITY BREAKOUT BONUS (FEAT-06) (+15 pts) ===
        if "breakout_with_volume" in analysis.get("patterns", []):
            sig = analysis.get("signals", {})
            if sig.get("breakout_20d_high") and sig.get("breakout_volume_2x") and sig.get("breakout_first_2h"):
                score += 15
                factors.append("Institutional Volume Breakout (20d high + 2x Vol + First 2h) (+15)")

        # === MARKET CONTEXT SCORE (20 points) ===
        market_score = 0
        if market_context.get("trend") == "bullish":
            market_score += 10
            factors.append("Market in uptrend")
        elif market_context.get("trend") == "sideways":
            market_score += 5
        elif market_context.get("trend") == "bearish":
            market_score -= 5
            factors.append("Market in downtrend (penalty applied)")

        if market_context.get("market_breadth") == "positive":
            market_score += 10
            factors.append("Positive market breadth")

        vix_vol = market_context.get("market_volatility", "normal")
        if vix_vol == "extreme":
            market_score -= 10
            factors.append("India VIX extreme (war regime penalty)")
        elif vix_vol == "high":
            market_score -= 5
            factors.append("India VIX elevated (volatility penalty)")

        score += max(-10, market_score)

        # === ML PREDICTION SCORE (10 points) ===
        ml_score = 0
        try:
            if self.is_model_trained():
                features = self.extract_features(analysis)
                if hasattr(self.scaler, "mean_"):
                    features_scaled = self.scaler.transform(features)
                    probability = self.ml_model.predict_proba(features_scaled)[0][1]
                    ml_score = probability * 10
                    factors.append(f"ML success probability: {probability:.1%}")
            else:
                # Heuristic fallback — ML model not yet trained (needs 20+ closed trades)
                rsi = analysis.get("rsi", 50)
                vol = analysis.get("volume_ratio", 1.0)
                if pd.notna(rsi) and pd.notna(vol):
                    if 38 <= rsi <= 62 and vol >= 1.3:
                        ml_score = 7
                        factors.append("Heuristic: RSI in range + strong volume")
                    elif 35 <= rsi <= 65 and vol >= 1.1:
                        ml_score = 4
                        factors.append("Heuristic: RSI acceptable + moderate volume")
                    elif 30 <= rsi <= 70:
                        ml_score = 2
                        factors.append("Heuristic: RSI in broad range")
        except Exception as e:
            logger.debug(f"ML prediction skipped: {e}")

        score += ml_score

        # === RELATIVE STRENGTH vs NIFTY (+5 / -5) ===
        # Outperforming Nifty over 20 days = institutional money flowing IN.
        # This is one of the strongest selection criteria used by professional desks.
        rs_positive = analysis.get('rs_positive')  # True/False/None
        if rs_positive is True:
            score += 5
            stock_ret = analysis.get('stock_return_20d', 0) or 0
            nifty_ret = analysis.get('nifty_return_20d', 0) or 0
            factors.append(f"RS outperforms Nifty ({stock_ret:.1f}% vs {nifty_ret:.1f}%)")
        elif rs_positive is False:
            score -= 5
            stock_ret = analysis.get('stock_return_20d', 0) or 0
            nifty_ret = analysis.get('nifty_return_20d', 0) or 0
            factors.append(f"RS underperforms Nifty ({stock_ret:.1f}% vs {nifty_ret:.1f}%) — penalty")

        # === RESISTANCE PROXIMITY PENALTY (-8) ===
        # Entering within 3% of a 90-day swing high means very limited upside before
        # resistance pushes price back. Historical high = where sellers waiting.
        if analysis.get('near_resistance'):
            score -= 8
            resistance_level = analysis.get('signals', {}).get('resistance_level', '?')
            dist_pct = analysis.get('signals', {}).get('resistance_dist_pct', '?')
            factors.append(
                f"Near 90d resistance ₹{resistance_level} ({dist_pct}% away) — upside limited (-8)"
            )

        return {
            "total_score": min(100, max(0, score)),
            "technical_score": technical_score,
            "pattern_score": pattern_score,
            "market_score": market_score,
            "ml_score": ml_score,
            "factors": factors,
            "confidence": min(100, max(0, score)) / 100,
        }


    def calculate_entry_exit_levels(self, analysis: dict) -> dict:
        """Calculate entry price, stop loss, and target levels"""
        current_price = analysis['current_price']
        atr = analysis.get('atr', current_price * 0.02)

        if pd.isna(atr) or atr == 0:
            atr = current_price * 0.02

        entry_price = current_price

        # ── Two stop loss candidates ──────────────────────────────────────────
        # 1. ATR-based (2x ATR below entry) — volatility-aware
        atr_stop = current_price - (2 * atr)

        max_distance_stop = current_price * 0.88    # loosest allowed: 12% away
        min_distance_stop = current_price * 0.985   # tightest allowed: 1.5% away

        stop_loss = max(atr_stop, max_distance_stop)   # never wider than 12%
        stop_loss = min(stop_loss, min_distance_stop)  # never tighter than 1.5%
        # ─────────────────────────────────────────────────────────────────────

        risk = entry_price - stop_loss
        target_1 = entry_price + (risk * 2.0)
        target_2 = entry_price + (risk * 3.0)
        target_3 = entry_price + (risk * 4.0)

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
            'rr_ratio': round(reward_1_percent / risk_percent, 2)
            if risk_percent > 0
            else 0,
        }

    def evaluate_opportunity(
        self, analysis: dict, market_context: dict, portfolio_state: dict
    ) -> dict:
        """
        Complete evaluation of a trading opportunity.

        Features:
        - Weekly EMA penalty (not binary block — allows strong setups in downtrends)
        - ML Cold Start Bonus (+10 pts until model trained — breaks catch-22)
        - Position scaling by score (bet bigger on high-conviction setups)
        """
        score_breakdown = self.calculate_setup_score(analysis, market_context)
        levels = self.calculate_entry_exit_levels(analysis)
        symbol = analysis["symbol"]

        # --- COLD START BONUS: +10 pts until ML model is trained ---
        # We need 20 trades to train ML, but ML adds 10 pts to score.
        # Without this bonus, we can't reach thresholds to get those 20 trades.
        # This is temporary and auto-disables once model is trained.
        ml_model_active = self.is_model_trained()

        if not ml_model_active:
            old_score = score_breakdown["total_score"]
            score_breakdown["total_score"] = min(100, score_breakdown["total_score"] + 10)
            score_breakdown["factors"].append(f"ML cold start bonus (+10): {old_score} → {score_breakdown['total_score']}")
            logger.info(
                f"[ColdStart] {symbol}: score boosted {old_score} → {score_breakdown['total_score']} "
                f"(ML model not yet trained — need 20 trades)"
            )

        # --- WEEKLY EMA: Apply -10 pt penalty instead of binary block ---
        # Being below 50W EMA is a warning sign, not an automatic reject.
        # Strong daily setups (score 70+) can still be valid in long-term downtrends.
        weekly_ema_passes, weekly_ema_reason = self.check_weekly_ema_filter(symbol)
        ema_penalty_applied = False

        if not weekly_ema_passes:
            ema_penalty_applied = True
            ema_penalty = 10
            old_score = score_breakdown["total_score"]
            score_breakdown["total_score"] = max(0, score_breakdown["total_score"] - ema_penalty)
            score_breakdown["factors"].append(f"Weekly EMA penalty (-{ema_penalty}): {weekly_ema_reason}")
            logger.info(
                f"[WeeklyEMA] {symbol}: Below 50W EMA — applying -{ema_penalty} penalty "
                f"(not blocking). Score: {old_score} → {score_breakdown['total_score']}"
            )
        else:
            # Bonus for being ABOVE 50W EMA — confirms long-term uptrend
            score_breakdown["factors"].append(f"Weekly EMA confirmation: {weekly_ema_reason}")

        # Store EMA info for Discord alerts
        weekly_ema_status = "above" if weekly_ema_passes else "below"

        # --- BASE POSITION SIZING ---
        position_info = {"quantity": 0, "investment": 0, "risk_amount": 0}
        if self.risk_manager:
            position_info = self.risk_manager.calculate_position_size(
                capital=portfolio_state["available_capital"],
                entry_price=levels["entry_price"],
                stop_loss=levels["stop_loss"],
                atr=analysis.get("atr")
            )

        # --- POSITION SCALING BY SCORE ---
        score = score_breakdown["total_score"]
        multiplier, position_tier = self.get_position_size_multiplier(score)

        if position_info["quantity"] > 0 and multiplier != 1.0:
            scaled_qty = max(1, round(position_info["quantity"] * multiplier))
            scaled_investment = scaled_qty * levels["entry_price"]

            # Hard cap: never exceed 30% of available capital
            max_investment = portfolio_state["available_capital"] * 0.30
            if scaled_investment > max_investment:
                scaled_qty = max(1, int(max_investment / levels["entry_price"]))
                scaled_investment = scaled_qty * levels["entry_price"]

            position_info["quantity"] = scaled_qty
            position_info["investment"] = round(scaled_investment, 2)
            position_info["risk_amount"] = round(
                scaled_qty * (levels["entry_price"] - levels["stop_loss"]), 2
            )

            logger.info(
                f"[PositionScale] {symbol}: score={score} → "
                f"{position_tier} ({multiplier}x) → qty={scaled_qty}"
            )

        trade_worthy = self.should_enter_trade(
            score_breakdown,
            levels,
            portfolio_state,
            position_info,
            symbol=symbol,
            market_context=market_context,
            patterns=analysis.get("patterns", []),
        )

        return {
            "symbol": symbol,
            "score": score_breakdown["total_score"],
            "confidence": score_breakdown["confidence"],
            "factors": score_breakdown["factors"],
            "entry_price": levels["entry_price"],
            "stop_loss": levels["stop_loss"],
            "target_1": levels["target_1"],
            "target_2": levels["target_2"],
            "target_3": levels["target_3"],
            "rr_ratio": levels["rr_ratio"],
            "quantity": position_info["quantity"],
            "investment": position_info["investment"],
            "risk_amount": position_info["risk_amount"],
            "trade_worthy": trade_worthy,
            "decision": "ENTER" if trade_worthy else "PASS",
            "reason": self.get_decision_reason(
                trade_worthy,
                score_breakdown,
                levels,
                portfolio_state,
                symbol,
                market_context,
                position_info,
            ),
            "patterns": analysis.get("patterns", []),
            "weekly_ema_status": weekly_ema_status,  # above/below (for Discord)
            "weekly_ema_reason": weekly_ema_reason,  # detailed reason (for Discord)
            "ema_penalty_applied": ema_penalty_applied,
            "position_tier": position_tier,
            "ml_model_active": ml_model_active,
            "rsi": analysis.get("rsi"),
            "macd": analysis.get("macd"),
            "volume_ratio": analysis.get("volume_ratio"),
            "atr": analysis.get("atr"),
            "pattern_count": analysis.get("pattern_count", 0),
        }

    def should_enter_trade(
        self,
        score_breakdown: dict,
        levels: dict,
        portfolio_state: dict,
        position_info: dict,
        symbol: str = None,
        market_context: dict = None,
        patterns: list = None,
    ) -> bool:
        """Final decision gate with multiple checks

        Bearish threshold is now scaled proportionally to market strength:
        - Strength 0-2: threshold = 70 (capitulation = opportunity)
        - Strength 3-5: threshold = 73-75 (weak bearish)
        - Strength 6-8: threshold = 76-78 (moderate bearish)
        - Strength 9-10: threshold = 79-80 (strong bearish/crash)

        This avoids the 80-point hard ceiling that was blocking all trades
        in moderately bearish markets (strength 5-8).
        """
        market_context = market_context or {}
        trend = market_context.get("trend", "sideways")
        market_strength = market_context.get("strength", 5.0)
        patterns = patterns or []

        # --- STRUCT-02: Per-Pattern Score Thresholds ---
        pattern_thresholds = {
            'bullish_ma_crossover':  65,
            'macd_bullish_crossover': 68,
            'pullback_in_uptrend':   72,
            'breakout_with_volume':  70,
            'trend_strength':        72,
            'rsi_oversold_bounce':   68,
            'stochastic_oversold':   68,
            'strong_momentum':       68,
        }

        # --- FEAT-09: Adaptive Confidence Thresholds ---
        # Uses cache built once by prime_adaptive_thresholds() before the scan loop.
        # Avoids per-stock DB queries that exhaust the connection pool mid-scan.
        if hasattr(self, '_cached_pattern_thresholds') and self._cached_pattern_thresholds:
            pattern_thresholds.update(self._cached_pattern_thresholds)

        # Determine base threshold based on patterns detected
        custom_thresholds = [pattern_thresholds[p] for p in patterns if p in pattern_thresholds]
        base_threshold = max(custom_thresholds) if custom_thresholds else self.min_confidence_score

        if trend == "bearish":
            # Scaled threshold: 70 + (strength * 2), capped at 80
            # Strength 7.95 → threshold ~76 (was 80)
            # Strength 3 → threshold ~73 (was 75)
            effective_threshold = base_threshold + min(10, market_strength * 2)
            logger.debug(
                f"[BearishThreshold] Market strength={market_strength:.1f} → "
                f"threshold={effective_threshold:.1f} (base={base_threshold})"
            )
        else:
            effective_threshold = base_threshold

        if score_breakdown["total_score"] < effective_threshold:
            logger.debug(
                f"[ScoreGuard] {symbol}: score {score_breakdown['total_score']} "
                f"< threshold {effective_threshold:.1f} (base={base_threshold}) — skipping"
            )
            return False

        # --- FEAT-03: Market Regime Guard per Pattern ---
        pattern_market_requirements = {
            'pullback_in_uptrend': ['bullish'],          # Only in uptrends
            'breakout_with_volume': ['bullish'],          # Breakouts need trend
            'bullish_ma_crossover': ['bullish', 'sideways'],
            'macd_bullish_crossover': ['bullish', 'sideways'],
        }

        for pattern in patterns:
            allowed_trends = pattern_market_requirements.get(pattern)
            if allowed_trends is not None and trend not in allowed_trends:
                logger.info(
                    f"[RegimeGuard] {symbol}: pattern '{pattern}' not allowed in "
                    f"'{trend}' market (requires {allowed_trends}) — skipping"
                )
                return False

        if symbol and self.db:
            from models.database import Trade
            from datetime import datetime, timedelta

            existing = (
                self.db.query(Trade)
                .filter(Trade.symbol == symbol, Trade.status == "OPEN")
                .first()
            )
            if existing:
                logger.debug(f"Duplicate guard: {symbol} already held — skipping")
                return False

            # 24h cooldown for same-symbol re-entry
            recent_closed = (
                self.db.query(Trade)
                .filter(Trade.symbol == symbol, Trade.status == "CLOSED")
                .order_by(Trade.exit_date.desc())
                .first()
            )
            if recent_closed and recent_closed.exit_date:
                if (datetime.now(IST).replace(tzinfo=None) - recent_closed.exit_date) < timedelta(hours=24):
                    logger.debug(f"Cooldown guard: {symbol} exited recently (less than 24h) — skipping")
                    return False

        max_pos = int(os.getenv("MAX_POSITIONS", 7))
        if portfolio_state["positions_count"] >= max_pos:
            return False

        # --- RISK MANAGER VALIDATION ---
        if self.risk_manager:
            valid, reason = self.risk_manager.validate_trade(portfolio_state, position_info)
            if not valid:
                logger.info(f"[RiskGuard] {symbol} blocked: {reason}")
                return False

        if position_info["quantity"] <= 0:
            return False

        # --- FEAT-01: Brokerage-Adjusted R:R Gating ---
        net_t1_pnl, t1_charges = self.calculate_net_pnl(
            levels["entry_price"], levels["target_1"], position_info["quantity"]
        )
        net_sl_pnl, sl_charges = self.calculate_net_pnl(
            levels["entry_price"], levels["stop_loss"], position_info["quantity"]
        )
        abs_net_sl = abs(net_sl_pnl)
        if abs_net_sl > 0:
            net_rr = net_t1_pnl / abs_net_sl
            if net_rr < 1.2:
                logger.info(
                    f"[NetRRGuard] {symbol} blocked: Brokerage-adjusted R:R ({net_rr:.2f}) < 1.2 "
                    f"(Net T1: ₹{net_t1_pnl:.2f}, Net SL: ₹{net_sl_pnl:.2f})"
                )
                return False

        # Brokerage validity check: ensure T1 profit > 2x estimated brokerage
        if t1_charges > 0 and net_t1_pnl < (t1_charges * 2):
            logger.debug(
                f"[BrokerageGuard] {symbol} blocked: Target1 net profit (₹{net_t1_pnl:.2f}) "
                f"< 2x charges (₹{t1_charges:.2f})"
            )
            return False

        if position_info["investment"] > portfolio_state["available_capital"] * 0.30:
            return False

        # === EARNINGS BLACKOUT ===
        # Skip stocks within EARNINGS_BLACKOUT_DAYS of their earnings date.
        # Earnings cause unpredictable gap moves that invalidate technical setups.
        if symbol and os.getenv('EARNINGS_BLACKOUT_DAYS', '5') != '0':
            try:
                from datetime import date
                blackout_days = int(os.getenv('EARNINGS_BLACKOUT_DAYS', '5'))
                ds = self.data_service
                if ds is None:
                    from services.data_service import DataService
                    ds = DataService()
                earnings_dates = ds.fetch_earnings_dates(symbol)
                today = date.today()
                for ed in earnings_dates:
                    days_diff = abs((ed - today).days)
                    if days_diff <= blackout_days:
                        logger.info(
                            f"[EarningsBlackout] {symbol}: earnings on {ed} "
                            f"({days_diff}d away) — entry blocked"
                        )
                        return False
            except Exception as e:
                logger.debug(f"[EarningsBlackout] {symbol}: check skipped ({e})")

        return True

    def get_decision_reason(
        self,
        trade_worthy: bool,
        score_breakdown: dict,
        levels: dict,
        portfolio_state: dict,
        symbol: str = None,
        market_context: dict = None,
        position_info: dict = None,
    ) -> str:
        """Generate human-readable decision reason"""
        market_context = market_context or {}
        trend = market_context.get("trend", "sideways")
        market_strength = market_context.get("strength", 5.0)

        if trade_worthy:
            return (
                f"Strong setup (score: {score_breakdown['total_score']}/100) "
                f"with {levels['rr_ratio']}:1 risk-reward"
            )

        # 1. Bearish Market Threshold check
        if trend == "bearish":
            # Dynamically scaled threshold: 70 + (strength * 2), capped at 80
            effective_threshold = 70 + min(10, market_strength * 2)
            if score_breakdown["total_score"] < effective_threshold:
                return (
                    f"Bearish market — score {score_breakdown['total_score']}/100 "
                    f"below elevated threshold ({effective_threshold:.1f})"
                )

        # 2. Base Score check
        if score_breakdown["total_score"] < self.min_confidence_score:
            return f"Setup quality insufficient (score: {score_breakdown['total_score']}/100)"

        # 3. Duplicate Guard
        if symbol and self.db:
            from models.database import Trade
            existing = (
                self.db.query(Trade)
                .filter(Trade.symbol == symbol, Trade.status == "OPEN")
                .first()
            )
            if existing:
                return f"Duplicate guard: {symbol} already held in portfolio"

        # 4. Position Limits
        max_pos = int(os.getenv("MAX_POSITIONS", 7))
        if portfolio_state["positions_count"] >= max_pos:
            return f"Maximum positions reached ({max_pos}/{max_pos})"

        # 5. Risk Manager validation
        if position_info and self.risk_manager:
            valid, reason = self.risk_manager.validate_trade(portfolio_state, position_info)
            if not valid:
                return reason

        # 6. Position Sizing constraints
        if position_info:
            if position_info["quantity"] <= 0:
                return "Position size too small (Risk management resulted in 0 shares)"

            # --- FEAT-01: Brokerage-Adjusted R:R Check ---
            net_t1_pnl, _ = self.calculate_net_pnl(
                levels["entry_price"], levels["target_1"], position_info["quantity"]
            )
            net_sl_pnl, _ = self.calculate_net_pnl(
                levels["entry_price"], levels["stop_loss"], position_info["quantity"]
            )
            abs_net_sl = abs(net_sl_pnl)
            if abs_net_sl > 0:
                net_rr = net_t1_pnl / abs_net_sl
                if net_rr < 1.2:
                    return f"Brokerage-adjusted R:R too low ({net_rr:.2f}:1)"

            if position_info["investment"] > portfolio_state["available_capital"] * 0.30:
                return "Investment exceeds 30% single-position capital limit"

        # 7. Earnings Blackout
        if symbol and os.getenv('EARNINGS_BLACKOUT_DAYS', '5') != '0':
            try:
                from datetime import date
                blackout_days = int(os.getenv('EARNINGS_BLACKOUT_DAYS', '5'))
                ds = self.data_service
                if ds is None:
                    from services.data_service import DataService
                    ds = DataService()
                earnings_dates = ds.fetch_earnings_dates(symbol)
                today = date.today()
                for ed in earnings_dates:
                    days_diff = abs((ed - today).days)
                    if days_diff <= blackout_days:
                        return f"Earnings blackout active (Earnings on {ed} is within {blackout_days}d)"
            except Exception:
                pass

        return "General constraints not met (Risk/Margin/Blackout)"

    def check_exit_conditions(
        self, trade, current_price: float, current_data: pd.DataFrame = None
    ) -> dict:
        """
        Determine if position should be exited.
        Supports partial exit at T1 — exits 50%, moves SL to breakeven.
        """
        # --- STOP LOSS ---
        # trade.stop_loss may have been ratcheted above entry_price by the trailing-stop
        # arming logic below, or moved to breakeven by the T1 partial-exit handler in
        # app.py — distinguish those cases so exit_reason/exit_type stay accurate for
        # Discord/email alerts and the learning engine.
        if current_price <= trade.stop_loss:
            if trade.stop_loss > trade.entry_price:
                reason, exit_type = "Trailing stop hit (profit protected)", "trailing_stop"
            elif trade.partially_exited and trade.stop_loss == trade.entry_price:
                reason, exit_type = "Breakeven stop hit (post-partial-exit)", "breakeven_stop"
            else:
                reason, exit_type = "Stop loss hit", "stop_loss"
            return {
                "action": "EXIT",
                "reason": reason,
                "exit_type": exit_type,
                "urgency": "immediate",
            }

        # --- PARTIAL EXIT AT TARGET 1 ---
        t1 = trade.target
        t2 = trade.target_2 if trade.target_2 else None

        if t2 and not trade.partially_exited and current_price >= t1:
            return {
                "action": "PARTIAL_EXIT",
                "reason": "Target 1 achieved — booking 50%, riding to T2",
                "exit_type": "partial_exit_t1",
                "urgency": "immediate",
                "new_stop_loss": trade.entry_price,
            }

        # --- FULL EXIT AT TARGET 2 ---
        if t2 and trade.partially_exited and current_price >= t2:
            return {
                "action": "EXIT",
                "reason": "Target 2 achieved — full exit",
                "exit_type": "target_2",
                "urgency": "immediate",
            }

        # --- FULL EXIT AT TARGET (no T2, legacy) ---
        if not t2 and current_price >= trade.target:
            return {
                "action": "EXIT",
                "reason": "Target achieved",
                "exit_type": "target",
                "urgency": "immediate",
            }

        # --- TRAILING STOP ---
        # Ratchets trade.stop_loss upward (never down) once price reaches +1R.
        # The STOP LOSS check above performs the actual exit on a later cycle if price
        # falls back — this reuses the same persist-via-session-commit mechanism already
        # used by the partial-exit breakeven-SL move, so no new DB field is needed.
        initial_sl = trade.initial_stop_loss if trade.initial_stop_loss else trade.stop_loss
        risk_per_share = trade.entry_price - initial_sl

        if risk_per_share > 0:
            unrealized_per_share = current_price - trade.entry_price
            if unrealized_per_share >= risk_per_share:
                locked_stop = trade.entry_price + (risk_per_share * 0.5)
                if locked_stop > trade.stop_loss:
                    logger.info(
                        f"[TrailingStop] {trade.symbol}: +1R reached — "
                        f"SL ratcheted ₹{trade.stop_loss:.2f} → ₹{locked_stop:.2f} (0.5R locked)"
                    )
                    trade.stop_loss = locked_stop

        # --- TIME STOP ---
        if trade.entry_date:
            entry_d = trade.entry_date.date()
            today_d = datetime.now(IST).replace(tzinfo=None).date()
            days_held = int(np.busday_count(entry_d, today_d))  # trading days, weekends excluded
        else:
            days_held = 0

        if days_held >= 7 and current_price < trade.entry_price * 0.97:
            return {
                "action": "EXIT",
                "reason": f"Time decay ({days_held} days with loss >3%)",
                "exit_type": "time_stop",
                "urgency": "normal",
            }

        if days_held >= 15:
            return {
                "action": "EXIT",
                "reason": f"Maximum holding period reached ({days_held} days)",
                "exit_type": "max_duration",
                "urgency": "normal",
            }

        return {
            "action": "HOLD",
            "reason": "All criteria within acceptable range",
            "exit_type": None,
            "urgency": None,
        }
