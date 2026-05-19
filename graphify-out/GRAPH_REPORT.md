# Graph Report - personal-work  (2026-05-19)

## Corpus Check
- 29 files · ~69,755 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 534 nodes · 894 edges · 36 communities (32 shown, 4 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 173 edges (avg confidence: 0.71)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7c4de649`
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

## Communities (36 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.22
Nodes (8): admin_flush_history(), api_trades(), AI Trading Bot - Main Flask Application Autonomous swing trading bot for Indian, Decorator to require a secret API key for sensitive endpoints, Wipe scan history, pattern occurrences, and learning metrics.     Use this after, Wipe scan history, pattern occurrences, and learning metrics.     Use this after, Wipe scan history, pattern occurrences, and learning metrics.     Use this after, require_api_key()

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (33): Base, EmailLog, LearningMetrics, MarketDataCache, Portfolio, Portfolio snapshot at each point in time, Pattern and strategy performance metrics, Pattern and strategy performance metrics (+25 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (40): MarketMonitor, Market Monitor Service Scans markets, fetches data, and detects trading opportun, Complete analysis of a single stock.          Args:             symbol: Stock sy, Market scanning and opportunity detection, Complete analysis of a single stock.          Args:             symbol: Stock sy, Rank the watchlist by relative strength, momentum, and volume trend.         Ret, Pre-market scan (8:45 AM IST) — runs BEFORE the market opens.          Identical, Analyze overall market trend (Nifty 50).          On failure, returns the last s (+32 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (37): Trading Brain - AI Decision Engine Makes intelligent trading decisions using ML, Check if stock price is above its 50-week EMA         Returns:             (pass, Check if stock price is above its 50-week EMA         Returns:             (pass, Returns (multiplier, tier_label) based on setup score., Calculate trading setup quality score (0-100)          Scoring:         - Techni, Returns (multiplier, tier_label) based on setup score., Calculate trading setup quality score (0-100)          Scoring:         - Techni, AI Decision Engine for trading (+29 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (28): DiscordService, Discord Webhook Alert Service Sends instant trade alerts to your Discord channel, Send alert when a trade is exited (full or partial).         Called from monitor, Send alert when 50% of position is booked at T1.         Includes TradingView ch, Send EOD daily summary at 4 PM IST.         Now includes weekly P&L and circuit, Sends trading alerts to Discord via webhook — zero cost, Dedicated alert the moment circuit breaker triggers mid-day.         Call this f, Send system health alert (+20 more)

### Community 5 - "Community 5"
Cohesion: 0.13
Nodes (12): DataService, Data Service Fetches market data from Yahoo Finance and NSE, Fetch stock info (market cap, sector, etc.), Fetch Nifty 50 index data with retry, Get current market price of a stock.         Uses 2d period — faster and suffici, Get current prices for multiple stocks in a single batch fetch.          Uses yf, Service for fetching market data, Check if Indian stock market is open (+4 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (22): PortfolioManager, Portfolio Manager Handles trade execution and portfolio management  Improvements, Portfolio and trade management, Get current portfolio state, Check if adding this symbol would breach the sector concentration limit., Check if weekly losses have exceeded the circuit breaker threshold.          Ret, Execute trade entry.         Runs two guards before entering:         1. Sector, Check if daily entries or closed losses exceed daily limits.          Returns: (+14 more)

### Community 7 - "Community 7"
Cohesion: 0.14
Nodes (12): IndicatorService, Technical Indicator Service Calculates various technical indicators for stock an, Calculate Stochastic Oscillator          Args:             data: DataFrame with, Calculate Average Directional Index (ADX)          Args:             data: DataF, Calculate technical indicators for stock data, Calculate Relative Strength Index (RSI)          Args:             prices: Serie, Calculate Volume Weighted Average Price (VWAP)          Args:             data:, Calculate On-Balance Volume (OBV)          Args:             data: DataFrame wit (+4 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (26): LearningEngine, Learning Engine Self-improvement through trade analysis and ML optimization, Update running statistics for a pattern, Persist pattern statistics to database, Retrain ML model with latest trade data.         Requires minimum 20 closed trad, Self-improvement and trade analysis engine, Save trained ML model to database, Load historical pattern performance from database (+18 more)

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
Cohesion: 0.10
Nodes (20): Scan entire watchlist for opportunities.          Pre-fetches Nifty 20d return o, Risk Manager Handles position sizing and risk calculations, Calculate total portfolio risk from open positions          Args:             op, Calculate total portfolio risk from open positions          Args:             op, Risk management and position sizing, Calculate position size based on risk          Args:             capital: Availa, Validate if trade meets risk criteria          Args:             portfolio_state, RiskManager (+12 more)

### Community 24 - "Community 24"
Cohesion: 0.50
Nodes (4): api_rejection_analysis(), Get analysis of why opportunities are being rejected, Get analysis of why opportunities are being rejected, Get analysis of why opportunities are being rejected

### Community 25 - "Community 25"
Cohesion: 0.16
Nodes (14): dashboard(), format_currency(), format_percentage(), get_ist_now(), get_market_status_message(), is_market_hours(), is_trading_hours(), Utility helper functions (+6 more)

### Community 26 - "Community 26"
Cohesion: 0.13
Nodes (15): get_engine(), init_database(), _migrate_database(), Database models for AI Trading Bot Using SQLAlchemy ORM with PostgreSQL, Initialize database connection and create tables, Initialize database connection and create tables, Idempotent schema migrations.     Safely adds missing columns on every startup., Idempotent schema migrations.     Safely adds missing columns on every startup. (+7 more)

### Community 27 - "Community 27"
Cohesion: 0.33
Nodes (9): main(), Test that Flask app can start, Test learning engine enhancements, Test database initialization, Test reporting service, test_api_endpoints(), test_database_setup(), test_learning_engine() (+1 more)

### Community 28 - "Community 28"
Cohesion: 0.33
Nodes (6): get_session(), Get a new database session, Get a new database session, Get a new database session, initialize_portfolio(), Initialize portfolio with starting capital if not exists

### Community 29 - "Community 29"
Cohesion: 0.50
Nodes (4): admin_top_up_capital(), Add capital to the existing portfolio WITHOUT resetting trade history.     Use t, Add capital to the existing portfolio WITHOUT resetting trade history.     Use t, Add capital to the existing portfolio WITHOUT resetting trade history.     Use t

### Community 30 - "Community 30"
Cohesion: 0.50
Nodes (4): admin_flush_all(), Nuclear option: wipe ALL data — trades, scans, patterns, learning, portfolio., Nuclear option: wipe ALL data — trades, scans, patterns, learning, portfolio., Nuclear option: wipe ALL data — trades, scans, patterns, learning, portfolio.

### Community 31 - "Community 31"
Cohesion: 0.50
Nodes (4): api_scan_history(), Get recent scan history, Get recent scan history, Get recent scan history

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

## Knowledge Gaps
- **51 isolated node(s):** `allow`, `Problem Analysis`, `code:python (# Before: score = 53 (rejected at 80 threshold))`, `code:python (if trend == "bearish":)`, `code:python (# Scaled: 70 + (strength * 2), capped at 80)` (+46 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_session()` connect `Community 28` to `Community 0`, `Community 33`, `Community 2`, `Community 35`, `Community 34`, `Community 1`, `Community 32`, `Community 8`, `Community 10`, `Community 23`, `Community 24`, `Community 25`, `Community 26`, `Community 27`, `Community 29`, `Community 30`, `Community 31`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
- **Why does `TradingBrain` connect `Community 3` to `Community 2`, `Community 5`, `Community 6`, `Community 8`, `Community 23`, `Community 26`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Why does `MarketMonitor` connect `Community 2` to `Community 26`, `Community 23`, `Community 5`, `Community 7`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Are the 30 inferred relationships involving `get_session()` (e.g. with `test_database_setup()` and `test_reporting_service()`) actually correct?**
  _`get_session()` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `TradingBrain` (e.g. with `PortfolioManager` and `MLModel`) actually correct?**
  _`TradingBrain` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `LearningEngine` (e.g. with `Trade` and `LearningMetrics`) actually correct?**
  _`LearningEngine` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `MarketMonitor` (e.g. with `DataService` and `IndicatorService`) actually correct?**
  _`MarketMonitor` has 11 INFERRED edges - model-reasoned connections that need verification._