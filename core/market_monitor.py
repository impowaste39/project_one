"""
Market Monitor Service
Scans markets, fetches data, and detects trading opportunities
"""

import pandas as pd
import logging
from datetime import datetime

from services.data_service import DataService
from services.indicator_service import IndicatorService

logger = logging.getLogger(__name__)


class MarketMonitor:
    """Market scanning and opportunity detection"""

    def __init__(self, db_session=None):
        self.db = db_session
        self.data_service = DataService()
        self.indicator_service = IndicatorService()
        self.watchlist = self.data_service.get_watchlist('nifty50')

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
        recent_highs = data['High'].tail(10)
        recent_lows = data['Low'].tail(10)
        if (recent_highs.iloc[-1] > recent_highs.iloc[-3] and
                recent_lows.iloc[-1] > recent_lows.iloc[-3]):
            patterns.append('strong_uptrend')
            signals['trend_strength'] = True

        # Pattern 7: Stochastic Oversold
        if latest['Stoch_K'] < 20 and latest['Stoch_D'] < 20:
            patterns.append('stochastic_oversold')
            signals['stoch_oversold'] = True

        # Pattern 8: Price above all MAs (Strong momentum)
        if (latest['Close'] > latest['SMA_20'] > latest['SMA_50']):
            patterns.append('above_all_mas')
            signals['strong_momentum'] = True

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
        Analyze overall market trend (Nifty 50)

        Returns:
            dict: Market sentiment and trend information
        """
        try:
            data = self.data_service.fetch_nifty_index(period='1mo')

            if data is None or data.empty:
                return {'trend': 'unknown', 'strength': 0}

            data = self.calculate_indicators(data)

            if data is None:
                return {'trend': 'unknown', 'strength': 0}

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

            return {
                'trend': trend,
                'strength': round(strength, 2),
                'nifty_price': round(latest['Close'], 2),
                'nifty_rsi': round(latest['RSI'], 2) if pd.notna(latest['RSI']) else 50,
                'market_breadth': 'positive' if latest['Volume_Ratio'] > 1 else 'negative'
            }

        except Exception as e:
            logger.error(f"Error getting market context: {e}")
            return {'trend': 'unknown', 'strength': 0}
