# Project One — AI Trading Bot: Overview

## What It Does

**project_one** is a fully automated AI-powered stock trading bot for the Indian market (Nifty/NSE). It continuously scans the market, evaluates potential trades using a machine learning model, manages an active portfolio with strict risk controls, and notifies via Discord and email. It runs as a Flask web app deployed on Render (Singapore region), backed by an **Aiven PostgreSQL** database.

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────┐
│                   Render Web Service                     │
│              (project-one-hd0i.onrender.com)             │
│                                                         │
│  ┌────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ app.py │  │  APScheduler │  │  Flask REST API     │  │
│  │(Flask) │  │  (5 jobs)    │  │  + Dashboard UI     │  │
│  └────────┘  └──────────────┘  └────────────────────┘  │
│        │                                                 │
│  ┌─────┼──────────────────────────────────────┐         │
│  │     ▼        Core Engines                  │         │
│  │  TradingBrain  PortfolioManager  LearningEngine │    │
│  │  MarketMonitor  RiskManager                 │         │
│  └─────────────────────────────────────────────┘         │
│        │                                                 │
│  ┌─────┼──────────────────────────────────────┐         │
│  │     ▼        Services Layer                │         │
│  │  DataService  DiscordService  EmailService  │         │
│  │  IndicatorService  ReportingService         │         │
│  └─────────────────────────────────────────────┘         │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
            ┌─────────────────────────┐
            │   Aiven PostgreSQL DB   │
            │  (cloud-hosted, 403 MCP)│
            └─────────────────────────┘
```

---

## Module Breakdown

### `app.py` — Flask App + Scheduler Hub (~62KB, central god file)
The entry point. Wires all components and schedules 5 background jobs:

| Job | Schedule | Purpose |
|-----|----------|---------|
| `scan_market_job()` | Market hours | Full market scan, AI evaluation |
| `monitor_positions_job()` | Frequent | Check stop-loss/targets on open trades |
| `premarket_scan_job()` | Pre-market | Watchlist setup before open |
| `end_of_day_analysis_job()` | EOD | Close trades, learn, report |
| `weekly_portfolio_cleanup_job()` | Weekly | Capital reset, circuit breaker |

### `core/` — Brain Modules

| File | Role |
|------|------|
| `trading_brain.py` (~34KB) | AI decision engine — evaluates setups, calculates scores (0-100), manages entry/exit signals. Key: `evaluate_opportunity()`, `should_enter_trade()`, `check_exit_conditions()` |
| `portfolio_manager.py` (~21KB) | Trade execution, position tracking, unrealized P&L, sector correlation, weekly loss circuit breaker |
| `learning_engine.py` (~18KB) | Self-improvement via ML — analyzes completed trades, retrains RandomForest model, tracks pattern statistics |
| `market_monitor.py` (~18KB) | Real-time position monitoring during market hours |
| `risk_manager.py` (~4.6KB) | Risk guardrails — position sizing, exposure limits |

### `services/` — External Integrations

| File | Role |
|------|------|
| `data_service.py` | Yahoo Finance API — prices, stock info, Nifty index, earnings dates |
| `discord_service.py` (~23KB) | Rich Discord notifications — trade alerts, daily summaries |
| `email_service.py` (~25KB) | Email reports and alerts |
| `indicator_service.py` | Technical indicators (EMA, RSI, etc.) |
| `reporting_service.py` | Saves scan reports and results to DB |

### `models/` — Database Schema (SQLAlchemy ORM)

| Model | Purpose |
|-------|---------|
| `Trade` | Individual trade records (entry/exit, P&L, strategy) |
| `Portfolio` | Portfolio snapshots over time |
| `LearningMetrics` | ML pattern performance statistics |
| `MarketDataCache` | Cached market data to reduce API calls |
| `MLModel` | Persisted trained RandomForest model |
| `EmailLog` | Email audit trail |
| `ScanReport / ScanResult / PatternOccurrence` | Full scan audit history |

---

## API Endpoints (selected)

| Route | Purpose |
|-------|---------|
| `GET /` | Dashboard UI |
| `GET /api/portfolio` | Portfolio state |
| `GET /api/trades` | Trade history |
| `GET /api/open-positions` | Live positions |
| `GET /health` | Health + ML training stats |
| `GET /api/performance` | Performance metrics |
| `GET /api/learning-insights` | AI learning state |
| `POST /admin/force-scan` | Manual market scan trigger |
| `POST /admin/flush-trades` | Admin: clear trades |
| `POST /admin/top-up-capital` | Add capital |

---

## Deployment Status (Render)

| Property | Value |
|----------|-------|
| **Service** | `project_one` (`srv-d63nj6m3jp1c73b84hn0`) |
| **URL** | https://project-one-hd0i.onrender.com |
| **Status** | ✅ Live (not suspended) |
| **Region** | Singapore |
| **Plan** | Free (1 instance, 1 worker, 2 threads) |
| **Runtime** | Python / Gunicorn |
| **Auto-deploy** | Yes (on `main` branch push) |
| **Last deploy** | May 16, 2026 — "add production database diagnostic tool" |

---

## Database Backend

- **Aiven PostgreSQL** (external cloud) — connected via `DATABASE_URL` env var
- **No Render-native Postgres** (confirmed: no Render Postgres instances found)
- **Aiven MCP**: Currently returning **403** — read-only access is blocked on the MCP server connection; direct SQL queries via Aiven console or psql still work
- The `diagnose_db.py` script exists locally for direct DB diagnostics

---

## Key Design Patterns

1. **Singleton pattern** for core engines (`_get_brain()`, `_get_learning_engine()`) — avoids re-initialization on each request
2. **Circuit breaker** — weekly loss limit stops trading automatically
3. **Partial exit at T1** — exits half position at Target 1, rides rest to T2
4. **Earnings blackout** — won't enter trades near earnings dates
5. **Sector correlation guard** — limits exposure to correlated positions
6. **ML feedback loop** — completed trades feed back into model retraining

---

## God Nodes (Most Connected Components)

1. `get_session()` — degree 31 (every component touches the DB)
2. `ScanReport` / `ScanResult` — degree 14 (scan pipeline hub)
3. `scan_market_job()` — degree 13 (orchestration center)
4. `PatternOccurrence` — degree 13 (ML learning hub)
