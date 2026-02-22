"""
Market Monitor Service
Scans markets, fetches data, and detects trading opportunities
"""

import pandas as pd
import logging
from datetime import datetime
import time

from services.data_service import DataService
from services.indicator_service import IndicatorService

logger = logging.getLogger(__name__)

_NIFTY_CACHE = {
    'context': None,
    'timestamp': 0
}


class MarketMonitor:
    """Market scanning and opportunity detection"""

    def __init__(self, db_session=None):
        self.db = db_session
        self.data_service = DataService()
        self.indicator_service = IndicatorService()
        self.watchlist = self.data_service.get_watchlist('custom')
        # Fallback context: returned when Nifty fetch fails, avoiding silent 20-pt score loss
        self._last_known_context = {
            'trend': 'sideways',
            'strength': 50,
            'nifty_price': None,
            'nifty_rsi': 50,
            'market_breadth': 'positive',
            'fetch_failed': False
        }

    def fetch_stock_data(self, symbol: str, period: str = '3mo', interval: str = '1d') -> pd.DataFrame:
        """Fetch historical data for a stock"""
        return self.data_service.fetch_stock_data(symbol, period, interval)

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all technical indicators for a stock

        Args:
            data: OHLCV DataFrame

        Returns:
            DataFrame with indicators added
        """
        if data is None or len(data) < 50:
            return None

        try:
            # Moving Averages
            data['SMA_20'] = data['Close'].rolling(window=20).mean()
            data['SMA_50'] = data['Close'].rolling(window=50).mean()
            data['EMA_20'] = data['Close'].ewm(span=20, adjust=False).mean()
            data['EMA_50'] = data['Close'].ewm(span=50, adjust=False).mean()

            # RSI
            data['RSI'] = self.indicator_service.calculate_rsi(data['Close'])

            # MACD
            macd_data = self.indicator_service.calculate_macd(data['Close'])
            data['MACD'] = macd_data['MACD']
            data['MACD_Signal'] = macd_data['Signal']
            data['MACD_Hist'] = macd_data['Histogram']

            # Bollinger Bands
            bb_data = self.indicator_service.calculate_bollinger_bands(
                data['Close'])
            data['BB_Upper'] = bb_data['Upper']
            data['BB_Middle'] = bb_data['Middle']
            data['BB_Lower'] = bb_data['Lower']

            # Volume indicators
            data['Volume_SMA'] = data['Volume'].rolling(window=20).mean()
            data['Volume_Ratio'] = data['Volume'] / data['Volume_SMA']

            # ATR for volatility
            data['ATR'] = self.indicator_service.calculate_atr(data)

            # Stochastic
            stoch = self.indicator_service.calculate_stochastic(data)
            data['Stoch_K'] = stoch['K']
            data['Stoch_D'] = stoch['D']

            return data

        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return None

    def detect_patterns(self, data: pd.DataFrame) -> dict:
        """
        Detect chart patterns and trading setups

        Args:
            data: DataFrame with indicators

        Returns:
            Dict with patterns and signals
        """
        if data is None or len(data) < 20:
            return {'patterns': [], 'signals': {}}

        patterns = []
        signals = {}

        latest = data.iloc[-1]
        prev = data.iloc[-2]

        # Pattern 1: Bullish Moving Average Crossover
        if (prev['Close'] <= prev['SMA_20'] and
            latest['Close'] > latest['SMA_20'] and
                latest['SMA_20'] > latest['SMA_50']):
            patterns.append('bullish_ma_crossover')
            signals['ma_crossover'] = True

        # Pattern 2: RSI Oversold Bounce
        if prev['RSI'] < 30 and latest['RSI'] > 30:
            patterns.append('rsi_oversold_bounce')
            signals['rsi_bounce'] = True

        # Pattern 3: MACD Bullish Crossover
        if (prev['MACD'] <= prev['MACD_Signal'] and
                latest['MACD'] > latest['MACD_Signal']):
            patterns.append('macd_bullish_crossover')
            signals['macd_cross'] = True

        # Pattern 4: Breakout with Volume
        if (latest['Close'] > latest['BB_Upper'] and
                latest['Volume_Ratio'] > 1.5):
            patterns.append('breakout_with_volume')
            signals['breakout'] = True

        # Pattern 5: Pullback in Uptrend
        if (latest['SMA_20'] > latest['SMA_50'] and
            latest['Close'] < latest['EMA_20'] and
            latest['Close'] > latest['SMA_50'] and
                latest['RSI'] > 40 and latest['RSI'] < 60):
            patterns.append('pullback_in_uptrend')
            signals['pullback'] = True

        # Pattern 6: Higher Highs & Higher Lows (Trend Strength)
        # DEMOTED: moved to context{} — fires on ~23k stocks, too common to count as a signal
        recent_highs = data['High'].tail(5)
        recent_lows = data['Low'].tail(5)
        if recent_highs.is_monotonic_increasing and recent_lows.is_monotonic_increasing:
            signals['trend_strength'] = True
            # Context flag, not a tradeable signal
            signals['strong_uptrend_context'] = True

        # Pattern 7: Stochastic Oversold
        if latest['Stoch_K'] < 20 and latest['Stoch_D'] < 20:
            patterns.append('stochastic_oversold')
            signals['stoch_oversold'] = True

        # Pattern 8: Price above all MAs
        # DEMOTED: moved to context{} — fires on ~17k stocks, structural condition not a signal
        if (latest['Close'] > latest['SMA_20'] > latest['SMA_50']):
            signals['strong_momentum'] = True
            # Context flag, not a tradeable signal
            signals['above_all_mas_context'] = True

        return {
            'patterns': patterns,
            'signals': signals,
            'pattern_count': len(patterns)
        }

    def scan_stock(self, symbol: str) -> dict:
        """
        Complete analysis of a single stock

        Args:
            symbol: Stock symbol

        Returns:
            dict: Analysis results or None
        """
        try:
            # Fetch data
            data = self.fetch_stock_data(symbol)
            if data is None:
                return None

            # Calculate indicators
            data = self.calculate_indicators(data)
            if data is None:
                return None

            # Detect patterns
            pattern_analysis = self.detect_patterns(data)

            latest = data.iloc[-1]

            # Return analysis package
            return {
                'symbol': symbol,
                'current_price': latest['Close'],
                'rsi': latest['RSI'],
                'macd': latest['MACD'],
                'volume_ratio': latest['Volume_Ratio'],
                'atr': latest['ATR'],
                'sma_20': latest['SMA_20'],
                'sma_50': latest['SMA_50'],
                'patterns': pattern_analysis['patterns'],
                'signals': pattern_analysis['signals'],
                'pattern_count': pattern_analysis['pattern_count'],
                'data': data
            }

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            return None

    def scan_market(self) -> list:
        """
        Scan entire watchlist for opportunities

        Returns:
            list: Stocks with potential trading setups
        """
        logger.info("=" * 50)
        logger.info("MARKET SCAN STARTED")
        logger.info("=" * 50)

        opportunities = []

        for symbol in self.watchlist:
            try:
                analysis = self.scan_stock(symbol)

                if analysis and analysis['pattern_count'] > 0:
                    opportunities.append(analysis)
                    logger.info(
                        f"✅ Opportunity: {symbol} - {analysis['patterns']}")

            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                continue

        logger.info(
            f"Market scan complete. Found {len(opportunities)} opportunities")
        return opportunities

    def get_market_context(self) -> dict:
        """
        Analyze overall market trend (Nifty 50).

        On failure, returns the last successfully fetched context (with fetch_failed=True)
        instead of 'unknown', preventing a silent 20-point score loss on every evaluation.

        Returns:
            dict: Market sentiment and trend information
        """
        current_time = time.time()
        # Ensure 5-minute memory cache to prevent yfinance shadow bans
        if _NIFTY_CACHE['context'] is not None and (current_time - _NIFTY_CACHE['timestamp'] < 300):
            return _NIFTY_CACHE['context']

        try:
            data = self.data_service.fetch_nifty_index(period='6mo')

            if data is None or data.empty:
                logger.warning(
                    "[MarketContext] Nifty data empty — using last known context: "
                    f"trend={self._last_known_context['trend']}"
                )
                self._last_known_context['fetch_failed'] = True
                return self._last_known_context

            data = self.calculate_indicators(data)

            if data is None:
                logger.warning(
                    "[MarketContext] Indicator calculation failed — using last known context"
                )
                self._last_known_context['fetch_failed'] = True
                return self._last_known_context

            latest = data.iloc[-1]

            # Determine market trend
            if latest['Close'] > latest['SMA_20'] > latest['SMA_50']:
                trend = 'bullish'
                strength = min(
                    100, (latest['Close'] / latest['SMA_50'] - 1) * 100)
            elif latest['Close'] < latest['SMA_20'] < latest['SMA_50']:
                trend = 'bearish'
                strength = min(
                    100, (1 - latest['Close'] / latest['SMA_50']) * 100)
            else:
                trend = 'sideways'
                strength = 50

            context = {
                'trend': trend,
                'strength': round(strength, 2),
                'nifty_price': round(latest['Close'], 2),
                'nifty_rsi': round(latest['RSI'], 2) if pd.notna(latest['RSI']) else 50,
                'market_breadth': 'positive' if latest['Volume_Ratio'] > 1 else 'negative',
                'fetch_failed': False
            }

            # Persist last good context for fallback use
            self._last_known_context = context

            _NIFTY_CACHE['context'] = context
            _NIFTY_CACHE['timestamp'] = time.time()
            return context

        except Exception as e:
            logger.error(
                f"[CRITICAL][MarketContext] Nifty fetch exception: {e}. "
                f"Falling back to last known context: trend={self._last_known_context['trend']}"
            )
            self._last_known_context['fetch_failed'] = True

            _NIFTY_CACHE['context'] = self._last_known_context
            _NIFTY_CACHE['timestamp'] = time.time()

            return self._last_known_context
