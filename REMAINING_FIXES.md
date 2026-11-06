# Remaining fixes: handoff for the next engineer / AI agent

Project: autonomous NSE swing-trading bot (Flask + APScheduler + SQLAlchemy/psycopg3 + yfinance + scikit-learn).
Production: Render free web service + Aiven free PostgreSQL. Source of truth for behaviour is the code; evidence below
was read from the live deployment on 2026-10-24.

## Hard constraints (do not violate)
- Render free tier: 512 MB RAM (the service was OOM-killed ~daily), 1 gunicorn worker, 2 threads. Synchronous Flask only, no async.
- Aiven free tier: `max_connections` = 20 (verified). Engine pool is 5 + 3 overflow; keep it that way.
- Never read, edit or commit `.env` files or credentials.
- Minimal, targeted changes. No whole-file rewrites. Show before/after for each change and note data-loss risk.
- No heavy compute on Render (no training, no big backtests). Training happens offline and the model is inserted into `ml_models`.
- `main` auto-deploys on Render. Work on a branch, run `pytest tests/` and `python -m py_compile` on touched files first.
- The live start command is set in the Render dashboard, NOT `render.yaml` (`render.yaml` is not in effect).
- New DB columns need an idempotent step in `_migrate_database` (models/database.py). Never drop or truncate tables.

## Already done
- Fix 1 (deployed): `utils/memory.py` telemetry + post-job cleanup (`@memory_guard`), scheduler executor capped at 4 threads, pinned `requirements.txt`.
- Fix 2 (this patch): `calc_return_pct()` replaces the INITIAL_CAPITAL-based return; `/api/portfolio` computes it on read;
  top-up capital row now uses a naive IST timestamp (an aware datetime was stored 5.5 h early and could sort behind an older row,
  which the weekly cleanup could then delete).
- Verify fix 1 on a trading day: logs should show `MEM <job>: rss X MB -> Y MB` lines (first at the 08:45 IST pre-market scan).
  Success = no OOM `server_failed` events and post-job RSS staying flat instead of climbing.

## Remaining items (suggested order)

| ID | Issue and evidence | Proposed fix | Risk / decision |
|---|---|---|---|
| R1 | `scan_market_job` (app.py) calls `discord_service.send_trade_entry_alert()` BEFORE `portfolio_mgr.enter_trade()`. `enter_trade` can still refuse (max 2 per sector, weekly 3% breaker, daily breaker). The owner trades manually from alerts, so this creates alerts for trades the bot never recorded. | Alert only when `enter_trade` returned True. Wrap the alert in try/except with one retry. Email is already sent after commit as a second channel. | Low. Do this in the communication phase. |
| R2 | `RiskManager.validate_trade()` and `calculate_portfolio_risk()` have no callers anywhere, so the minimum-investment rule and the 10% portfolio-risk cap are not enforced. | Wire one gate into `TradingBrain.should_enter_trade`. Make min investment a percentage of capital (env, e.g. `MIN_INVESTMENT_PCT`). Portfolio-risk calc must use remaining quantity after a partial exit and the current stop (risk 0 once stop >= entry). | Medium: changes which trades are taken. Check current capital against any fixed minimum first. DECISION needed from owner. |
| R3 | Score-scaled sizing (up to 1.5x) is capped by a hardcoded `0.30` in two places in trading_brain.py, above `RiskManager.max_position_pct` (0.20 in volatile mode). Scaled risk can reach ~1.5x the configured risk. Sizing uses `available_capital`, not total equity. | Use the risk manager's cap in both places. Add an explicit ceiling on scaled risk (env). | Changes position sizes. DECISION: the ceiling. |
| R4 | `MIN_CONFIDENCE_SCORE` has no effect on entries: it is only a fallback when no detected pattern has its own threshold, and all 8 detectable patterns do (65 to 72). | Make it a floor: `max(pattern_threshold, MIN_CONFIDENCE_SCORE)`. Read `prime_adaptive_thresholds` first (it can override the per-pattern values). | None at today's values. |
| R5 | ML: the active `ml_models` row (created 2026-09-03) reports accuracy 0.20, earlier models 0.54 to 0.62. `scan_results.ml_score` is NULL on every stored row, so ML influence on entries is unverified. The pickle was trained under scikit-learn 1.9.0 and runs under 1.9.1 (now pinned). | First read how `ml_score` is computed and persisted (trading_brain predict path, reporting_service save). Then decide: deactivate the model (set `is_active=False`, do not delete the row) or retrain offline under the pinned scikit-learn and insert. Make sure `ml_score` is persisted so the effect can be measured. | DB write needs owner approval. DECISION: keep or deactivate. |
| R6 | gunicorn `--max-requests 100` (dashboard setting) recycles the worker roughly every 8 h at the UptimeRobot ping rate and can kill a job mid-run. | Revisit once the `MEM` lines show whether memory is flat. | Dashboard setting, not code. |
| R7 | `INITIAL_CAPITAL` is 5000 in app.py, 10000 in render.yaml. The reset endpoints (`flush-trades`, `flush-all`) restore capital to it, which would silently shrink a topped-up portfolio. | Owner sets `INITIAL_CAPITAL` in Render to the real contributed capital. | Env var, owner action. |
| R8 | `render.yaml` is not in effect (service was created manually) and still declares a Render Postgres with `DATABASE_URL` from it. If the service were ever Blueprint-synced, `DATABASE_URL` could repoint to an empty database. | Remove the `databases:` block and `fromDatabase`, or mark the file clearly as unused. | DATA-LOSS class: do not change until confirmed the service is not Blueprint-managed. |
| R9 | Security: API key compared with `!=`; `SECRET_KEY` has a default fallback; CORS is open; most read endpoints (portfolio, trades, equity curve) are public. | `hmac.compare_digest`; require `SECRET_KEY` in prod; restrict CORS. | DECISION: which reads stay public. |
| R10 | Dead code and doc drift: `target_3` is stored but never used by exits; `push_to_bot()` in scripts/swing_screener_cron.py posts to an endpoint not found in app.py; README describes a Nifty-50, 5-minute, 5000-capital setup (actual: custom 73-symbol watchlist, scan every 10 min); `alembic` and `python-json-logger` are pinned but never imported. | Implement or delete each; refresh README. | None. |
| R11 | `scan_market_job` runs the whole yfinance scan inside one `get_session()` block. One sample showed 0 idle-in-transaction sessions, so low priority. `pool_recycle=25` is aggressive. | Fetch market data with no session open, then use short sessions. Only if idle-in-transaction shows up in `pg_stat_activity`. | Low. |
| R12 | Same bug class as fix 2: grep for other DB writes using `datetime.now(IST)` without `.replace(tzinfo=None)` (DateTime columns are `timestamp without time zone`, Aiven session timezone is GMT). | Normalise to the naive-IST convention (`_ist_now()` in models/database.py). | Low. |
| R13 | Communication phase: scans stopped for ~2 weeks (Oct 9 to Oct 24) with no alert. | GitHub Actions watchdog that posts to Discord when the last `scan_reports` row is stale on a market day. Then the Discord and email issues the owner will list. | After R1. |

## Strategy context (for later, not for this round)
- The bot correctly stayed out of the market from early September: its own market-context reading was bearish and it raises entry thresholds to 74 to 80 in that state.
- Closed-trade results show charges are larger than the gross loss, and exits are dominated by time-decay and max-hold rather than targets. Do not change thresholds, stops or targets without a walk-forward backtest that reuses `calculate_net_pnl`.
- Roadmap for prediction quality: (1) weekly job that labels forward outcomes for every stored scan result, including rejected setups; (2) offline walk-forward backtester; (3) model v2 with calibrated probabilities, run in shadow mode before it influences entries; (4) log actual fill prices to measure slippage between alert and manual fill. Run heavy jobs on GitHub Actions or locally, never on Render.
