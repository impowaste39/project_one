# Graph Report - personal-work  (2026-07-18)

## Corpus Check
- 4 files · ~6,762 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 102 nodes · 115 edges · 25 communities (7 shown, 18 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `055748f7`
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
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]

## God Nodes (most connected - your core abstractions)
1. `🤖 AI Swing Trading Bot` - 10 edges
2. `_get_brain()` - 6 edges
3. `main()` - 6 edges
4. `Review Findings & Proposed Changes` - 6 edges
5. `_send_error_alert_guarded()` - 5 edges
6. `scan_market_job()` - 5 edges
7. `monitor_positions_job()` - 5 edges
8. `_get_consecutive_zero_trade_days()` - 5 edges
9. `health()` - 4 edges
10. `Quick Start` - 4 edges

## Surprising Connections (you probably didn't know these)
- `health()` --calls--> `_get_consecutive_zero_trade_days()`  [EXTRACTED]
  app.py → app.py  _Bridges community 5 → community 0_

## Communities (25 total, 18 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (17): admin_reload_model(), end_of_day_analysis_job(), _get_brain(), _get_learning_engine(), health(), monitor_positions_job(), Manually trigger a market scan, Return the shared LearningEngine, binding it to the current DB session. (+9 more)

### Community 1 - "Community 1"
Cohesion: 0.15
Nodes (12): 🤖 AI Swing Trading Bot, API Endpoints, Calling Protected Endpoints, code:bash (curl -X POST https://your-app.onrender.com/api/trigger-scan ), code:block4 (ai-trading-bot/), Features, ⚠️ Important Notes, License (+4 more)

### Community 2 - "Community 2"
Cohesion: 0.18
Nodes (10): 1. Exit Condition: Flawed Time Stop (Max Duration), 2. Entry Condition: Stop Loss Selection is Too Tight, 3. Exit Condition: Trailing Stop Overriding Breakeven, 4. Entry Condition: Hardcoded Risk/Reward Ratio Check, Entry and Exit Conditions Review, Implementation Plan, [MODIFY] `app.py`, [MODIFY] `core/trading_brain.py` (+2 more)

### Community 3 - "Community 3"
Cohesion: 0.52
Nodes (6): ask_ollama(), fetch_ml_model_info(), fetch_pattern_summary(), fetch_recent_rejections(), fetch_trade_summary(), main()

### Community 4 - "Community 4"
Cohesion: 0.33
Nodes (3): api_portfolio(), AI Trading Bot - Main Flask Application Autonomous swing trading bot for Indian, Portfolio API endpoint

### Community 5 - "Community 5"
Cohesion: 0.33
Nodes (6): admin_system_status(), daily_health_digest_job(), _get_consecutive_zero_trade_days(), Deep diagnostic snapshot of the system., Daily system health digest - runs at 3:35 PM IST (after market close)., Count how many consecutive trading days have had zero trades entered

### Community 6 - "Community 6"
Cohesion: 0.33
Nodes (6): 1. Local Development, 2. Environment Variables, 3. Deploy to Render.com, code:bash (# Clone the repository), code:bash (DATABASE_URL=postgresql://user:password@localhost:5432/tradi), Quick Start

## Knowledge Gaps
- **18 isolated node(s):** `Features`, `Tech Stack`, `code:bash (# Clone the repository)`, `code:bash (DATABASE_URL=postgresql://user:password@localhost:5432/tradi)`, `3. Deploy to Render.com` (+13 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `🤖 AI Swing Trading Bot` connect `Community 1` to `Community 6`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Why does `Quick Start` connect `Community 6` to `Community 1`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **Why does `_get_brain()` connect `Community 0` to `Community 4`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **What connects `AI Trading Bot - Main Flask Application Autonomous swing trading bot for Indian`, `Send a Discord error alert at most once per cooldown window per job.`, `Return the shared TradingBrain, binding it to the current DB session.` to the rest of the system?**
  _49 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.125 - nodes in this community are weakly interconnected._