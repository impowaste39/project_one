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
            return self.nifty_50

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

    def fetch_nifty_index(self, period: str = '1mo') -> pd.DataFrame:
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
