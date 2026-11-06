# WP2 Backtest Report — Exit Variant Analysis

Generated: 2026-11-07
Notional per trade: ₹25,000
Total signals: 544

## Baseline Performance (Original Stops & Targets)

| Metric | Value |
|--------|-------|
| Trades | 544 |
| Expectancy (R) | -0.5164 |
| Expectancy (₹) | -12910.07 |
| Profit Factor | 0.26 |
| Win Rate | 26.7% |
| Break-even Win Rate | 58.2% |
| Max Drawdown (R) | -288.6117 |
| Avg Win (R) | 0.6857 |
| Avg Loss (R) | -0.9532 |
| Avg R:R | 0.72 |
| Bootstrap CI | [-0.5889, -0.4443] |
| Bootstrap Significant | True |

## Exit Variant Comparison

| Variant | Expectancy (R) | Profit Factor | Win Rate | Max DD (R) | vs Baseline |
|---------|----------------|---------------|----------|------------|-------------|
| stop_1.5r | -0.5190 | 0.26 | 26.7% | -290.9821 | -0.0026 |
| stop_2.0r | -0.5245 | 0.26 | 26.7% | -293.9517 | -0.0081 |
| target_1.5r | -0.5070 | 0.27 | 26.7% | -284.6156 | +0.0094 |
| target_2.0r | -0.5062 | 0.28 | 26.7% | -284.1479 | +0.0102 |
| time_stop_7d | -0.3298 | 0.36 | 31.1% | -184.3009 | +0.1866 |
| time_stop_10d | -0.4069 | 0.29 | 27.2% | -223.7793 | +0.1095 |

## Walk-Forward Analysis

| Fold | Test Month | Train Trades | Test Trades | Baseline (R) | Best Variant | Best (R) | Improvement (R) |
|------|------------|--------------|-------------|--------------|--------------|----------|-----------------|
| 1 | 2026-09 | 298 | 144 | -0.7408 | time_stop_7d | -0.6157 | +0.1251 |
| 2 | 2026-10 | 442 | 73 | -0.6578 | time_stop_7d | -0.2399 | +0.4179 |
| 3 | 2026-11 | 515 | 29 | 0.0179 | stop_1.5r | 0.0179 | +0.0000 |

## Promotion Gate

| Criterion | Result |
|-----------|--------|
| Promote variant | NO |
| Wins in last 3 folds | 2 / 3 |
| Bootstrap significant | False |
| Mean improvement (R) | +0.1810 |

## Breakdown by Pattern

| breakout_with_volume | 574 | -0.5977 | 22.7% | 0.17 |
| bullish_ma_crossover | 1225 | -0.6077 | 20.4% | 0.20 |
| macd_bullish_crossover | 791 | -0.6380 | 20.1% | 0.18 |
| pullback_in_uptrend | 511 | -0.1261 | 49.7% | 0.70 |
| rsi_oversold_bounce | 217 | -0.9373 | 12.0% | 0.03 |
| stochastic_oversold | 280 | -0.3866 | 28.2% | 0.36 |
| strong_momentum | 2660 | -0.5117 | 26.3% | 0.24 |
| trend_strength | 518 | -0.3035 | 34.2% | 0.40 |

## Breakdown by Score Bucket

| <65 | 3129 | -0.4913 | 26.5% | 0.26 |
| 65-74 | 546 | -0.2772 | 36.6% | 0.48 |
| 75-84 | 105 | -0.8810 | 6.7% | 0.04 |
| 85+ | 28 | -0.6942 | 21.4% | 0.15 |

## Breakdown by Market Regime

| bullish | 903 | -0.1096 | 46.0% | 0.77 |
| sideways | 1813 | -0.4637 | 25.7% | 0.25 |
| bearish | 1092 | -0.7884 | 14.8% | 0.10 |

## Recommendation

❌ **Do not promote**: no variant shows consistent, significant improvement over baseline.

---
*Go/No-Go after WP2: if no rule variant shows net expectancy above zero with a bootstrap CI that excludes zero, the honest conclusion is that this strategy has no demonstrated edge.*