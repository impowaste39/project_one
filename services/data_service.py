"""
Data Service
Fetches market data from Yahoo Finance and NSE
"""

import pytz
import yfinance as yf
import pandas as pd
import logging
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# In-memory cache for earnings dates — fetched once per 24h per symbol.
# Avoids slowing down every iteration of the scan loop with an .info API call.
_EARNINGS_CACHE = {}   # symbol -> {'dates': [...], 'fetched_at': datetime}
_EARNINGS_CACHE_TTL_HOURS = 24


class DataService:
    """Service for fetching market data"""

    def __init__(self):
        self.nifty_50 = [
            'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
            'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS',
            'LT.NS', 'AXISBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS', 'SUNPHARMA.NS',
            'TITAN.NS', 'NESTLEIND.NS', 'ULTRACEMCO.NS', 'BAJFINANCE.NS', 'HCLTECH.NS',
            'WIPRO.NS', 'ONGC.NS', 'NTPC.NS', 'POWERGRID.NS', 'M&M.NS',
            'TATASTEEL.NS', 'TATAMOTORS.NS', 'TECHM.NS', 'ADANIPORTS.NS', 'COALINDIA.NS',
            'BAJAJFINSV.NS', 'INDUSINDBK.NS', 'HEROMOTOCO.NS', 'DIVISLAB.NS', 'CIPLA.NS',
            'DRREDDY.NS', 'EICHERMOT.NS', 'GRASIM.NS', 'HINDALCO.NS', 'JSWSTEEL.NS',
            'BRITANNIA.NS', 'APOLLOHOSP.NS', 'TATACONSUM.NS', 'SHREECEM.NS', 'UPL.NS',
            'SBILIFE.NS', 'HDFCLIFE.NS', 'BAJAJ-AUTO.NS', 'ADANIENT.NS', 'BPCL.NS'
        ]

        self.nifty_next_50 = [
            'HAVELLS.NS', 'GODREJCP.NS', 'DABUR.NS', 'SIEMENS.NS', 'INDIGO.NS',
            'COLPAL.NS', 'PGHH.NS', 'NAUKRI.NS', 'ACC.NS', 'BOSCHLTD.NS',
            'PIDILITIND.NS', 'MARICO.NS', 'ABB.NS', 'BANKBARODA.NS', 'TVSMOTOR.NS',
            'AMBUJACEM.NS', 'GAIL.NS', 'DLF.NS', 'MCDOWELL-N.NS', 'SBICARD.NS'
        ]

        self.custom = [
            # ADDED FROM TOP SELECTIONS (sorted by PF desc)
            # "NATIONALUM.NS",
            "MRPL.NS",
            "SWIGGY.NS",
            "TARIL.NS",
            "KOTAKBANK.NS",
            # "ADANIPOWER.NS",
            "COALINDIA.NS",
            "BELRISE.NS",
            "USHAMART.NS",
            "CUB.NS",
            "ACMESOLAR.NS",
            # "VEDL.NS",
            "JIOFIN.NS",
            "HINDPETRO.NS",
            "KARURVYSYA.NS",
            "BPCL.NS",
            "LTF.NS",
            # "RITES.NS",
            # "SUZLON.NS",
            # "CANBK.NS",
            "INDIACEM.NS",
            "NYKAA.NS",
            "ICICIPRULI.NS",
            # "GAIL.NS",
            "SWANCORP.NS",
            "ITCHOTELS.NS",
            "ANGELONE.NS",
            # "TATAPOWER.NS",
            # "ONGC.NS",
            "LICI.NS",
            # "ASHOKLEY.NS",

            # PSU BANKS & FINANCE
            "SBIN.NS",
            "PNB.NS",
            "BANKBARODA.NS",
            "CANBK.NS",
            "UNIONBANK.NS",
            "MAHABANK.NS",
            "IDFCFIRSTB.NS",
            "IRFC.NS",
            "RECLTD.NS",
            "PFC.NS",

            # POWER / ENERGY
            "SUZLON.NS",
            "NTPC.NS",
            "NHPC.NS",
            "TATAPOWER.NS",
            "ADANIPOWER.NS",
            "BHEL.NS",
            "IOC.NS",
            "ONGC.NS",
            "GAIL.NS",
            "IEX.NS",

            # RAILWAYS / INFRA
            "RVNL.NS",
            "RITES.NS",
            "IRB.NS",
            "NCC.NS",

            # METALS & MATERIALS
            "SAIL.NS",
            "NMDC.NS",
            "HINDCOPPER.NS",
            "VEDL.NS",
            "JINDALSTEL.NS",
            "NATIONALUM.NS",

            # IT & TECH
            "WIPRO.NS",
            "REDINGTON.NS",
            "ROUTE.NS",

            # AUTO & INDUSTRIAL
            "ASHOKLEY.NS",
            "MOTHERSON.NS",

            # FMCG / CONSUMER
            "ITC.NS",
            "DABUR.NS",

            # PHARMA
            "AUROPHARMA.NS",
            "ZYDUSLIFE.NS",

            # HIGH BETA / MOMENTUM
            "IDEA.NS",
            "JPPOWER.NS",
            "BEL.NS"
        ]

    def get_watchlist(self, category: str = 'nifty50') -> list:
        if category == 'nifty50':
            return self.nifty_50
        elif category == 'nifty100':
            return self.nifty_50 + self.nifty_next_50
        else:
            return self.custom

    def fetch_stock_data(self, symbol: str, period: str = '3mo',
                         interval: str = '1d') -> pd.DataFrame:
        """
        Fetch historical data for a stock.
        Includes retry logic — if first fetch fails or returns empty,
        waits 2 seconds and tries once more before giving up.
        """
        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.history(period=period, interval=interval)

                if data is None or data.empty:
                    if attempt < max_retries:
                        logger.warning(
                            f"[Attempt {attempt}] Empty data for {symbol} — retrying in 2s...")
                        time.sleep(2)
                        continue
                    else:
                        logger.warning(
                            f"No data returned for {symbol} after {max_retries} attempts")
                        return None

                logger.debug(f"Fetched {len(data)} rows for {symbol}")
                return data

            except Exception as e:
                if attempt < max_retries:
                    logger.warning(
                        f"[Attempt {attempt}] Error fetching {symbol}: {e} — retrying in 2s...")
                    time.sleep(2)
                else:
                    logger.error(
                        f"Error fetching data for {symbol} after {max_retries} attempts: {e}")
                    return None

        return None

    def fetch_stock_info(self, symbol: str) -> dict:
        """Fetch stock info (market cap, sector, etc.)"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return {
                'symbol': symbol,
                'name': info.get('longName', ''),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'pb_ratio': info.get('priceToBook', 0),
                '52_week_high': info.get('fiftyTwoWeekHigh', 0),
                '52_week_low': info.get('fiftyTwoWeekLow', 0)
            }
        except Exception as e:
            logger.error(f"Error fetching info for {symbol}: {e}")
            return {}

    def fetch_nifty_index(self, period: str = '6mo') -> pd.DataFrame:
        """Fetch Nifty 50 index data with retry"""
        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                nifty = yf.Ticker('^NSEI')
                data = nifty.history(period=period)
                if data is None or data.empty:
                    if attempt < max_retries:
                        logger.warning(
                            f"[Attempt {attempt}] Empty Nifty data — retrying in 2s...")
                        time.sleep(2)
                        continue
                    return None
                return data
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(
                        f"[Attempt {attempt}] Nifty fetch error: {e} — retrying in 2s...")
                    time.sleep(2)
                else:
                    logger.error(
                        f"Error fetching Nifty index after {max_retries} attempts: {e}")
                    return None
        return None

    def get_current_price(self, symbol: str) -> float:
        """
        Get current market price of a stock.
        Uses 2d period — faster and sufficient for just getting latest price.
        """
        try:
            ticker = yf.Ticker(symbol)
            # FIXED: was '1d', now '2d' for reliability
            data = ticker.history(period='2d')
            if data is None or data.empty:
                return None
            return data['Close'].iloc[-1]
        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            return None

    def get_batch_prices(self, symbols: list) -> dict:
        """
        Get current prices for multiple stocks in a single batch fetch.

        Fetches in chunks of 10 to avoid OOM spikes on Render free tier (512MB).
        Each chunk is a single yf.download() call; results are merged into prices.
        Falls back to serial per-symbol fetch if all chunks fail.

        Args:
            symbols: List of stock symbols

        Returns:
            Dict mapping symbol -> latest close price
        """
        prices = {}

        if not symbols:
            return prices

        # --- CHUNKED BATCH FETCH (fast path) ---
        chunk_size = 10
        try:
            for i in range(0, len(symbols), chunk_size):
                chunk = symbols[i:i + chunk_size]
                try:
                    data = yf.download(
                        chunk,
                        period='2d',
                        interval='1d',
                        progress=False,
                        group_by='ticker',
                        auto_adjust=True,
                    )

                    if data is None or data.empty:
                        continue

                    if len(chunk) == 1:
                        # Single symbol: flat DataFrame
                        sym = chunk[0]
                        if 'Close' in data.columns and not data['Close'].empty:
                            prices[sym] = float(data['Close'].iloc[-1])
                    else:
                        # Multi-symbol: MultiIndex columns (ticker, field)
                        for sym in chunk:
                            try:
                                close = data['Close'][sym].dropna()
                                if not close.empty:
                                    prices[sym] = float(close.iloc[-1])
                            except (KeyError, IndexError):
                                pass  # Will be filled by serial fallback below

                except Exception as chunk_err:
                    logger.warning(
                        f"Batch price fetch failed for chunk {chunk}: {chunk_err}"
                    )
                    continue  # try remaining chunks; serial fallback catches misses

            logger.debug(
                f"Batch prices fetched: {len(prices)}/{len(symbols)} symbols"
            )

            # Serial fallback for any symbol not captured across all chunks
            missing = [s for s in symbols if s not in prices]
            if missing:
                logger.debug(f"Serial fallback for {len(missing)} symbols")
                for sym in missing:
                    try:
                        price = self.get_current_price(sym)
                        if price:
                            prices[sym] = price
                    except Exception:
                        pass

            return prices

        except Exception as e:
            logger.warning(
                f"Chunked batch fetch failed ({e}) — falling back to serial")

        # --- SERIAL FALLBACK ---
        for symbol in symbols:
            try:
                price = self.get_current_price(symbol)
                if price:
                    prices[symbol] = price
            except Exception as e:
                logger.error(f"Error fetching price for {symbol}: {e}")
                continue

        return prices

    def is_market_open(self) -> bool:
        """Check if Indian stock market is open"""
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        if now.weekday() >= 5:
            return False
        market_open = now.replace(hour=9, minute=15, second=0)
        market_close = now.replace(hour=15, minute=30, second=0)
        return market_open <= now <= market_close

    def get_market_status(self) -> dict:
        """Get detailed market status"""
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        is_open = self.is_market_open()
        market_open = now.replace(hour=9, minute=15, second=0)
        market_close = now.replace(hour=15, minute=30, second=0)

        if is_open:
            time_to_close = (market_close - now).seconds // 60
            status_msg = f"Market is OPEN. Closes in {time_to_close} minutes."
        elif now.weekday() >= 5:
            status_msg = "Market is CLOSED (Weekend)."
        elif now < market_open:
            time_to_open = (market_open - now).seconds // 60
            status_msg = f"Market OPENS in {time_to_open} minutes."
        else:
            status_msg = "Market is CLOSED for the day."

        return {
            'is_open': is_open,
            'current_time': now.strftime('%I:%M %p IST'),
            'status': status_msg,
            'is_weekend': now.weekday() >= 5
        }

    # ─── Relative Strength & Earnings ─────────────────────────────────────────

    def fetch_nifty_return(self, period_days: int = 20) -> float:
        """
        Fetch Nifty 50's price return over the last N trading days.
        Used for relative strength comparison.

        Returns:
            Float percentage return (e.g. 3.5 means +3.5%), or None on failure.
        """
        try:
            nifty = yf.Ticker('^NSEI')
            # Fetch slightly more days to account for weekends / holidays
            data = nifty.history(period=f'{period_days + 10}d', interval='1d')
            if data is None or data.empty or len(data) < 2:
                return None

            # Use the last `period_days` worth of actual trading bars
            data = data.tail(period_days)
            start_price = data['Close'].iloc[0]
            end_price = data['Close'].iloc[-1]

            if start_price <= 0:
                return None

            return_pct = ((end_price - start_price) / start_price) * 100
            logger.debug(f"Nifty {period_days}d return: {return_pct:.2f}%")
            return round(return_pct, 4)

        except Exception as e:
            logger.warning(f"Nifty return fetch failed: {e}")
            return None

    def fetch_earnings_dates(self, symbol: str) -> list:
        """
        Fetch upcoming/recent earnings dates for a stock.
        Results are cached for 24h per symbol to avoid API hammering.

        Returns:
            List of datetime.date objects, or [] if unavailable.
        """
        global _EARNINGS_CACHE

        # Check cache
        cached = _EARNINGS_CACHE.get(symbol)
        if cached:
            age_hours = (datetime.now() -
                         cached['fetched_at']).total_seconds() / 3600
            if age_hours < _EARNINGS_CACHE_TTL_HOURS:
                return cached['dates']

        dates = []
        try:
            ticker = yf.Ticker(symbol)
            calendar = ticker.calendar

            if calendar is not None:
                # yfinance returns calendar as a dict or DataFrame depending on version
                if isinstance(calendar, dict):
                    earnings_date = calendar.get('Earnings Date')
                    if earnings_date:
                        if hasattr(earnings_date, '__iter__') and not isinstance(earnings_date, str):
                            for d in earnings_date:
                                try:
                                    dates.append(pd.Timestamp(d).date())
                                except Exception:
                                    pass
                        else:
                            try:
                                dates.append(pd.Timestamp(
                                    earnings_date).date())
                            except Exception:
                                pass

            logger.debug(f"Earnings dates for {symbol}: {dates}")

        except Exception as e:
            logger.debug(f"Earnings fetch skipped for {symbol}: {e}")

        _EARNINGS_CACHE[symbol] = {
            'dates': dates, 'fetched_at': datetime.now()}
        return dates