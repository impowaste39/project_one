import argparse
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import time
import os
import sys

# Default Render API URL, can be overridden by environment variable
API_URL = os.getenv(
    "BOT_API_URL", "https://project-one-hd0i.onrender.com/api/admin/update-watchlist")
# Replace or use env
API_KEY = os.getenv("API_WEBHOOK_KEY", "your_secret_key_here")


def fetch_nifty500_symbols():
    """Fetch the latest Nifty 500 constituents from NSE website"""
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    print("Fetching latest Nifty 500 list from NSE...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))

        # Filter out DUMMY or placeholder symbols that NSE sometimes includes
        valid_symbols = df[~df['Symbol'].str.startswith('DUMMY')]

        symbols = [f"{sym}.NS" for sym in valid_symbols['Symbol'].tolist()]
        print(
            f"Successfully loaded {len(symbols)} symbols from NSE (filtered out {len(df) - len(valid_symbols)} dummy symbols).")
        return symbols
    except Exception as e:
        print(f"Failed to fetch Nifty 500 from NSE: {e}")
        print("Falling back to top 150 hardcoded list...")
        return get_fallback_symbols()


def get_fallback_symbols():
    """Fallback symbols if NSE download fails"""
    return [
        # 'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
        # 'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS',
        # 'LT.NS', 'AXISBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS', 'SUNPHARMA.NS',
        # 'TITAN.NS', 'NESTLEIND.NS', 'ULTRACEMCO.NS', 'BAJFINANCE.NS', 'HCLTECH.NS',
        # 'WIPRO.NS', 'ONGC.NS', 'NTPC.NS', 'POWERGRID.NS', 'M&M.NS',
        # 'TATASTEEL.NS', 'TATAMOTORS.NS', 'TECHM.NS', 'ADANIPORTS.NS', 'COALINDIA.NS',
        # 'BAJAJFINSV.NS', 'INDUSINDBK.NS', 'HEROMOTOCO.NS', 'DIVISLAB.NS', 'CIPLA.NS',
        # 'DRREDDY.NS', 'EICHERMOT.NS', 'GRASIM.NS', 'HINDALCO.NS', 'JSWSTEEL.NS',
        # 'BRITANNIA.NS', 'APOLLOHOSP.NS', 'TATACONSUM.NS', 'SHREECEM.NS', 'UPL.NS',
        # 'SBILIFE.NS', 'HDFCLIFE.NS', 'BAJAJ-AUTO.NS', 'ADANIENT.NS', 'BPCL.NS',
        # 'HAVELLS.NS', 'GODREJCP.NS', 'DABUR.NS', 'SIEMENS.NS', 'INDIGO.NS',
        # 'COLPAL.NS', 'PGHH.NS', 'NAUKRI.NS', 'ACC.NS', 'BOSCHLTD.NS',
        # 'PIDILITIND.NS', 'MARICO.NS', 'ABB.NS', 'BANKBARODA.NS', 'TVSMOTOR.NS',
        # 'AMBUJACEM.NS', 'GAIL.NS', 'DLF.NS', 'MCDOWELL-N.NS', 'SBICARD.NS',
        # 'PNB.NS', 'CANBK.NS', 'UNIONBANK.NS', 'IDFCFIRSTB.NS', 'IRFC.NS',
        # 'SUZLON.NS', 'NHPC.NS', 'TATAPOWER.NS', 'ADANIPOWER.NS', 'BHEL.NS',
        # 'RVNL.NS', 'RITES.NS', 'SAIL.NS', 'NMDC.NS', 'VEDL.NS'
    ]


def calculate_atr_percent(df, period=30):
    """Calculate average true range as a percentage of price"""
    if len(df) < period:
        return 0
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    atr = true_range.rolling(period).mean()
    atr_pct = (atr / df['Close']) * 100
    return atr_pct.iloc[-1]


def calculate_rsi(df, period=14):
    """Calculate RSI"""
    if len(df) < period:
        return pd.Series(index=df.index, dtype=float)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def backtest_swing_rule(df):
    """
    Backtests a simple swing rule:
    Buy: Close > 50 EMA and RSI crosses above 40
    Sell: RSI > 60 or Close < 50 EMA
    Returns dict with win_rate and profit_factor
    """
    if len(df) < 100:
        return {'win_rate': 0, 'profit_factor': 0, 'trades': 0}

    df = df.copy()
    df['50EMA'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['RSI'] = calculate_rsi(df)

    in_trade = False
    entry_price = 0
    wins = 0
    losses = 0
    gross_profit = 0
    gross_loss = 0

    for i in range(50, len(df)):
        close = df['Close'].iloc[i]
        ema50 = df['50EMA'].iloc[i]
        rsi = df['RSI'].iloc[i]
        prev_rsi = df['RSI'].iloc[i-1]

        if not in_trade:
            # Buy logic
            if close > ema50 and prev_rsi <= 40 and rsi > 40:
                in_trade = True
                entry_price = close
        else:
            # Sell logic: target +10%, stop -5%, or signal exit
            pnl = (close - entry_price) / entry_price
            if pnl >= 0.10 or pnl <= -0.05 or rsi > 60 or close < ema50:
                in_trade = False
                pnl = (close - entry_price) / entry_price
                if pnl > 0:
                    wins += 1
                    gross_profit += pnl
                else:
                    losses += 1
                    gross_loss += abs(pnl)

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    profit_factor = min((gross_profit / gross_loss) if gross_loss >
                        0 else (gross_profit if gross_profit > 0 else 0), 20.0)

    return {
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'trades': total_trades
    }


def process_universe(count=50):
    symbols = fetch_nifty500_symbols()
    results = []

    print(
        f"Downloading data for {len(symbols)} symbols. This may take a few minutes...")

    # Download batch data (much faster than looping)
    data = yf.download(
        symbols,
        period='2y',
        interval='1d',
        progress=True,
        group_by='ticker',
        auto_adjust=True
    )

    print("Analyzing symbols...")
    for sym in symbols:
        try:
            if len(symbols) == 1:
                df = data
            else:
                if sym not in data.columns.levels[0]:
                    continue
                df = data[sym].dropna(subset=['Close'])

            if len(df) < 150:
                continue

            # 0. Price Filter (affordable for small capital)
            ltp = df['Close'].iloc[-1]
            if not (50 <= ltp <= 500):
                continue

            # 1. Liquidity Filter
            # Average daily turnover (Close * Volume) last 30 days >= 5 Crore (50M INR)
            recent_turnover = (df['Close'].tail(
                30) * df['Volume'].tail(30)).mean()
            if recent_turnover < 50_000_000:
                continue

            # 2. Volatility Filter
            # ATR% between 1% and 4%
            atr_pct = calculate_atr_percent(df)
            if not (1.0 <= atr_pct <= 4.5):
                continue

            # 3. Backtest
            stats = backtest_swing_rule(df)

            if stats['trades'] < 3:
                continue
            if stats['profit_factor'] < 1.5:  # Only keep genuinely profitable patterns
                continue
            if stats['win_rate'] < 50 and stats['profit_factor'] < 1.8:
                continue

            results.append({
                'symbol': sym,
                'ltp': round(ltp, 2),
                'win_rate': stats['win_rate'],
                'profit_factor': stats['profit_factor'],
                'atr_pct': atr_pct,
                'trades': stats['trades']
            })

        except Exception as e:
            pass  # Skip on any calculation error

    # Sort primarily by Profit Factor, then by Win Rate
    sorted_results = sorted(results, key=lambda x: (
        x['profit_factor'], x['win_rate']), reverse=True)
    top_stocks = sorted_results[:count]

    final_symbols = [r['symbol'] for r in top_stocks]

    print("\n--- TOP SELECTIONS ---")
    for i, r in enumerate(top_stocks, 1):
        qty = int(5000 / r['ltp'])
        deployed = round(qty * r['ltp'], 1)
        print(f"{i}. {r['symbol']:<15} | LTP: ₹{r['ltp']:>6.1f} | Qty: {qty:>3} | Deployed: ₹{deployed:>6} | WR: {r['win_rate']:>5.1f}% | PF: {r['profit_factor']:>4.2f} | ATR: {r['atr_pct']:>4.1f}%")

    return final_symbols


def push_to_bot(symbols):
    """Send the generated watchlist to the live bot via API"""
    if API_KEY == "your_secret_key_here":
        print("\nWARNING: API_WEBHOOK_KEY is not set. Cannot push to production.")
        print("Set it using: export API_WEBHOOK_KEY='your_key'")
        return

    payload = {"symbols": symbols}
    headers = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}

    print(f"\nPushing {len(symbols)} symbols to {API_URL}...")
    try:
        response = requests.post(
            API_URL, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            print("✅ Successfully updated the bot's dynamic watchlist!")
        else:
            print(f"❌ Failed to update bot. HTTP {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Connection error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Generate dynamic universe and push to bot.')
    parser.add_argument('--count', type=int, default=50,
                        help='Number of stocks to select')
    args = parser.parse_args()

    print(
        f"Starting Universe Generation Pipeline (Target: {args.count} stocks)")

    start_time = time.time()
    final_symbols = process_universe(count=args.count)

    print(f"\nCompleted in {time.time() - start_time:.1f} seconds.")
    print(
        f"Selected {len(final_symbols)} out of requested {args.count} stocks.")
