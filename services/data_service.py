"""
Data Service
Fetches market data from Yahoo Finance and NSE
"""

import yfinance as yf
import pandas as pd
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DataService:
    """Service for fetching market data"""

    def __init__(self):
        # Nifty 50 stocks (most liquid Indian stocks)
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

        # Additional quality stocks
        self.nifty_next_50 = [
            'HAVELLS.NS', 'GODREJCP.NS', 'DABUR.NS', 'SIEMENS.NS', 'INDIGO.NS',
            'COLPAL.NS', 'PGHH.NS', 'NAUKRI.NS', 'ACC.NS', 'BOSCHLTD.NS',
            'PIDILITIND.NS', 'MARICO.NS', 'ABB.NS', 'BANKBARODA.NS', 'TVSMOTOR.NS',
            'AMBUJACEM.NS', 'GAIL.NS', 'DLF.NS', 'MCDOWELL-N.NS', 'SBICARD.NS'
        ]

        # Curated watchlist: 60 Nifty-grade stocks only.
        # Reduced from 185 (Feb 2026 audit):
        #   - Dropped illiquid small-caps (Chemicals group, Services misc)
        #   - Dropped over-concentrated Banking (39→12, keep most liquid)
        #   - Dropped PSU project/infra stocks (poor swing characteristics)
        #   - Dropped auto ancillaries and IT micro-caps (unreliable yfinance data)
        # Selection criteria: Nifty 100 membership OR avg daily turnover > ₹100 Cr,
        # clean yfinance data history, readable trend structure for swing trading.
        # Target scan time: ~9s (down from ~28s). Redeploy after any changes here.
        # self.custom = [
        #     # --- BANKING & FINANCIAL — 12 stocks ---
        #     # Kept: top 5 private banks, top NBFC, 2 insurance, 2 lending only
        #     "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS",
        #     "BAJFINANCE.NS", "BAJAJFINSV.NS", "INDUSINDBK.NS", "FEDERALBNK.NS",
        #     "SHRIRAMFIN.NS", "CHOLAFIN.NS", "PFC.NS",

        #     # --- ENERGY & POWER — 7 stocks ---
        #     # Kept: large-cap only; dropped PSU small utilities, project infra
        #     "RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "BPCL.NS",
        #     "TATAPOWER.NS", "ADANIGREEN.NS",

        #     # --- IT & TELECOM — 8 stocks ---
        #     # Kept: Nifty IT index + Airtel; dropped micro-cap digital plays
        #     "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS",
        #     "LTIM.NS", "BHARTIARTL.NS", "NAUKRI.NS",

        #     # --- FMCG & RETAIL — 9 stocks ---
        #     # Kept: Nifty FMCG + premium retail; dropped mid-cap FMCG
        #     "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DABUR.NS",
        #     "TATACONSUM.NS", "TITAN.NS", "DMART.NS", "TRENT.NS",

        #     # --- PHARMA & HEALTHCARE — 7 stocks ---
        #     # Kept: all liquid large-cap pharma; dropped BIOCON (volatile, data gaps)
        #     "SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS", "DIVISLAB.NS",
        #     "APOLLOHOSP.NS", "LUPIN.NS", "ZYDUSLIFE.NS",

        #     # --- METALS & CEMENT — 7 stocks ---
        #     # Kept: top by market cap and liquidity; dropped small cyclicals
        #     "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "COALINDIA.NS",
        #     "ULTRACEMCO.NS", "GRASIM.NS", "VEDL.NS",

        #     # --- AUTOMOBILES — 7 stocks ---
        #     # Kept: major OEMs only; dropped ancillaries (Bosch, Motherson etc.)
        #     "MARUTI.NS", "M&M.NS", "BAJAJ-AUTO.NS", "TVSMOTOR.NS",
        #     "EICHERMOT.NS", "HEROMOTOCO.NS", "TATAMOTORS.NS",

        #     # --- INFRASTRUCTURE — 3 stocks ---
        #     # Drastically cut: kept only Nifty-grade with clean swing data
        #     "LT.NS", "HAL.NS", "ADANIPORTS.NS",
        # ]
        self.custom = [

            # BANKING & FINANCE
            "YESBANK.NS",
            "PNB.NS",
            "BANKBARODA.NS",
            "FEDERALBNK.NS",
            "IDFCFIRSTB.NS",
            "IRFC.NS",
            "RECLTD.NS",
            "PFC.NS",
            "MANAPPURAM.NS",
            "LTF.NS",
            "CHOLAFIN.NS",
            "SBIN.NS",
            "UCOBANK.NS",
            "CENTRALBK.NS",

            # ENERGY & POWER
            "SUZLON.NS",
            # JPPOWER.NS removed: low liquidity, high war-volatility
            "SJVN.NS",
            "NTPC.NS",
            "ONGC.NS",
            "IOC.NS",
            "GAIL.NS",
            "TATAPOWER.NS",
            "ADANIPOWER.NS",
            "NHPC.NS",
            "IEX.NS",
            "PTC.NS",

            # METALS & MATERIALS
            "SAIL.NS",
            "NMDC.NS",
            "NATIONALUM.NS",
            "VEDL.NS",
            "HINDZINC.NS",
            "TATASTEEL.NS",
            "JINDALSTEL.NS",
            # GPIL.NS removed: low liquidity

            # IT & DIGITAL — added WIPRO (~₹250, defensive)
            "WIPRO.NS",
            # HGS.NS removed: unreliable yfinance data
            # INFIBEAM.NS removed: low liquidity, poor data
            "ROUTE.NS",
            "REDINGTON.NS",

            # AUTO & INDUSTRIAL
            "ASHOKLEY.NS",
            # GREAVESCOT.NS removed: low liquidity
            "MOTHERSON.NS",
            # MSUMI.NS removed: duplicate/overlap with Motherson

            # CONSUMER
            "ITC.NS",
            "NYKAA.NS",
            "EMAMILTD.NS",
            "DABUR.NS",

            # PHARMA
            "BIOCON.NS",
            "AUROPHARMA.NS",
            "GLENMARK.NS",
            "ZYDUSLIFE.NS",

            # INFRA & SERVICES
            "RVNL.NS",
            "NBCC.NS",
            "RITES.NS",
            "SCI.NS",

            # MID & SMALL CAPS — removed illiquid chemicals
            # PCBL.NS removed: illiquid, chemicals sector war-sensitive
            # GNFC.NS removed: illiquid chemicals
            # GSFC.NS removed: illiquid chemicals
            "BALRAMCHIN.NS",
            "CASTROLIND.NS",
            "GRAPHITE.NS"
        ]

    def get_watchlist(self, category: str = 'nifty50') -> list:
        """
        Get watchlist of stocks to monitor

        Args:
            category: 'nifty50', 'nifty100', or 'custom'

        Returns:
            List of stock symbols
        """
        if category == 'nifty50':
            return self.nifty_50
        elif category == 'nifty100':
            return self.nifty_50 + self.nifty_next_50
        else:
            return self.custom

    def fetch_stock_data(self, symbol: str, period: str = '3mo', interval: str = '1d') -> pd.DataFrame:
        """
        Fetch historical data for a stock

        Args:
            symbol: Stock symbol (e.g., 'RELIANCE.NS')
            period: Data period (1mo, 3mo, 6mo, 1y)
            interval: Data interval (1d, 1h)

        Returns:
            DataFrame with OHLCV data
        """
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)

            if data.empty:
                logger.warning(f"No data returned for {symbol}")
                return None

            logger.debug(f"Fetched {len(data)} rows for {symbol}")
            return data

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None

    def fetch_stock_info(self, symbol: str) -> dict:
        """
        Fetch stock info (market cap, sector, etc.)

        Args:
            symbol: Stock symbol

        Returns:
            Dict with stock info
        """
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
        """
        Fetch Nifty 50 index data

        Args:
            period: Data period

        Returns:
            DataFrame with Nifty 50 data
        """
        try:
            nifty = yf.Ticker('^NSEI')
            data = nifty.history(period=period)
            return data
        except Exception as e:
            logger.error(f"Error fetching Nifty index: {e}")
            return None

    def get_current_price(self, symbol: str) -> float:
        """
        Get current market price of a stock

        Args:
            symbol: Stock symbol

        Returns:
            Current price or None
        """
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='1d')

            if data.empty:
                return None

            return data['Close'].iloc[-1]

        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            return None

    def get_batch_prices(self, symbols: list) -> dict:
        """
        Get current prices for multiple stocks

        Args:
            symbols: List of stock symbols

        Returns:
            Dict mapping symbol to price
        """
        prices = {}

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
        """
        Check if Indian stock market is open

        Returns:
            True if market is open
        """
        import pytz

        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)

        # Market is closed on weekends
        if now.weekday() >= 5:
            return False

        # Market hours: 9:15 AM - 3:30 PM IST
        market_open = now.replace(hour=9, minute=15, second=0)
        market_close = now.replace(hour=15, minute=30, second=0)

        return market_open <= now <= market_close

    def get_market_status(self) -> dict:
        """
        Get detailed market status

        Returns:
            Dict with market status info
        """
        import pytz

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
