# Graph Report - personal-work  (2026-05-23)

## Corpus Check
- 57 files · ~87,563 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 990 nodes · 1322 edges · 73 communities (68 shown, 5 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 173 edges (avg confidence: 0.71)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2317654d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 71|Community 71]]

## God Nodes (most connected - your core abstractions)
1. `get_session()` - 36 edges
2. `TradingBrain` - 25 edges
3. `LearningEngine` - 22 edges
4. `MarketMonitor` - 22 edges
5. `ReportingService` - 21 edges
6. `PortfolioManager` - 20 edges
7. `ScanResult` - 18 edges
8. `DataService` - 18 edges
9. `scan_market_job()` - 17 edges
10. `PatternOccurrence` - 17 edges

## Surprising Connections (you probably didn't know these)
- `api_trades()` --calls--> `get_session()`  [INFERRED]
  app.py → models/database.py
- `test_database_setup()` --calls--> `init_database()`  [INFERRED]
  test_implementation.py → models/database.py
- `test_database_setup()` --calls--> `get_session()`  [INFERRED]
  test_implementation.py → models/database.py
- `test_reporting_service()` --calls--> `get_session()`  [INFERRED]
  test_implementation.py → models/database.py
- `test_reporting_service()` --calls--> `ReportingService`  [INFERRED]
  test_implementation.py → services/reporting_service.py

## Communities (73 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (16): admin_flush_all(), admin_top_up_capital(), api_trades(), initialize_portfolio(), AI Trading Bot - Main Flask Application Autonomous swing trading bot for Indian, Decorator to require a secret API key for sensitive endpoints, Add capital to the existing portfolio WITHOUT resetting trade history.     Use t, Add capital to the existing portfolio WITHOUT resetting trade history.     Use t (+8 more)

### Community 1 - "Community 1"
Cohesion: 0.14
Nodes (13): api_scan_history(), Get recent scan history, Get recent scan history, Get recent scan history, Reporting Service Handles scan data persistence and retrieval for analysis, Get recent scan reports          Args:             limit: Number of reports to r, Service for saving and retrieving scan data, Get pattern performance statistics          Args:             days: Number of da (+5 more)

### Community 2 - "Community 2"
Cohesion: 0.20
Nodes (11): MarketMonitor, Market Monitor Service Scans markets, fetches data, and detects trading opportun, Complete analysis of a single stock.          Args:             symbol: Stock sy, Market scanning and opportunity detection, Complete analysis of a single stock.          Args:             symbol: Stock sy, Analyze overall market trend (Nifty 50).          On failure, returns the last s, Fetch historical data for a stock, Calculate all technical indicators for a stock          Args:             data: (+3 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (37): Trading Brain - AI Decision Engine Makes intelligent trading decisions using ML, Check if stock price is above its 50-week EMA         Returns:             (pass, Check if stock price is above its 50-week EMA         Returns:             (pass, Returns (multiplier, tier_label) based on setup score., Calculate trading setup quality score (0-100)          Scoring:         - Techni, Returns (multiplier, tier_label) based on setup score., Calculate trading setup quality score (0-100)          Scoring:         - Techni, AI Decision Engine for trading (+29 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (19): DiscordService, Discord Webhook Alert Service Sends instant trade alerts to your Discord channel, Send alert when a trade is exited (full or partial).         Called from monitor, Send alert when 50% of position is booked at T1.         Includes TradingView ch, Send EOD daily summary at 4 PM IST.         Now includes weekly P&L and circuit, Sends trading alerts to Discord via webhook — zero cost, Dedicated alert the moment circuit breaker triggers mid-day.         Call this f, Send system health alert (+11 more)

### Community 5 - "Community 5"
Cohesion: 0.13
Nodes (12): DataService, Data Service Fetches market data from Yahoo Finance and NSE, Fetch stock info (market cap, sector, etc.), Fetch Nifty 50 index data with retry, Get current market price of a stock.         Uses 2d period — faster and suffici, Get current prices for multiple stocks in a single batch fetch.          Uses yf, Service for fetching market data, Check if Indian stock market is open (+4 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (39): PortfolioManager, Portfolio Manager Handles trade execution and portfolio management  Improvements, Portfolio and trade management, Get current portfolio state, Check if adding this symbol would breach the sector concentration limit., Check if weekly losses have exceeded the circuit breaker threshold.          Ret, Execute trade entry.         Runs two guards before entering:         1. Sector, Check if daily entries or closed losses exceed daily limits.          Returns: (+31 more)

### Community 7 - "Community 7"
Cohesion: 0.14
Nodes (12): IndicatorService, Technical Indicator Service Calculates various technical indicators for stock an, Calculate Stochastic Oscillator          Args:             data: DataFrame with, Calculate Average Directional Index (ADX)          Args:             data: DataF, Calculate technical indicators for stock data, Calculate Relative Strength Index (RSI)          Args:             prices: Serie, Calculate Volume Weighted Average Price (VWAP)          Args:             data:, Calculate On-Balance Volume (OBV)          Args:             data: DataFrame wit (+4 more)

### Community 8 - "Community 8"
Cohesion: 0.13
Nodes (15): LearningEngine, Learning Engine Self-improvement through trade analysis and ML optimization, Update running statistics for a pattern, Persist pattern statistics to database, Retrain ML model with latest trade data.         Requires minimum 20 closed trad, Self-improvement and trade analysis engine, Save trained ML model to database, Load historical pattern performance from database (+7 more)

### Community 9 - "Community 9"
Cohesion: 0.09
Nodes (22): 1. ML Cold Start Bonus (`core/trading_brain.py`), 2. Bearish Threshold Formula (`core/trading_brain.py:505-522`), 3. Weekly EMA: Binary Block → Penalty (`core/trading_brain.py`), 4. MIN_CONFIDENCE_SCORE Config (`render.yaml`), 5. System Status API Enhancement (`app.py`), 6. Discord Alert Improvements (`services/discord_service.py`), Changes Made, code:python (# Before: score = 53 (rejected at 80 threshold)) (+14 more)

### Community 10 - "Community 10"
Cohesion: 0.29
Nodes (7): api_pattern_performance(), api_trades_summary(), Get pattern performance statistics, Get pattern performance statistics, Get pattern performance statistics, Comprehensive trade summary with real P&L (after Groww charges).     No auth req, Comprehensive trade summary with real P&L (after Groww charges).     No auth req

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (18): 1. Local Development, 2. Environment Variables, 3. Deploy to Render.com, 🤖 AI Swing Trading Bot, API Endpoints, Calling Protected Endpoints, code:bash (# Clone the repository), code:bash (DATABASE_URL=postgresql://user:password@localhost:5432/tradi) (+10 more)

### Community 19 - "Community 19"
Cohesion: 0.12
Nodes (16): code:python (# Example configuration), code:python (if current_daily_drawdown >= MAX_DAILY_DRAWDOWN_PCT:), code:python (if is_system_halted():), code:python (# Instead of: fill_price = current_market_price), code:python (# Instead of: exit_price = current_market_price), code:python (MIN_AVG_VOLUME = 1_000_000 # 1 Million shares/day), code:python (import yfinance as yf), code:python (MAX_HOLD_DAYS = 10 # Force exit if held longer than 10 tradi) (+8 more)

### Community 20 - "Community 20"
Cohesion: 0.13
Nodes (14): API Endpoints (selected), `app.py` — Flask App + Scheduler Hub (~62KB, central god file), Architecture at a Glance, code:block1 (┌─────────────────────────────────────────────────────────┐), `core/` — Brain Modules, Database Backend, Deployment Status (Render), God Nodes (Most Connected Components) (+6 more)

### Community 23 - "Community 23"
Cohesion: 0.20
Nodes (7): Scan entire watchlist for opportunities.          Pre-fetches Nifty 20d return o, Rank the watchlist by relative strength, momentum, and volume trend.         Ret, Pre-market scan (8:45 AM IST) — runs BEFORE the market opens.          Identical, Scan entire watchlist for opportunities.          Pre-fetches Nifty 20d return o, Scan entire watchlist for opportunities.          Pre-fetches Nifty 20d return o, Pre-market scan (8:45 AM IST) — runs BEFORE the market opens.          Identical, Pre-market scan (8:45 AM IST) — runs BEFORE the market opens.          Identical

### Community 24 - "Community 24"
Cohesion: 0.50
Nodes (4): api_rejection_analysis(), Get analysis of why opportunities are being rejected, Get analysis of why opportunities are being rejected, Get analysis of why opportunities are being rejected

### Community 25 - "Community 25"
Cohesion: 0.16
Nodes (13): monitor_positions_job(), Position monitoring job - runs every 2 minutes during market hours, format_currency(), format_percentage(), get_ist_now(), is_market_hours(), is_trading_hours(), Utility helper functions (+5 more)

### Community 26 - "Community 26"
Cohesion: 0.16
Nodes (13): get_engine(), get_session(), init_database(), Initialize database connection and create tables, Initialize database connection and create tables, Get a new database session, Get a new database session, Get a new database session (+5 more)

### Community 27 - "Community 27"
Cohesion: 0.33
Nodes (9): main(), Test that Flask app can start, Test learning engine enhancements, Test database initialization, Test reporting service, test_api_endpoints(), test_database_setup(), test_learning_engine() (+1 more)

### Community 28 - "Community 28"
Cohesion: 0.05
Nodes (42): API Design, Async Routes, Async Test Client from Day 0, Chain Dependencies, code:block1 (fastapi-project), code:python (async def valid_post_id(post_id: UUID4) -> dict[str, Any]:), code:python (# parse_jwt_data is used 3 times but called only once), code:python (@router.get("/profiles/{profile_id}", response_model=Profile) (+34 more)

### Community 29 - "Community 29"
Cohesion: 0.05
Nodes (42): Basic Setup, Batch Messages, Best Practices, code:python (# Sync client from env), code:python (from fastapi import FastAPI, Response, Cookie, HTTPException), code:python (from upstash_ratelimit import Ratelimit, FixedWindow, Slidin), code:python (from fastapi import FastAPI, HTTPException, Request), code:python (ratelimits = {) (+34 more)

### Community 30 - "Community 30"
Cohesion: 0.05
Nodes (41): Alembic Migration Naming, Async Engine + Session, Bulk Insert, Bulk Operations, Bulk Update, Cascade Delete, code:python (from collections.abc import AsyncGenerator), code:python (from datetime import datetime) (+33 more)

### Community 31 - "Community 31"
Cohesion: 0.06
Nodes (32): Cell 1 — Install Dependencies, Cell 2 — Mount Google Drive (if using Step 4 above), Cell 3 — Load Secrets and Connect to DB, Cell 4 — Fetch Closed Trades, Cell 5 — Feature Extraction, Cell 6 — Train the Model, Cell 7 — Save Model to DB, Cell 8 — Trigger Server Reload (Optional) (+24 more)

### Community 32 - "Community 32"
Cohesion: 0.50
Nodes (4): admin_flush_trades(), Wipe all trade records (OPEN and CLOSED) and reset the portfolio snapshot.     T, Wipe all trade records (OPEN and CLOSED) and reset the portfolio snapshot.     T, Wipe all trade records (OPEN and CLOSED) and reset the portfolio snapshot.     T

### Community 33 - "Community 33"
Cohesion: 0.50
Nodes (4): api_open_positions(), Open positions API endpoint, Open positions API endpoint, Open positions API endpoint

### Community 34 - "Community 34"
Cohesion: 0.50
Nodes (4): api_portfolio(), Portfolio API endpoint, Portfolio API endpoint, Portfolio API endpoint

### Community 35 - "Community 35"
Cohesion: 0.50
Nodes (4): Weekly portfolio row cleanup — runs every Saturday at 6:00 AM IST.      Keeps on, Weekly portfolio row cleanup — runs every Saturday at 6:00 AM IST.      Keeps on, Weekly portfolio row cleanup — runs every Saturday at 6:00 AM IST.      Keeps on, weekly_portfolio_cleanup_job()

### Community 36 - "Community 36"
Cohesion: 0.07
Nodes (28): Change A: `end_of_day_analysis_job()`, Change B: New endpoint `/admin/reload-model`, code:block1 (1. Chunking fix (Option B)   ← 20 min, stops the crash immed), code:block10 (Day 1 (today):), code:block2 (yf.download(all_52_symbols, period='3mo', group_by='ticker')), code:block3 (split symbols list into chunks of 10), code:block4 (reload_ml_model():), code:block5 (the retrain_ml_model() call) (+20 more)

### Community 37 - "Community 37"
Cohesion: 0.08
Nodes (24): 1. Observe the Symptom, 2. Find Immediate Cause, 3. Ask: What Called This?, 4. Keep Tracing Up, 5. Find Original Trigger, Adding Stack Traces, code:dot (digraph when_to_use {), code:block2 (Error: git init failed in ~/project/packages/core) (+16 more)

### Community 38 - "Community 38"
Cohesion: 0.09
Nodes (22): computedHash, skillPath, source, sourceType, computedHash, skillPath, source, sourceType (+14 more)

### Community 39 - "Community 39"
Cohesion: 0.10
Nodes (20): Async Routes, code:block1 (src/), code:python (# BAD - blocks event loop), code:python (from pydantic import BaseModel, EmailStr, Field), code:python (async def get_current_user(token: str = Depends(oauth2_schem), code:python (from sqlalchemy.ext.asyncio import AsyncSession, async_sessi), code:python (from upstash_redis import Redis), code:python (from upstash_ratelimit import Ratelimit, SlidingWindow) (+12 more)

### Community 40 - "Community 40"
Cohesion: 0.10
Nodes (19): Bulletproofing Elements, Creation Log: Systematic Debugging Skill, Enhancement 1: TDD Reference, Extraction Decisions, Final Outcome, Initial Version, Iterations, Key Insight (+11 more)

### Community 41 - "Community 41"
Cohesion: 0.10
Nodes (19): code:block1 (NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST), code:block2 (For EACH component boundary:), code:bash (# Layer 1: Workflow), Common Rationalizations, Overview, Phase 1: Root Cause Investigation, Phase 2: Pattern Analysis, Phase 3: Hypothesis and Testing (+11 more)

### Community 42 - "Community 42"
Cohesion: 0.15
Nodes (12): Base, EmailLog, LearningMetrics, MarketDataCache, MLModel, Database models for AI Trading Bot Using SQLAlchemy ORM with PostgreSQL, Pattern and strategy performance metrics, Pattern and strategy performance metrics (+4 more)

### Community 43 - "Community 43"
Cohesion: 0.12
Nodes (16): 1. High Idle/Baseline Memory Footprint (~80% of total capacity), 1. The Crash Timeframe (around 17:00:00 UTC), 2. The Log Trigger, 2. The Memory Spike during Yahoo Finance Batch Download (`yf.download`), 3. Latent Danger: ML Model Retraining, code:block1 (2026-05-20 07:25:00,005 - app - INFO - MARKET SCAN STARTED), code:bash (gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads ), code:python (# In core/market_monitor.py:) (+8 more)

### Community 44 - "Community 44"
Cohesion: 0.21
Nodes (9): EmailService, Email Service using Resend Sends trade notifications and daily summaries, Email notification service using Resend, Send email notification for trade exit          Args:             trade: Trade o, Send end-of-day summary email          Args:             summary_data: Dict with, Send an email using Resend          Args:             subject: Email subject, Send a general alert email          Args:             title: Alert title, Send end-of-day email listing stocks that were evaluated but rejected today. (+1 more)

### Community 45 - "Community 45"
Cohesion: 0.12
Nodes (15): Call-graph collapse, Candidate card, code:html (<!doctype html>), code:html (<div class="rounded-lg border border-slate-200 bg-white p-4"), Cross-section (good for layered shallowness), Diagram patterns, Hand-built boxes-and-arrows (when Mermaid's layout fights you), Header (+7 more)

### Community 46 - "Community 46"
Cohesion: 0.12
Nodes (15): Applying the Pattern, code:typescript (function createProject(name: string, workingDirectory: strin), code:typescript (function initializeWorkspace(projectDir: string, sessionId: ), code:typescript (async function gitInit(directory: string) {), code:typescript (async function gitInit(directory: string) {), Defense-in-Depth Validation, Example from Session, Key Insight (+7 more)

### Community 47 - "Community 47"
Cohesion: 0.14
Nodes (13): API Key Auth via Header, code:python (from passlib.context import CryptContext), code:python (from datetime import datetime, timedelta, timezone), code:python (from fastapi import Depends, HTTPException, status), code:python (from fastapi import Depends, Header, HTTPException, status), code:python (from fastapi import FastAPI), code:python (from fastapi import FastAPI), CORS Configuration (+5 more)

### Community 48 - "Community 48"
Cohesion: 0.14
Nodes (12): code:dot (digraph when_to_use {), code:typescript (// ❌ BEFORE: Guessing at timing), code:typescript (// Tool ticks every 100ms - need 2 ticks to verify partial o), Common Mistakes, Condition-Based Waiting, Core Pattern, Implementation, Overview (+4 more)

### Community 49 - "Community 49"
Cohesion: 0.17
Nodes (11): Diagnose, Iterate on the loop itself, Non-deterministic bugs, Phase 1 — Build a feedback loop, Phase 2 — Reproduce, Phase 3 — Hypothesise, Phase 4 — Instrument, Phase 5 — Fix + regression test (+3 more)

### Community 50 - "Community 50"
Cohesion: 0.17
Nodes (12): admin_system_status(), daily_health_digest_job(), _get_consecutive_zero_trade_days(), Deep diagnostic snapshot of the system.     Returns DB counts, scoring config, s, Deep diagnostic snapshot of the system.     Returns DB counts, scoring config, s, Deep diagnostic snapshot of the system.     Returns DB counts, scoring config, s, Daily system health digest - runs at 3:35 PM IST (after market close).      Send, Daily system health digest - runs at 3:35 PM IST (after market close).      Send (+4 more)

### Community 51 - "Community 51"
Cohesion: 0.18
Nodes (11): api_market_context(), dashboard(), health(), Health check endpoint for UptimeRobot, Health check endpoint for UptimeRobot, Get current market context, Get current market context, Get current market context (+3 more)

### Community 52 - "Community 52"
Cohesion: 0.20
Nodes (9): 1. High-Level Architecture, 2. The Daily Code Flow (Chronological), 3. The API Layer, 4. Key Database Entities (`models/database.py`), A. Pre-Market Scan (8:45 AM IST), B. Market Scans (9:30 AM, 12:00 PM, 2:00 PM IST), C. Position Monitoring (Every 15 mins during market hours), D. End of Day Analysis (4:00 PM IST) (+1 more)

### Community 53 - "Community 53"
Cohesion: 0.22
Nodes (8): 1. In-process, 2. Local-substitutable, 3. Remote but owned (Ports & Adapters), 4. True external (Mock), Deepening, Dependency categories, Seam discipline, Testing strategy: replace, don't layer

### Community 54 - "Community 54"
Cohesion: 0.25
Nodes (5): Scan Report Models Track every market scan for analysis and learning, Overall scan session metadata, Individual stock analysis result from a scan, ScanReport, ScanResult

### Community 55 - "Community 55"
Cohesion: 0.29
Nodes (6): 1. Explore, 2. Present candidates as an HTML report, 3. Grilling loop, Glossary, Improve Codebase Architecture, Process

### Community 56 - "Community 56"
Cohesion: 0.33
Nodes (5): 1. Frame the problem space, 2. Spawn sub-agents, 3. Present and compare, Interface Design, Process

### Community 57 - "Community 57"
Cohesion: 0.33
Nodes (5): Language, Principles, Rejected framings, Relationships, Terms

### Community 58 - "Community 58"
Cohesion: 0.33
Nodes (5): Choose A, B, or C, code:block1 (PaymentError: Connection timeout to payments.api.com), Pressure Test 1: Emergency Production Fix, Scenario, Your Options

### Community 59 - "Community 59"
Cohesion: 0.33
Nodes (5): Choose A, B, or C, code:block1 (Expected: { status: 'completed', amount: 100 }), Pressure Test 2: Sunk Cost + Exhaustion, Scenario, Your Options

### Community 60 - "Community 60"
Cohesion: 0.33
Nodes (3): Portfolio, Portfolio snapshot at each point in time, Portfolio snapshot at each point in time

### Community 61 - "Community 61"
Cohesion: 0.40
Nodes (3): PatternOccurrence, Track when patterns appear and their context, Save pattern occurrence records

### Community 62 - "Community 62"
Cohesion: 0.33
Nodes (5): api_scan_details(), Get detailed results for a specific scan, Get detailed results for a specific scan, Get detailed results for a specific scan, Get detailed results for a specific scan          Args:             scan_id: Sca

### Community 63 - "Community 63"
Cohesion: 0.40
Nodes (4): Choose A, B, or C, Pressure Test 3: Authority + Social Pressure, Scenario, Your Options

### Community 64 - "Community 64"
Cohesion: 0.40
Nodes (5): _migrate_database(), Idempotent schema migrations.     Safely adds missing columns on every startup., Idempotent schema migrations.     Safely adds missing columns on every startup., Idempotent schema migrations.     Safely adds missing columns on every startup., Idempotent schema migrations.     Safely adds missing columns on every startup.

### Community 66 - "Community 66"
Cohesion: 0.50
Nodes (4): admin_flush_history(), Wipe scan history, pattern occurrences, and learning metrics.     Use this after, Wipe scan history, pattern occurrences, and learning metrics.     Use this after, Wipe scan history, pattern occurrences, and learning metrics.     Use this after

### Community 67 - "Community 67"
Cohesion: 0.50
Nodes (4): api_learning_insights(), Get AI learning insights, Get AI learning insights, Get AI learning insights

### Community 68 - "Community 68"
Cohesion: 0.50
Nodes (4): api_performance(), Performance metrics API, Performance metrics API, Performance metrics API

### Community 69 - "Community 69"
Cohesion: 0.50
Nodes (4): premarket_scan_job(), Pre-market scan — runs at 8:45 AM IST Mon-Fri.      Scans the watchlist using la, Pre-market scan — runs at 8:45 AM IST Mon-Fri.      Scans the watchlist using la, Pre-market scan — runs at 8:45 AM IST Mon-Fri.      Scans the watchlist using la

## Knowledge Gaps
- **300 isolated node(s):** `version`, `source`, `sourceType`, `skillPath`, `computedHash` (+295 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_session()` connect `Community 26` to `Community 0`, `Community 1`, `Community 6`, `Community 8`, `Community 10`, `Community 24`, `Community 25`, `Community 27`, `Community 32`, `Community 33`, `Community 34`, `Community 35`, `Community 42`, `Community 50`, `Community 51`, `Community 62`, `Community 66`, `Community 67`, `Community 68`, `Community 69`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `MarketMonitor` connect `Community 2` to `Community 5`, `Community 6`, `Community 7`, `Community 69`, `Community 50`, `Community 51`, `Community 23`, `Community 25`, `Community 26`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `TradingBrain` connect `Community 3` to `Community 5`, `Community 6`, `Community 69`, `Community 8`, `Community 42`, `Community 26`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 30 inferred relationships involving `get_session()` (e.g. with `test_database_setup()` and `test_reporting_service()`) actually correct?**
  _`get_session()` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `TradingBrain` (e.g. with `PortfolioManager` and `MLModel`) actually correct?**
  _`TradingBrain` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `LearningEngine` (e.g. with `Trade` and `LearningMetrics`) actually correct?**
  _`LearningEngine` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `MarketMonitor` (e.g. with `DataService` and `IndicatorService`) actually correct?**
  _`MarketMonitor` has 11 INFERRED edges - model-reasoned connections that need verification._