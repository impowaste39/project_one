# AI Trading Bot — Audit & Fix Log

**Purpose:** Paste this at the start of a new chat to resume exactly where this session left off.

---

## Project Overview

Autonomous swing trading bot for NSE (Indian stock market), combining technical
signals with ML-based scoring. Fully automated: scans, scores, enters, monitors,
and exits positions on a schedule.

**Stack:** Flask + APScheduler + SQLAlchemy + yfinance + scikit-learn (RandomForest)
**Hosting:** Render free tier — 512MB RAM, single Gunicorn worker
**Database:** Aiven PostgreSQL free tier — confirmed 20 connection limit (not 5, verified via Aiven console screenshot)
**Alerts:** Discord + Email (Resend)

**File structure:**
```
app.py                          — routes, scheduler jobs, admin endpoints
core/
  trading_brain.py              — scoring engine, entry/exit decision logic
  market_monitor.py             — scanning, indicator calc, pattern detection
  portfolio_manager.py          — capital tracking, trade entry/exit execution
  risk_manager.py                — position sizing, risk validation
  learning_engine.py            — pattern stats, ML retraining, performance reports
models/
  database.py                   — SQLAlchemy models (Trade, Portfolio, MLModel, etc.)
  scan_report.py                — ScanReport, ScanResult, PatternOccurrence models
services/
  data_service.py               — price/earnings data fetching (yfinance)
  indicator_service.py          — RSI, MACD, ATR, ADX, etc.
  reporting_service.py          — scan data persistence, cleanup, analytics
  discord_service.py            — Discord webhook alerts
  email_service.py              — email alerts (Resend)
utils/helpers.py                — shared calculate_net_pnl(), IST time helpers
render.yaml / runtime.txt / requirements.txt
```

---

## Original Trigger

Dashboard showed an open MRPL position with `SCORE: 100` while sitting at
**-6.23% P&L (-₹1,633)**. This kicked off a full logic audit across the codebase.

---

## Audit Findings & Status

### 1. Dashboard `SCORE` column is misleading — **SKIPPED (user decision)**
`score` = `entry_score`, computed once at entry, never recalculated. Displayed
next to live P&L with no label distinguishing "setup quality on entry day" from
"how the trade is doing now." Not a logic bug — a UI/labeling issue.
**Decision: user chose to skip this fix and focus on real logic bugs.**

### 2. Breakeven trades counted as losses — **FIXED**
File: `core/learning_engine.py`, `update_pattern_statistics()`
```python
# Before
if trade.profit_loss and trade.profit_loss > 0:
    stats['wins'] += 1
else:
    stats['losses'] += 1

# After
if trade.profit_loss is not None and trade.profit_loss >= 0:
    stats['wins'] += 1
else:
    stats['losses'] += 1
```
Reasoning: `trade.profit_loss` alone is a truthy check — `0` is falsy in Python,
so breakeven trades fell into `else` (loss) even before the `>0`/`>=0` distinction
mattered. Fixed by checking `is not None` explicitly. User decision: breakeven = win.

**⚠️ Same bug exists in a second location — found but NOT yet fixed:**
File: `core/learning_engine.py`, `retrain_ml_model()`, line ~229
```python
label = 1 if trade.profit_loss and trade.profit_loss > 0 else 0
```
Same fix should apply here for consistency when we get to it.

### 3. Capital not released at partial exit — **FIXED**
Files: `app.py` (`monitor_positions_job`) + `core/portfolio_manager.py`

Problem: on `PARTIAL_EXIT` at Target 1, the `Trade` row updated correctly
(`partially_exited`, `partial_exit_price`, `partial_exit_qty`), but
`Portfolio.available_capital` was never credited with the freed cash — only
released in full at final exit. Caused false "insufficient capital" rejections
on new trades while a partial exit was pending.

**Design decision:** release principal immediately at partial exit; book P&L
(brokerage-adjusted, dual-leg) only once, at final exit — because charges can't
be split cleanly across two events.

`app.py` — in `PARTIAL_EXIT` handler, after `db.commit()`:
```python
# Before
                        trade.stop_loss = trade.entry_price  # Move SL to breakeven
                        db.commit()

# After
                        trade.stop_loss = trade.entry_price  # Move SL to breakeven
                        db.commit()

                        portfolio_mgr.credit_partial_exit_capital(trade, partial_qty)
```

`core/portfolio_manager.py` — new method:
```python
def credit_partial_exit_capital(self, trade: Trade, partial_qty: int):
    """Release the partial-exit leg's principal back to available capital,
    and reduce deployed capital by the same amount. No P&L booked here —
    that happens once, at final exit."""
    portfolio = self.db.query(Portfolio).order_by(
        Portfolio.timestamp.desc()
    ).first()
    if portfolio:
        principal_released = trade.entry_price * partial_qty
        portfolio.available_capital = portfolio.available_capital + principal_released
        portfolio.deployed_capital = portfolio.deployed_capital - principal_released
        portfolio.timestamp = datetime.now(IST).replace(tzinfo=None)
```

`core/portfolio_manager.py` — `exit_trade()`, adjust final-exit investment calc
so the already-released partial principal isn't double-counted:
```python
# Before
                investment = trade.entry_price * trade.quantity

# After
                remaining_qty = (trade.quantity - trade.partial_exit_qty) if trade.partially_exited else trade.quantity
                investment = trade.entry_price * remaining_qty
```

### 4. Earnings-date cache uses server-local time instead of IST — **FIXED**
File: `services/data_service.py`, `fetch_earnings_dates()`

3 edits — `IST` wasn't even defined in this file (rest of codebase uses IST
consistently, this file didn't):
```python
# Edit 1 — after "import pytz" near top of file
IST = pytz.timezone('Asia/Kolkata')

# Edit 2 — cache read (was line ~423-424)
# Before
            age_hours = (datetime.now() -
                         cached['fetched_at']).total_seconds() / 3600
# After
            age_hours = (datetime.now(IST) -
                         cached['fetched_at']).total_seconds() / 3600

# Edit 3 — cache write (was line ~457)
# Before
            'dates': dates, 'fetched_at': datetime.now()}
# After
            'dates': dates, 'fetched_at': datetime.now(IST)}
```
All three had to change together — mixing naive/aware datetimes here would
raise a `TypeError` on subtraction.

### 5. Bearish/high-volatility market penalty never actually applies — **FIXED**
**This was the most consequential bug found — directly inflated entry scores
in bad market conditions, likely a real contributor to the MRPL-style losses.**

File: `core/trading_brain.py`, `calculate_setup_score()`
```python
# Before
score += max(0, market_score)

# After
score += max(-10, market_score)
```
`market_score` can go negative from bearish trend (-5) and/or elevated/extreme
VIX (-5 to -10). The original `max(0, ...)` silently clamped any negative value
to zero — so bad market conditions contributed **nothing** to the score, despite
the code logging "Market in downtrend (penalty applied)" as if a penalty had
been applied. Capped at -10 (not left uncapped) because `should_enter_trade()`
already raises the *entry threshold* by up to +10 in bearish markets separately
— letting both penalties stack uncapped risked over-suppressing valid entries.

### 6. Python version mismatch across config files — **FIXED**
`runtime.txt` said `python-3.11.0`; `render.yaml` and `requirements.txt`
comments assumed 3.13. Standardized on **3.13** (user's dependencies were
tested against it).
```python
# Before
python-3.11.0

# After
python-3.13.0
```
(`render.yaml`'s `PYTHON_VERSION: 3.13.0` was already correct, unchanged.)

### 7. DB connection pool size vs. Aiven limit — **RETRACTED, no issue**
Code comment claimed Aiven's real limit was 20 (not the assumed 5). Verified via
Aiven console screenshot: **confirmed 20 connections**. Current pool config
(`pool_size=5, max_overflow=3` = 8 max) is well under the real limit. No change
needed.

---

## ML Model Status — IN PROGRESS, blocked on data (not a code bug)

**Discovery:** `retrain_ml_model()` in `learning_engine.py` is fully implemented
and self-gating (requires 20+ "clean" closed trades with all 5 feature columns
populated) — but it is **never called anywhere** in the codebase. No scheduled
job, no route triggers it. This is why ML scoring has been stuck in cold-start
heuristic mode. **Not yet fixed — no trigger mechanism decided/added.**

**History:** ML training was manually disabled several weeks ago via a direct
Postgres query:
```python
session.query(MLModel).filter_by(
    model_name='pattern_classifier', is_active=True
).update({'is_active': False})
```
This only flipped the flag — did **not** delete the old trained model row.
Confirmed via `verify_training_data.py` / active-model check: currently
`active model = None`.

**Data check (run 2026-08-15):**
- Total closed trades: 41
- Dirty trades (missing all 5 ML feature columns): 29 — all entered **before
  2026-06-22**, predating an earlier feature-schema-mismatch fix (6 features
  trained vs. 10 in production, logged in prior session)
- Clean trades (usable for training): **12** — need **20 minimum**
- Win/Loss split (all 41, old buggy label logic): 24 losses / 17 wins
- Pattern distribution: bullish_ma_crossover(22), pullback_in_uptrend(8),
  macd_bullish_crossover(8), trend_strength(2), breakout_with_volume(1)
- Clean data date range: starts 2026-06-22, latest 2026-07-29

**Decision: waiting for 8 more clean closed trades before retraining.**

**Open questions for next session:**
1. Once 20+ clean trades exist, decide *how* to trigger `retrain_ml_model()` —
   user has ruled out an on-Render scheduled job due to OOM risk on the 512MB
   free tier. Leaning toward retraining locally/offline against the Aiven DB
   and inserting the pickled model+scaler via script, so Render never runs
   `.fit()` directly. Not yet decided/implemented.
2. Apply the breakeven-as-win fix to `retrain_ml_model()`'s label logic
   (line ~229) — found in this session, not yet patched (see Issue #2 above).
3. Confirm whether the *old* deactivated model (pre-disable) is worth
   reactivating in the meantime while waiting for clean data — script was
   drafted but not run:
   ```python
   from models.database import get_session, MLModel

   with get_session() as session:
       latest = session.query(MLModel).filter_by(
           model_name='pattern_classifier'
       ).order_by(MLModel.created_at.desc()).first()

       if latest:
           latest.is_active = True
           print(f"Reactivated model id={latest.id}, accuracy={latest.accuracy}")
       else:
           print("No existing model found — nothing to reactivate")
   ```

---

## Files Fully Audited (no further issues expected unless code changes)
`trading_brain.py`, `market_monitor.py`, `database.py`, `scan_report.py`,
`risk_manager.py`, `portfolio_manager.py`, `data_service.py`,
`reporting_service.py`, `indicator_service.py`, `discord_service.py`,
`email_service.py`, `helpers.py`, `app.py`, `requirements.txt`, `render.yaml`,
`runtime.txt`

## Not Yet Applied to Live Code
All fixes above are **agreed and drafted** in this conversation but not yet
confirmed as deployed — verify against the live repo before assuming they're live.

## Immediate Next Steps
1. Apply fixes #2 (both spots), #3, #4, #5, #6 to the actual repo if not done yet
2. Decide + implement ML retrain trigger mechanism (local vs. remote)
3. Revisit dashboard `SCORE` labeling if desired later
4. Once 20+ clean trades exist, retrain and reactivate ML scoring
