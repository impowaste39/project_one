# Production-Ready Trading Bot Implementation Plan

This document outlines the steps to transition the AI trading bot from a paper-trading environment to a production-ready system suitable for real capital. It focuses on risk management, realistic simulations, and automated filtering.

---

## Phase 1: Realistic Friction Simulation
**Goal:** Ensure the strategy's P&L calculations account for real-world slippage (the difference between expected price and fill price) and broker commissions.

**Target File:** `core/portfolio_manager.py` (or where you execute/record trades)

**Implementation Steps:**
1. **Define Friction Constants:** Add configuration variables for expected friction.
   ```python
   # Example configuration
   SLIPPAGE_PCT = 0.001  # 0.1% slippage assumption
   COMMISSION_PER_TRADE = 0.00 # Assuming zero commission broker, but good to have
   ```
2. **Adjust Entry Prices:** When opening a position, artificially inflate the purchase price slightly.
   ```python
   # Instead of: fill_price = current_market_price
   fill_price = current_market_price * (1 + SLIPPAGE_PCT)
   ```
3. **Adjust Exit Prices:** When closing a position, artificially deflate the sale price.
   ```python
   # Instead of: exit_price = current_market_price
   exit_price = current_market_price * (1 - SLIPPAGE_PCT)
   ```
4. **Outcome:** Monitor the bot for another 10-20 trades. If the win rate and P&L remain positive despite the artificial friction, the strategy has a robust edge.

---

## Phase 2: Dynamic Fundamental Guardrails
**Goal:** Replace the manual curation of watchlists with automated checks that filter out low-liquidity or fundamentally weak stocks before any technical analysis occurs.

**Target File:** `core/market_monitor.py` (or the module responsible for generating the initial scan list)

**Implementation Steps:**
1. **Define Fundamental Thresholds:**
   ```python
   MIN_AVG_VOLUME = 1_000_000 # 1 Million shares/day
   MIN_MARKET_CAP = 1_000_000_000 # $1 Billion (Mid/Large cap only)
   ```
2. **Fetch Fundamental Data:** Integrate a library like `yfinance` to grab this data quickly during the initial scan.
   ```python
   import yfinance as yf

   def passes_fundamental_check(symbol):
       try:
           info = yf.Ticker(symbol).info
           vol = info.get('averageVolume', 0)
           cap = info.get('marketCap', 0)
           
           if vol < MIN_AVG_VOLUME or cap < MIN_MARKET_CAP:
               return False, f"Failed fundamentals: Vol={vol}, Cap={cap}"
           return True, "Passed"
       except Exception as e:
           return False, f"Data error: {e}"
   ```
3. **Pre-filter Loop:** Apply this check *before* passing symbols to the heavy ML or Technical Analysis logic to save CPU and API calls.

---

## Phase 3: The "Time-in-Trade" Timeout (Capital Velocity)
**Goal:** Prevent capital from being tied up in stagnant stocks. If a swing trade hasn't worked out within a reasonable timeframe, cut it to free up cash for better setups.

**Target File:** `core/trading_brain.py` (or wherever open positions are monitored daily)

**Implementation Steps:**
1. **Define Timeout Limit:**
   ```python
   MAX_HOLD_DAYS = 10 # Force exit if held longer than 10 trading days
   ```
2. **Calculate Trade Age:** During your daily position monitoring loop, calculate how long the trade has been open.
   ```python
   from datetime import datetime
   
   trade_age = (datetime.now().date() - position.entry_date.date()).days
   # Note: To be highly accurate, you might want to calculate 'trading days' excluding weekends/holidays.
   ```
3. **Implement Timeout Logic:**
   ```python
   if trade_age > MAX_HOLD_DAYS:
       execute_sell(symbol, reason="Time Decay / Stagnant Position")
   ```

---

## Phase 4: The Global Kill Switch (Circuit Breaker)
**Goal:** Automatically halt all trading activity if the portfolio experiences a severe drawdown, protecting the account from runaway losses due to market crashes or software bugs.

**Target File:** `core/risk_manager.py` and `app.py`

**Implementation Steps:**
1. **Define Max Drawdown:**
   ```python
   MAX_DAILY_DRAWDOWN_PCT = 0.05 # Halt system if account loses 5% in a single day
   ```
2. **Create System State Flag:** Add a boolean flag in your database or a config file (e.g., `SYSTEM_HALTED = False`).
3. **Monitor Daily P&L:** At the end of every trading day (or during continuous scans), calculate the total portfolio value compared to the start of the day.
4. **Trigger the Halt:**
   ```python
   if current_daily_drawdown >= MAX_DAILY_DRAWDOWN_PCT:
       # 1. Update database: SET SYSTEM_HALTED = True
       # 2. Send urgent Discord/email alert
       # 3. Optional: Close all open positions immediately at market
   ```
5. **Enforce the Halt:** In your main `app.py` routing or scanning loop, check the flag first.
   ```python
   if is_system_halted():
       return "Trading halted by Risk Manager. Manual reset required.", 403
   ```
