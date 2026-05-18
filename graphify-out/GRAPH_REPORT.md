# Graph Report - personal-work  (2026-05-19)

## Corpus Check
- 28 files · ~66,579 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 449 nodes · 796 edges · 23 communities (19 shown, 4 thin omitted)
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 166 edges (avg confidence: 0.71)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `862db4b1`
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

## God Nodes (most connected - your core abstractions)
1. `get_session()` - 33 edges
2. `TradingBrain` - 24 edges
3. `LearningEngine` - 22 edges
4. `ReportingService` - 21 edges
5. `MarketMonitor` - 20 edges
6. `PortfolioManager` - 18 edges
7. `ScanResult` - 18 edges
8. `DataService` - 18 edges
9. `scan_market_job()` - 17 edges
10. `PatternOccurrence` - 17 edges

## Surprising Connections (you probably didn't know these)
- `test_reporting_service()` --calls--> `ReportingService`  [INFERRED]
  test_implementation.py → services/reporting_service.py
- `test_learning_engine()` --calls--> `LearningEngine`  [INFERRED]
  test_implementation.py → core/learning_engine.py
- `_get_brain()` --calls--> `TradingBrain`  [INFERRED]
  app.py → core/trading_brain.py
- `initialize_portfolio()` --calls--> `Portfolio`  [INFERRED]
  app.py → models/database.py
- `scan_market_job()` --calls--> `get_session()`  [INFERRED]
  app.py → models/database.py

## Communities (23 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (40): get_engine(), get_session(), init_database(), _migrate_database(), Initialize database connection and create tables, Initialize database connection and create tables, Idempotent schema migrations.     Safely adds missing columns on every startup., Idempotent schema migrations.     Safely adds missing columns on every startup. (+32 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (41): Base, LearningEngine, Learning Engine Self-improvement through trade analysis and ML optimization, Update running statistics for a pattern, Persist pattern statistics to database, Retrain ML model with latest trade data.         Requires minimum 20 closed trad, Self-improvement and trade analysis engine, Save trained ML model to database (+33 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (47): MarketMonitor, Market Monitor Service Scans markets, fetches data, and detects trading opportun, Complete analysis of a single stock.          Args:             symbol: Stock sy, Market scanning and opportunity detection, Scan entire watchlist for opportunities.          Pre-fetches Nifty 20d return o, Pre-market scan (8:45 AM IST) — runs BEFORE the market opens.          Identical, Analyze overall market trend (Nifty 50).          On failure, returns the last s, Fetch historical data for a stock (+39 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (23): Trading Brain - AI Decision Engine Makes intelligent trading decisions using ML, Check if stock price is above its 50-week EMA         Returns:             (pass, Returns (multiplier, tier_label) based on setup score., Calculate trading setup quality score (0-100)          Scoring:         - Techni, AI Decision Engine for trading, Load existing ML model or create new one, Calculate entry price, stop loss, and target levels, Complete evaluation of a trading opportunity.          Features:         - Weekl (+15 more)

### Community 4 - "Community 4"
Cohesion: 0.16
Nodes (15): DiscordService, Discord Webhook Alert Service Sends instant trade alerts to your Discord channel, Send alert when a trade is exited (full or partial).         Called from monitor, Send alert when 50% of position is booked at T1.         Includes TradingView ch, Send EOD daily summary at 4 PM IST.         Now includes weekly P&L and circuit, Sends trading alerts to Discord via webhook — zero cost, Dedicated alert the moment circuit breaker triggers mid-day.         Call this f, Send system health alert (+7 more)

### Community 5 - "Community 5"
Cohesion: 0.13
Nodes (12): DataService, Data Service Fetches market data from Yahoo Finance and NSE, Fetch stock info (market cap, sector, etc.), Fetch Nifty 50 index data with retry, Get current market price of a stock.         Uses 2d period — faster and suffici, Get current prices for multiple stocks in a single batch fetch.          Uses yf, Service for fetching market data, Check if Indian stock market is open (+4 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (21): PortfolioManager, Portfolio Manager Handles trade execution and portfolio management  Improvements, Portfolio and trade management, Get current portfolio state, Check if adding this symbol would breach the sector concentration limit., Check if weekly losses have exceeded the circuit breaker threshold.          Ret, Execute trade entry.         Runs two guards before entering:         1. Sector, Execute trade exit.          Args:             trade: Trade object to exit (+13 more)

### Community 7 - "Community 7"
Cohesion: 0.13
Nodes (12): IndicatorService, Technical Indicator Service Calculates various technical indicators for stock an, Calculate Stochastic Oscillator          Args:             data: DataFrame with, Calculate Average Directional Index (ADX)          Args:             data: DataF, Calculate technical indicators for stock data, Calculate Relative Strength Index (RSI)          Args:             prices: Serie, Calculate Volume Weighted Average Price (VWAP)          Args:             data:, Calculate On-Balance Volume (OBV)          Args:             data: DataFrame wit (+4 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (19): api_pattern_performance(), api_rejection_analysis(), api_scan_details(), api_scan_history(), Get recent scan history, Get detailed results for a specific scan, Get pattern performance statistics, Get analysis of why opportunities are being rejected (+11 more)

### Community 9 - "Community 9"
Cohesion: 0.09
Nodes (22): 1. ML Cold Start Bonus (`core/trading_brain.py`), 2. Bearish Threshold Formula (`core/trading_brain.py:505-522`), 3. Weekly EMA: Binary Block → Penalty (`core/trading_brain.py`), 4. MIN_CONFIDENCE_SCORE Config (`render.yaml`), 5. System Status API Enhancement (`app.py`), 6. Discord Alert Improvements (`services/discord_service.py`), Changes Made, code:python (# Before: score = 53 (rejected at 80 threshold)) (+14 more)

### Community 10 - "Community 10"
Cohesion: 0.21
Nodes (9): EmailService, Email Service using Resend Sends trade notifications and daily summaries, Email notification service using Resend, Send email notification for trade exit          Args:             trade: Trade o, Send end-of-day summary email          Args:             summary_data: Dict with, Send an email using Resend          Args:             subject: Email subject, Send a general alert email          Args:             title: Alert title, Send end-of-day email listing stocks that were evaluated but rejected today. (+1 more)

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (18): 1. Local Development, 2. Environment Variables, 3. Deploy to Render.com, 🤖 AI Swing Trading Bot, API Endpoints, Calling Protected Endpoints, code:bash (# Clone the repository), code:bash (DATABASE_URL=postgresql://user:password@localhost:5432/tradi) (+10 more)

### Community 19 - "Community 19"
Cohesion: 0.12
Nodes (16): code:python (# Example configuration), code:python (if current_daily_drawdown >= MAX_DAILY_DRAWDOWN_PCT:), code:python (if is_system_halted():), code:python (# Instead of: fill_price = current_market_price), code:python (# Instead of: exit_price = current_market_price), code:python (MIN_AVG_VOLUME = 1_000_000 # 1 Million shares/day), code:python (import yfinance as yf), code:python (MAX_HOLD_DAYS = 10 # Force exit if held longer than 10 tradi) (+8 more)

### Community 20 - "Community 20"
Cohesion: 0.13
Nodes (14): API Endpoints (selected), `app.py` — Flask App + Scheduler Hub (~62KB, central god file), Architecture at a Glance, code:block1 (┌─────────────────────────────────────────────────────────┐), `core/` — Brain Modules, Database Backend, Deployment Status (Render), God Nodes (Most Connected Components) (+6 more)

## Knowledge Gaps
- **51 isolated node(s):** `allow`, `Problem Analysis`, `code:python (# Before: score = 53 (rejected at 80 threshold))`, `code:python (if trend == "bearish":)`, `code:python (# Scaled: 70 + (strength * 2), capped at 80)` (+46 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_session()` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 6`, `Community 8`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Why does `scan_market_job()` connect `Community 2` to `Community 0`, `Community 8`, `Community 6`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `admin_force_scan()` connect `Community 6` to `Community 0`, `Community 8`, `Community 2`, `Community 3`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `get_session()` (e.g. with `test_database_setup()` and `test_reporting_service()`) actually correct?**
  _`get_session()` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `TradingBrain` (e.g. with `PortfolioManager` and `MLModel`) actually correct?**
  _`TradingBrain` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `LearningEngine` (e.g. with `Trade` and `LearningMetrics`) actually correct?**
  _`LearningEngine` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `ReportingService` (e.g. with `ScanReport` and `ScanResult`) actually correct?**
  _`ReportingService` has 10 INFERRED edges - model-reasoned connections that need verification._