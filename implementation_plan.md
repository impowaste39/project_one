# Entry and Exit Conditions Review

I've conducted a deep review of the entry and exit conditions in `core/trading_brain.py` and `app.py`. Overall, the system has **excellent, professional-grade risk management** (capital caps, brokerage adjustments, partial exits, scaling by conviction). 

However, there are a few logical flaws and areas for improvement that we should address to maximize profitability and prevent premature stop-outs.

## Open Questions

> [!IMPORTANT]
> Please review the proposed changes below. Let me know if you approve all of them, or if you'd like to adjust the parameters (e.g., changing the 15-day max hold to 20 days, or keeping the tight SL).

## Review Findings & Proposed Changes

### 1. Exit Condition: Flawed Time Stop (Max Duration)
**Issue:** The system currently hard-exits any trade held for `12` days, regardless of profit. If a stock is slowly trending up and is at `+1.8R` on day 12, the bot will force exit, cutting your winners short.
**Proposed Change:** 
- Only apply the max duration time stop if the trade is **stagnant or in loss** (e.g., price is less than `+0.5R` profit).
- Extend the max holding period from 12 days to `15` or `20` days to allow swing trades more room to breathe.

### 2. Entry Condition: Stop Loss Selection is Too Tight
**Issue:** In `calculate_entry_exit_levels`, you calculate three SL candidates: 2x ATR, 8% fixed, and recent Swing Low. The code then selects the **tightest** of these: `stop_loss = max(candidates)`. If the swing low was just 2% away, the bot sets a 2% SL. For swing trading, picking the tightest SL often results in being whipsawed (stopped out before the stock moves up).
**Proposed Change:** 
- Instead of picking the tightest stop (`max()`), we should pick the **widest** stop within reason, capped by the 8% absolute floor (`percent_stop`). 
- Change `max(candidates)` to prioritize the Swing Low, but if it's *too* tight, fall back to the 2x ATR, with an absolute maximum risk of 8%.

### 3. Exit Condition: Trailing Stop Overriding Breakeven
**Issue:** At `Target 1` (+1.5R), the bot sells 50% and attempts to move the SL to breakeven (`trade.stop_loss = entry_price`). However, the `trailing_stop` logic permanently locks the SL at `+0.5R` once the price exceeds `+1.0R`. This means the remaining 50% will actually be stopped out at `+0.5R` instead of breakeven. 
**Proposed Change:** 
- This is actually a *good* thing (locking in `+0.5R` is better than breakeven), but the logic is conflicting. I propose we formalize this: once `Target 1` is hit, trail the stop loss to `+0.5R` explicitly, and remove the redundant breakeven assignment in `app.py`.

### 4. Entry Condition: Hardcoded Risk/Reward Ratio Check
**Issue:** The code calculates targets strictly as multiples of risk (`T1 = entry + 1.5*risk`). Because of this, the check `if levels["rr_ratio"] < 1.45:` is mathematically redundant and will always pass.
**Proposed Change:**
- This isn't breaking anything, but it's dead code. We should keep the check in case we implement dynamic, resistance-based targets in the future, but I propose we add a comment noting this.

---

### Implementation Plan

If you approve, I will modify `core/trading_brain.py` and `app.py` to:

#### [MODIFY] `core/trading_brain.py`
1. Update `calculate_entry_exit_levels` to choose a more resilient, wider stop-loss (e.g., prioritize 2ATR or Swing Low, whichever is lower, capped at an 8% drop).
2. Update `check_exit_conditions` to ignore the 12-day `max_duration` time stop if the stock is trending well (e.g., `unrealized_pnl > 0.5R`).

#### [MODIFY] `app.py`
1. Update `monitor_positions_job` where `Target 1` is hit to set the new stop loss to `+0.5R` explicitly (or another trailing value) instead of `trade.entry_price`, aligning it with the trailing stop logic.

Let me know if you would like me to proceed with these optimizations!
