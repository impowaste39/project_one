"""
Market Monitor Service
Scans markets, fetches data, and detects trading opportunities
"""

import os
import pytz
import pandas as pd
import logging
import yfinance as yf
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
        # Threshold: 1.5x volume confirms genuine institutional interest.
        # 2.0x was too strict for normal market conditions — very few breakouts qualified.
        # REFINED in Sprint 4 (FEAT-06):
        is_breakout = (latest['Close'] > latest['BB_Upper'] and latest['Volume_Ratio'] > 1.5)
        if is_breakout:
            patterns.append('breakout_with_volume')
            signals['breakout'] = True

            # Check for high-quality breakout filters
            if len(data) >= 21:
                high_20d = data['High'].iloc[-21:-1].max()
                if pd.notna(high_20d) and latest['Close'] > high_20d:
                    signals['breakout_20d_high'] = True

            if latest['Volume_Ratio'] > 2.0:
                signals['breakout_volume_2x'] = True

            # Time check: first 2 hours of market (9:15 - 11:15 AM IST)
            # Default to True if market is closed (e.g. testing or EOD/pre-market run)
            ist = pytz.timezone('Asia/Kolkata')
            now_ist = datetime.now(ist)

            # If it's a weekday and within market hours, check if it's first 2h
            if now_ist.weekday() < 5:
                market_open = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
                limit_time = now_ist.replace(hour=11, minute=15, second=0, microsecond=0)
                if market_open <= now_ist <= limit_time:
                    signals['breakout_first_2h'] = True
                elif now_ist > limit_time:
                    # After 11:15 AM
                    signals['breakout_first_2h'] = False
                else:
                    # Pre-market
                    signals['breakout_first_2h'] = True
            else:
                # Weekend / Testing
                signals['breakout_first_2h'] = True

        # Pattern 5: Pullback in Uptrend
        if (latest['SMA_20'] > latest['SMA_50'] and
            latest['Close'] < latest['EMA_20'] and
            latest['Close'] > latest['SMA_50'] and
                latest['RSI'] > 40 and latest['RSI'] < 60):
            patterns.append('pullback_in_uptrend')
            signals['pullback'] = True

        # Pattern 6: Higher Highs & Higher Lows (Trend Strength)
        # RE-INSTATED as a counted pattern — this is a swing trader's core setup signal.
        # Combined with other indicators it reliably confirms a healthy uptrend.
        # Previously demoted during extreme market conditions; now restored for normal markets.
        recent_highs = data['High'].tail(5)
        recent_lows = data['Low'].tail(5)
        if recent_highs.is_monotonic_increasing and recent_lows.is_monotonic_increasing:
            patterns.append('trend_strength')
            signals['trend_strength'] = True
            signals['strong_uptrend_context'] = True

        # Pattern 7: Stochastic Oversold
        if latest['Stoch_K'] < 20 and latest['Stoch_D'] < 20:
            patterns.append('stochastic_oversold')
            signals['stoch_oversold'] = True

        # Pattern 8: Price above all MAs (Strong Momentum)
        # RE-INSTATED — price above SMA20 > SMA50 confirms momentum alignment with trend.
        if (latest['Close'] > latest['SMA_20'] > latest['SMA_50']):
            patterns.append('strong_momentum')
            signals['strong_momentum'] = True
            signals['above_all_mas_context'] = True

        # Pattern 9: Near Resistance (90-day swing high)
        # If price is within RESISTANCE_BUFFER_PCT of the 90-day high,
        # we flag it — entering near resistance means limited upside before a pullback.
        # The scoring engine will apply a penalty but won't hard-block.
        try:
            resistance_buffer_pct = float(os.getenv('RESISTANCE_BUFFER_PCT', '3.0'))
            swing_high_90d = data['High'].tail(90).max() if len(data) >= 90 else data['High'].max()
            if pd.notna(swing_high_90d) and swing_high_90d > 0:
                dist_to_resistance_pct = ((swing_high_90d - latest['Close']) / swing_high_90d) * 100
                if 0 <= dist_to_resistance_pct <= resistance_buffer_pct:
                    signals['near_resistance'] = True
                    signals['resistance_level'] = round(swing_high_90d, 2)
                    signals['resistance_dist_pct'] = round(dist_to_resistance_pct, 2)
        except Exception:
            pass  # Resistance check failing never blocks a scan

        return {
            'patterns': patterns,
            'signals': signals,
            'pattern_count': len(patterns),
            'near_resistance': signals.get('near_resistance', False)
        }

    def scan_stock(self, symbol: str, nifty_return_20d: float = None) -> dict:
        """
        Complete analysis of a single stock.

        Args:
            symbol: Stock symbol
            nifty_return_20d: Pre-fetched Nifty 20d return for RS comparison (optional).
                              If None, RS calculation is skipped.

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

            # ── Relative Strength vs Nifty ─────────────────────────────────
            # Stock that moves UP more than Nifty = outperforming = strong candidate.
            # Stock that underperforms Nifty = money is rotating elsewhere.
            rs_positive = None
            stock_return_20d = None
            try:
                if os.getenv('RS_FILTER_ENABLED', 'true').lower() == 'true' and nifty_return_20d is not None:
                    lookback = int(os.getenv('RS_LOOKBACK_DAYS', '20'))
                    # Compute stock's own N-day return
                    price_series = data['Close'].tail(lookback + 5)
                    if len(price_series) >= 2:
                        start_p = price_series.iloc[0]
                        end_p = price_series.iloc[-1]
                        stock_return_20d = round(((end_p - start_p) / start_p) * 100, 4) if start_p > 0 else None
                    if stock_return_20d is not None:
                        rs_positive = stock_return_20d > nifty_return_20d
                        logger.debug(
                            f"[RS] {symbol}: stock={stock_return_20d:.2f}% nifty={nifty_return_20d:.2f}% "
                            f"-> {'OUTPERFORM' if rs_positive else 'UNDERPERFORM'}"
                        )
            except Exception as rs_err:
                logger.debug(f"[RS] {symbol}: RS calc skipped ({rs_err})")
            # ───────────────────────────────────────────────────

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
                'near_resistance': pattern_analysis.get('near_resistance', False),
                'rs_positive': rs_positive,
                'stock_return_20d': stock_return_20d,
                'nifty_return_20d': nifty_return_20d,
            }

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            return None

    def pre_rank_watchlist(self, limit: int = 30) -> list:
        """
        Rank the watchlist by relative strength, momentum, and volume trend.
        Returns the top `limit` ranked symbols.
        """
        logger.info(f"[PreRank] Pre-ranking watchlist ({len(self.watchlist)} symbols)...")
        try:
            # Fetch Nifty 20d return
            lookback = int(os.getenv('RS_LOOKBACK_DAYS', '20'))
            nifty_return_20d = self.data_service.fetch_nifty_return(lookback)
            if nifty_return_20d is None:
                nifty_return_20d = 0.0

            symbols = self.watchlist
            ranked_candidates = []
            chunk_size = 10

            for i in range(0, len(symbols), chunk_size):
                chunk = symbols[i:i + chunk_size]

                # Batch download data for this chunk
                data = yf.download(
                    chunk,
                    period='3mo',
                    interval='1d',
                    progress=False,
                    group_by='ticker',
                    auto_adjust=True
                )

                for symbol in chunk:
                    try:
                        # Get symbol data from multi-index DataFrame
                        if len(chunk) == 1:
                            sym_data = data
                        else:
                            sym_data = data[symbol].dropna()

                        if sym_data.empty or len(sym_data) < 20:
                            continue

                        # 1. 20-day Return
                        price_series = sym_data['Close'].tail(lookback)
                        start_p = price_series.iloc[0]
                        end_p = price_series.iloc[-1]
                        stock_return = ((end_p - start_p) / start_p) * 100 if start_p > 0 else 0.0

                        # Relative strength vs Nifty
                        rs_score = stock_return - nifty_return_20d

                        # 2. Proximity to 3-month High
                        high_3m = sym_data['High'].max()
                        current_price = sym_data['Close'].iloc[-1]
                        proximity = (current_price / high_3m) if high_3m > 0 else 0.0

                        # 3. Volume Trend (last 5 days vs preceding 15 days)
                        vol_5d = sym_data['Volume'].tail(5).mean()
                        vol_prev = sym_data['Volume'].iloc[-20:-5].mean()
                        vol_ratio = (vol_5d / vol_prev) if vol_prev > 0 else 1.0

                        # Calculate a composite ranking score
                        # RS (weight 50%) + Proximity (weight 30%) + Volume Trend (weight 20%)
                        rank_score = (rs_score * 0.5) + (proximity * 30.0) + (vol_ratio * 20.0)

                        ranked_candidates.append({
                            'symbol': symbol,
                            'rank_score': rank_score,
                            'rs_score': rs_score,
                            'proximity': proximity,
                            'vol_ratio': vol_ratio
                        })
                    except Exception as sym_err:
                        logger.debug(f"[PreRank] Error processing {symbol}: {sym_err}")

            # Sort by composite rank score descending
            ranked_candidates.sort(key=lambda x: x['rank_score'], reverse=True)

            # Extract top N symbols
            top_symbols = [c['symbol'] for c in ranked_candidates[:limit]]
            logger.info(f"[PreRank] Watchlist ranked. Top 5: {top_symbols[:5]}")
            return top_symbols

        except Exception as e:
            logger.warning(f"[PreRank] Watchlist pre-ranking failed ({e}) — using default watchlist order")
            return self.watchlist[:limit]

    def scan_market(self, nifty_return_20d: float = None) -> list:
        """
        Scan entire watchlist for opportunities.

        Pre-fetches Nifty 20d return once and passes it to each scan_stock call
        so relative strength is computed without an extra API call per stock.

        Returns:
            list: Stocks with potential trading setups (pattern_count > 0)
        """
        logger.info("=" * 50)
        logger.info("MARKET SCAN STARTED")
        logger.info("=" * 50)

        # Fetch Nifty return once for all RS comparisons
        if nifty_return_20d is None:
            try:
                lookback = int(os.getenv('RS_LOOKBACK_DAYS', '20'))
                nifty_return_20d = self.data_service.fetch_nifty_return(lookback)
                logger.info(f"[RS] Nifty {lookback}d return: {nifty_return_20d:.2f}%" if nifty_return_20d is not None else "[RS] Nifty return unavailable")
            except Exception as e:
                logger.warning(f"[RS] Nifty return fetch skipped: {e}")

        # Pre-rank watchlist to focus compute on top-performing setups (FEAT-04)
        watchlist_to_scan = self.watchlist
        if os.getenv('WATCHLIST_PRE_RANK_ENABLED', 'true').lower() == 'true':
            limit = int(os.getenv('WATCHLIST_PRE_RANK_LIMIT', '30'))
            watchlist_to_scan = self.pre_rank_watchlist(limit=limit)

        opportunities = []

        for symbol in watchlist_to_scan:
            try:
                analysis = self.scan_stock(symbol, nifty_return_20d=nifty_return_20d)

                if analysis and analysis['pattern_count'] > 0:
                    opportunities.append(analysis)
                    logger.info(
                        f"✅ Opportunity: {symbol} - {analysis['patterns']} "
                        f"RS={'outperform' if analysis.get('rs_positive') else ('underperform' if analysis.get('rs_positive') is False else 'n/a')}")

            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                continue

        logger.info(
            f"Market scan complete. Found {len(opportunities)} opportunities")
        return opportunities

    def scan_market_preopen(self) -> list:
        """
        Pre-market scan (8:45 AM IST) — runs BEFORE the market opens.

        Identical to scan_market() but returns ALL stocks with pattern_count > 0
        sorted by potential score (heuristic: pattern_count + volume_ratio).
        Does NOT trigger any trade entries — purely informational.

        Returns:
            list: Ranked analysis dicts for the pre-market Telegram/Discord summary
        """
        logger.info("PRE-MARKET SCAN STARTED")

        try:
            lookback = int(os.getenv('RS_LOOKBACK_DAYS', '20'))
            nifty_return_20d = self.data_service.fetch_nifty_return(lookback)
        except Exception:
            nifty_return_20d = None

        # Pre-rank watchlist to focus compute on top-performing setups (FEAT-04)
        watchlist_to_scan = self.watchlist
        if os.getenv('WATCHLIST_PRE_RANK_ENABLED', 'true').lower() == 'true':
            limit = int(os.getenv('WATCHLIST_PRE_RANK_LIMIT', '30'))
            watchlist_to_scan = self.pre_rank_watchlist(limit=limit)

        candidates = []
        for symbol in watchlist_to_scan:
            try:
                analysis = self.scan_stock(symbol, nifty_return_20d=nifty_return_20d)
                if analysis and analysis['pattern_count'] > 0:
                    candidates.append(analysis)
            except Exception as e:
                logger.debug(f"Pre-open scan error for {symbol}: {e}")
                continue

        # Sort by pattern count (desc), then volume ratio (desc)
        candidates.sort(
            key=lambda a: (a.get('pattern_count', 0), a.get('volume_ratio', 1)),
            reverse=True
        )

        logger.info(f"Pre-market scan complete. {len(candidates)} candidates found.")
        return candidates

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

            # India VIX: fetch to gauge fear/volatility regime
            try:
                vix_data = self.data_service.fetch_stock_data(
                    '^INDIAVIX', period='5d')
                if vix_data is not None and not vix_data.empty:
                    india_vix = round(vix_data['Close'].iloc[-1], 2)
                    if india_vix > 30:
                        market_volatility = 'extreme'   # War/crisis level
                    elif india_vix > 20:
                        market_volatility = 'high'      # Elevated fear
                    else:
                        market_volatility = 'normal'    # Typical 12-16 range
                    context['india_vix'] = india_vix
                    context['market_volatility'] = market_volatility
                else:
                    context['india_vix'] = None
                    context['market_volatility'] = 'normal'  # safe default
            except Exception as vix_err:
                logger.warning(f"[MarketContext] VIX fetch skipped: {vix_err}")
                context['india_vix'] = None
                context['market_volatility'] = 'normal'

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
