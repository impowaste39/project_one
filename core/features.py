"""
WP4 - Features v2: Single feature definition shared by training and inference.

All features are scale-free (ratios, percentages, flags) so they are
comparable across stocks and time. Both TradingBrain (inference) and
research/train_model.py (training) must call build_features() from here.
"""

from typing import Any

# Ordered list of feature names — must match between training and inference.
FEATURE_NAMES = [
    # Price relative features (scale-free)
    "atr_pct",           # ATR as % of price (volatility normalized)
    "macd_pct",          # MACD as % of price
    "dist_ema20_pct",    # Distance to EMA20 (%)
    "dist_ema50_pct",    # Distance to EMA50 (%)
    "dist_52w_high_pct", # Distance to 52-week high (%)
    "pos_in_20d_range_pct", # Position in 20-day range (0=low, 1=high)
    "gap_pct",           # Gap % from previous close
    "vol_trend_5d_20d",  # Volume trend: 5-day avg / 20-day avg
    "rsi_slope_3d",      # RSI slope over 3 days (points per day)

    # Market context features
    "nifty_trend",       # Nifty trend: 1=bullish, 0=sideways, -1=bearish
    "nifty_rsi",         # Nifty RSI (0-100)
    "vix_percentile",    # India VIX percentile (0-100), -1 if unavailable
    "rs_vs_nifty",       # Relative strength vs Nifty (20d return diff)
    "days_since_pattern",# Days since pattern triggered

    # Pattern flags (one per detectable pattern)
    "pat_bullish_ma_crossover",
    "pat_macd_bullish_crossover",
    "pat_pullback_in_uptrend",
    "pat_breakout_with_volume",
    "pat_trend_strength",
    "pat_rsi_oversold_bounce",
    "pat_stochastic_oversold",
    "pat_strong_momentum",
]

NUM_FEATURES = len(FEATURE_NAMES)


def build_features(analysis: dict, market_context: dict | None = None) -> list[float]:
    """
    Build feature vector from analysis dict and market context.

    Args:
        analysis: Stock analysis dict from market_monitor.scan_stock()
        market_context: Market context dict from market_monitor.get_market_context()

    Returns:
        List of float feature values in FEATURE_NAMES order.
        Missing values are filled with safe defaults (0.0 or -1.0).
    """
    market_context = market_context or {}

    # --- Price relative features ---
    current_price = analysis.get("current_price", 0.0) or 0.0
    atr = analysis.get("atr", 0.0) or 0.0
    macd = analysis.get("macd", 0.0) or 0.0
    ema20 = analysis.get("ema20", current_price) or current_price
    ema50 = analysis.get("ema50", current_price) or current_price
    high_52w = analysis.get("high_52w", current_price) or current_price
    low_20d = analysis.get("low_20d", current_price) or current_price
    high_20d = analysis.get("high_20d", current_price) or current_price
    prev_close = analysis.get("prev_close", current_price) or current_price
    volume_5d = analysis.get("volume_5d", 0.0) or 0.0
    volume_20d = analysis.get("volume_20d", 0.0) or 0.0
    rsi = analysis.get("rsi", 50.0) or 50.0
    rsi_3d_ago = analysis.get("rsi_3d_ago", rsi) or rsi

    atr_pct = (atr / current_price * 100.0) if current_price > 0 else 0.0
    macd_pct = (macd / current_price * 100.0) if current_price > 0 else 0.0
    dist_ema20_pct = ((current_price - ema20) / ema20 * 100.0) if ema20 > 0 else 0.0
    dist_ema50_pct = ((current_price - ema50) / ema50 * 100.0) if ema50 > 0 else 0.0
    dist_52w_high_pct = ((current_price - high_52w) / high_52w * 100.0) if high_52w > 0 else 0.0
    pos_in_20d_range_pct = (
        ((current_price - low_20d) / (high_20d - low_20d) * 100.0)
        if high_20d > low_20d else 50.0
    )
    gap_pct = ((current_price - prev_close) / prev_close * 100.0) if prev_close > 0 else 0.0
    vol_trend_5d_20d = (volume_5d / volume_20d) if volume_20d > 0 else 1.0
    rsi_slope_3d = ((rsi - rsi_3d_ago) / 3.0) if rsi_3d_ago else 0.0

    # --- Market context features ---
    trend = market_context.get("trend", "sideways")
    nifty_trend = 1.0 if trend == "bullish" else (-1.0 if trend == "bearish" else 0.0)
    nifty_rsi = market_context.get("nifty_rsi", 50.0) or 50.0
    vix_percentile = market_context.get("vix_percentile", -1.0)
    if vix_percentile is None:
        vix_percentile = -1.0
    rs_vs_nifty = analysis.get("rs_positive", None)
    if rs_vs_nifty is True:
        rs_vs_nifty = 1.0
    elif rs_vs_nifty is False:
        rs_vs_nifty = -1.0
    else:
        rs_vs_nifty = 0.0
    days_since_pattern = analysis.get("days_since_pattern", 0) or 0

    # --- Pattern flags (one per detectable pattern) ---
    patterns = analysis.get("patterns", []) or []
    if isinstance(patterns, str):
        import json
        try:
            patterns = json.loads(patterns)
        except Exception:
            patterns = []
    pat_flags = {
        "pat_bullish_ma_crossover": 1.0 if "bullish_ma_crossover" in patterns else 0.0,
        "pat_macd_bullish_crossover": 1.0 if "macd_bullish_crossover" in patterns else 0.0,
        "pat_pullback_in_uptrend": 1.0 if "pullback_in_uptrend" in patterns else 0.0,
        "pat_breakout_with_volume": 1.0 if "breakout_with_volume" in patterns else 0.0,
        "pat_trend_strength": 1.0 if "trend_strength" in patterns else 0.0,
        "pat_rsi_oversold_bounce": 1.0 if "rsi_oversold_bounce" in patterns else 0.0,
        "pat_stochastic_oversold": 1.0 if "stochastic_oversold" in patterns else 0.0,
        "pat_strong_momentum": 1.0 if "strong_momentum" in patterns else 0.0,
    }

    features = [
        atr_pct,
        macd_pct,
        dist_ema20_pct,
        dist_ema50_pct,
        dist_52w_high_pct,
        pos_in_20d_range_pct,
        gap_pct,
        vol_trend_5d_20d,
        rsi_slope_3d,
        nifty_trend,
        nifty_rsi,
        vix_percentile,
        rs_vs_nifty,
        float(days_since_pattern),
        pat_flags["pat_bullish_ma_crossover"],
        pat_flags["pat_macd_bullish_crossover"],
        pat_flags["pat_pullback_in_uptrend"],
        pat_flags["pat_breakout_with_volume"],
        pat_flags["pat_trend_strength"],
        pat_flags["pat_rsi_oversold_bounce"],
        pat_flags["pat_stochastic_oversold"],
        pat_flags["pat_strong_momentum"],
    ]

    return [float(f) if f is not None else 0.0 for f in features]


def build_features_dict(analysis: dict, market_context: dict | None = None) -> dict[str, float]:
    """
    Build feature vector as a dict keyed by feature name.

    Convenience wrapper around build_features() for debugging and inspection.
    """
    values = build_features(analysis, market_context)
    return dict(zip(FEATURE_NAMES, values))


def validate_feature_vector(features: list[float]) -> bool:
    """
    Validate that a feature vector has the correct length and no NaN/inf values.

    Returns True if valid, False otherwise.
    """
    if len(features) != NUM_FEATURES:
        return False
    import math
    return all(isinstance(f, (int, float)) and math.isfinite(f) for f in features)
