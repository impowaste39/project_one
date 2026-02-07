"""
Technical Indicator Service
Calculates various technical indicators for stock analysis
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class IndicatorService:
    """Calculate technical indicators for stock data"""

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI)

        Args:
            prices: Series of closing prices
            period: RSI period (default 14)

        Returns:
            Series of RSI values
        """
        delta = prices.diff()

        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)

        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """
        Calculate MACD (Moving Average Convergence Divergence)

        Args:
            prices: Series of closing prices
            fast: Fast EMA period (default 12)
            slow: Slow EMA period (default 26)
            signal: Signal line period (default 9)

        Returns:
            Dict with MACD, Signal, and Histogram
        """
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            'MACD': macd_line,
            'Signal': signal_line,
            'Histogram': histogram
        }

    def calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, std_dev: float = 2.0) -> dict:
        """
        Calculate Bollinger Bands

        Args:
            prices: Series of closing prices
            period: Moving average period (default 20)
            std_dev: Standard deviation multiplier (default 2.0)

        Returns:
            Dict with Upper, Middle, and Lower bands
        """
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()

        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        return {
            'Upper': upper,
            'Middle': middle,
            'Lower': lower
        }

    def calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Average True Range (ATR)

        Args:
            data: DataFrame with High, Low, Close columns
            period: ATR period (default 14)

        Returns:
            Series of ATR values
        """
        high = data['High']
        low = data['Low']
        close = data['Close']

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr

    def calculate_stochastic(self, data: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> dict:
        """
        Calculate Stochastic Oscillator

        Args:
            data: DataFrame with High, Low, Close columns
            k_period: %K period (default 14)
            d_period: %D period (default 3)

        Returns:
            Dict with %K and %D values
        """
        low_min = data['Low'].rolling(window=k_period).min()
        high_max = data['High'].rolling(window=k_period).max()

        k = 100 * ((data['Close'] - low_min) / (high_max - low_min))
        d = k.rolling(window=d_period).mean()

        return {
            'K': k,
            'D': d
        }

    def calculate_adx(self, data: pd.DataFrame, period: int = 14) -> dict:
        """
        Calculate Average Directional Index (ADX)

        Args:
            data: DataFrame with High, Low, Close columns
            period: ADX period (default 14)

        Returns:
            Dict with ADX, +DI, and -DI
        """
        high = data['High']
        low = data['Low']
        close = data['Close']

        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        atr = self.calculate_atr(data, period)

        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return {
            'ADX': adx,
            'PlusDI': plus_di,
            'MinusDI': minus_di
        }

    def calculate_vwap(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate Volume Weighted Average Price (VWAP)

        Args:
            data: DataFrame with High, Low, Close, Volume columns

        Returns:
            Series of VWAP values
        """
        typical_price = (data['High'] + data['Low'] + data['Close']) / 3
        vwap = (typical_price * data['Volume']
                ).cumsum() / data['Volume'].cumsum()

        return vwap

    def calculate_obv(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate On-Balance Volume (OBV)

        Args:
            data: DataFrame with Close and Volume columns

        Returns:
            Series of OBV values
        """
        obv = (np.sign(data['Close'].diff()) *
               data['Volume']).fillna(0).cumsum()
        return obv

    def calculate_support_resistance(self, data: pd.DataFrame, window: int = 20) -> dict:
        """
        Calculate support and resistance levels

        Args:
            data: DataFrame with High, Low columns
            window: Lookback window (default 20)

        Returns:
            Dict with support and resistance levels
        """
        support = data['Low'].rolling(window=window).min().iloc[-1]
        resistance = data['High'].rolling(window=window).max().iloc[-1]

        return {
            'support': support,
            'resistance': resistance
        }
