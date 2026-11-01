# WP2 Backtest Report — Exit Variant Analysis

Generated: 2026-11-01
Notional per trade: ₹25,000
Total signals: 39

## Baseline Performance (Original Stops & Targets)

| Metric | Value |
|--------|-------|
| Trades | 39 |
| Expectancy (R) | -0.4069 |
| Expectancy (₹) | -10172.82 |
| Profit Factor | 0.29 |
| Win Rate | 38.5% |
| Break-even Win Rate | 68.2% |
| Max Drawdown (R) | -18.8451 |
| Avg Win (R) | 0.4358 |
| Avg Loss (R) | -0.9336 |
| Avg R:R | 0.47 |
| Bootstrap CI | [-0.6303, -0.1767] |
| Bootstrap Significant | True |

## Exit Variant Comparison

| Variant | Expectancy (R) | Profit Factor | Win Rate | Max DD (R) | vs Baseline |
|---------|----------------|---------------|----------|------------|-------------|
| stop_1.5r | -0.4646 | 0.27 | 38.5% | -21.0932 | -0.0577 |
| stop_2.0r | -0.4721 | 0.26 | 38.5% | -21.3864 | -0.0652 |
| target_1.5r | -0.4069 | 0.29 | 38.5% | -18.8451 | +0.0000 |
| target_2.0r | -0.4069 | 0.29 | 38.5% | -18.8451 | +0.0000 |
| time_stop_7d | -0.3173 | 0.30 | 28.2% | -12.7503 | +0.0896 |
| time_stop_10d | -0.3358 | 0.31 | 33.3% | -13.4357 | +0.0711 |

## Walk-Forward Analysis

| Fold | Test Month | Train Trades | Test Trades | Baseline (R) | Best Variant | Best (R) | Improvement (R) |
|------|------------|--------------|-------------|--------------|--------------|----------|-----------------|
| 1 | 2026-09 | 22 | 8 | -0.4027 | stop_1.5r | -0.3237 | +0.0790 |
| 2 | 2026-10 | 30 | 9 | -1.0290 | time_stop_7d | -0.3022 | +0.7268 |

## Promotion Gate

| Criterion | Result |
|-----------|--------|
| Promote variant | YES |
| Wins in last 3 folds | 2 / 2 |
| Bootstrap significant | True |
| Mean improvement (R) | +0.4029 |

## Breakdown by Pattern

| breakout_with_volume | 35 | -0.6248 | 20.0% | 0.06 |
| bullish_ma_crossover | 119 | -0.5728 | 26.9% | 0.21 |
| macd_bullish_crossover | 49 | -0.2324 | 53.1% | 0.48 |
| pullback_in_uptrend | 35 | 0.0398 | 62.9% | 1.14 |
| rsi_oversold_bounce | 14 | -1.0143 | 0.0% | 0.00 |
| stochastic_oversold | 28 | -0.2110 | 32.1% | 0.23 |
| strong_momentum | 203 | -0.3570 | 40.9% | 0.36 |
| trend_strength | 21 | -0.4181 | 47.6% | 0.17 |

## Breakdown by Score Bucket

| <65 | 217 | -0.4753 | 31.3% | 0.21 |
| 65-74 | 42 | -0.0490 | 59.5% | 0.86 |
| 75-84 | 7 | -1.0458 | 0.0% | 0.00 |
| 85+ | 7 | 0.4153 | 85.7% | 7.46 |

## Breakdown by Market Regime

| bullish | 63 | -0.0047 | 61.9% | 0.99 |
| sideways | 119 | -0.3215 | 36.1% | 0.32 |
| bearish | 91 | -0.7808 | 18.7% | 0.08 |

## Recommendation

✅ **Promote `N/A`**: beats baseline in last 3 folds with significant bootstrap CI.

---
*Go/No-Go after WP2: if no rule variant shows net expectancy above zero with a bootstrap CI that excludes zero, the honest conclusion is that this strategy has no demonstrated edge.*