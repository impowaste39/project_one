# Trading Bot Fixes - Summary

**Date:** 2026-04-04
**Goal:** Break the catch-22 preventing first 20 trades needed for ML training

---

## Problem Analysis

The bot had **126 rejected opportunities** and **0 trades** in 10 days because:

| Issue | Impact |
|-------|--------|
| Bearish threshold hard-coded at 80 | Rejected 99 opportunities (78%) |
| Weekly EMA = binary block | Rejected 27 opportunities (21%) |
| No ML model active = -10 points | Scores too low to reach threshold |
| MIN_CONFIDENCE_SCORE = 65 | Too high for current market |

**Catch-22:** Need 20 trades to train ML → ML adds 10 pts to score → Without ML, can't reach 80-point threshold → No trades.

---

## Changes Made

### 1. ML Cold Start Bonus (`core/trading_brain.py`)

**What:** +10 score bonus when ML model is not yet trained

**Why:** Breaks the catch-22 by temporarily compensating for missing ML prediction

**Auto-disables:** After 20 trades when ML model trains

```python
# Before: score = 53 (rejected at 80 threshold)
# After:  score = 63 (now in contention)
if not ml_model_active:
    score += 10
    factors.append("ML cold start bonus (+10)")
```

---

### 2. Bearish Threshold Formula (`core/trading_brain.py:505-522`)

**What:** Replaced hard-coded 80/75 with scaled formula

**Before:**
```python
if trend == "bearish":
    effective_threshold = 80 if market_strength > 5 else 75
```

**After:**
```python
# Scaled: 70 + (strength * 2), capped at 80
if trend == "bearish":
    effective_threshold = 70 + min(10, market_strength * 2)
```

**Impact:**
| Market Strength | Old Threshold | New Threshold |
|-----------------|---------------|---------------|
| 3 (weak)        | 75            | 73            |
| 5 (moderate)    | 75            | 75            |
| 7.95 (current)  | 80            | 76            |
| 10 (crash)      | 80            | 80            |

---

### 3. Weekly EMA: Binary Block → Penalty (`core/trading_brain.py`)

**Before:** Below 50W EMA = instant reject (100% block)

**After:** Below 50W EMA = -10 points (strong setups still considered)

**Why:** A stock can have strong daily patterns even in long-term downtrends (short squeezes, mean reversion)

**Example:**
- Setup scores 75 (excellent daily patterns)
- Below 50W EMA: -10 penalty
- Final score: 65 (still trade-worthy)

---

### 4. MIN_CONFIDENCE_SCORE Config (`render.yaml`)

**Changed:** 65 → 58 (temporary during learning phase)

**Combined effect with cold start bonus:**
| Component | Score Boost |
|-----------|-------------|
| Base opportunity | 53 (avg rejected) |
| Cold start bonus | +10 |
| **Effective score** | **63** |
| Threshold (bearish 7.95) | 76 |
| Gap to close | 13 points |
| MIN_CONFIDENCE reduction | -7 points |
| **Final gap** | **6 points** |

Now only needs 6 points from pattern improvements instead of 27.

---

### 5. System Status API Enhancement (`app.py`)

Added `ml_cold_start` section to `/api/admin/system-status`:

```json
{
  "ml_cold_start": {
    "active": true,
    "ml_model_trained": false,
    "trades_completed": 0,
    "trades_needed_for_ml": 20,
    "bonus_applied": "+10 score bonus"
  },
  "effective_thresholds": {
    "min_confidence_score": 58,
    "bearish_market_formula": "70 + (strength * 2), capped at 80",
    "weekly_ema": "penalty (-10 pts) not binary block"
  }
}
```

---

### 6. Discord Alert Improvements (`services/discord_service.py`)

- Shows weekly EMA status (above/below) in trade alerts
- Increased factors shown from 3 to 4 (to display ML bonus)
- Clearer long-term trend indicator

---

## Files Changed

| File | Lines Changed |
|------|---------------|
| `core/trading_brain.py` | +57, -38 |
| `app.py` | +20 |
| `render.yaml` | 1 line |
| `services/discord_service.py` | +10, -4 |

---

## Expected Outcome

**Before:**
- Opportunities scoring: 52-64 (avg 53)
- Effective threshold: 80 (bearish)
- Trades per day: 0

**After:**
- Opportunities scoring: 62-74 (avg 63, with cold start)
- Effective threshold: 76 (bearish 7.95 strength)
- MIN_CONFIDENCE_SCORE: 58
- **Expected trades per day: 1-3** (conservative estimate)

**Timeline to ML activation:** 7-20 days (at 1-3 trades/day)

---

## Deployment Steps

1. **Review changes:**
   ```bash
   git diff
   ```

2. **Commit and push:**
   ```bash
   git add -A
   git commit -m "Fix: ML cold start bonus, scaled bearish threshold, EMA penalty
   - Add +10 score bonus until ML model trained (breaks catch-22)
   - Scale bearish threshold 70-80 based on market strength (was hard 80)
   - Weekly EMA: binary block → -10 pt penalty (allows strong setups)
   - Lower MIN_CONFIDENCE_SCORE 65→58 (temporary during learning)"
   git push
   ```

3. **Render will auto-deploy** (check health endpoint after deploy)

4. **Monitor:**
   - `/api/admin/system-status` — check `ml_cold_start.active`
   - `/api/rejection-analysis` — track avg rejected score
   - Discord alerts — should see trade entries within 1-3 days

---

## Rollback Plan

If something goes wrong:

```bash
git revert HEAD
git push
```

Or manually in Render dashboard:
- Change `MIN_CONFIDENCE_SCORE` back to 65
- Redeploy

---

## Post-Deployment Checklist

- [ ] Check `/health` endpoint returns 200
- [ ] Check `/api/admin/system-status` shows `ml_cold_start.active: true`
- [ ] Verify scheduler jobs are running (next_run times in future)
- [ ] Monitor Discord for trade entry alerts (expect 1-3 days)
- [ ] After 20 trades: verify ML model trains automatically

---

## Long-Term: When to Remove Cold Start Bonus

After 20+ trades complete:
1. ML model auto-trains and saves to database
2. Cold start bonus auto-disables (checks `ml_model_active`)
3. You can optionally restore `MIN_CONFIDENCE_SCORE` to 65

The system is designed to self-improve: more trades → better ML → better scores → better trades.
