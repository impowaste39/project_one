"""
Discord Webhook Alert Service
Sends instant trade alerts to your Discord channel — completely free!

Setup:
1. Create a Discord server (or use existing)
2. Go to channel settings → Integrations → Webhooks → New Webhook
3. Copy the webhook URL
4. Add to Render environment: DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

Improvements in this version:
- TradingView chart link in every alert (one tap → chart opens on phone)
- Position tier badge (CAUTIOUS / NORMAL / HIGH CONVICTION)
- Weekly EMA filter confirmation shown in entry alert
- Circuit breaker status in EOD daily summary
- Dedicated circuit breaker triggered alert
"""

import requests
import logging
import os
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')

TIER_DISPLAY = {
    'HIGH CONVICTION': '🔴 HIGH CONVICTION (1.5x size)',
    'NORMAL':          '🟠 NORMAL (1.0x size)',
    'CAUTIOUS':        '🟡 CAUTIOUS (0.75x size)',
    'N/A':             '⚪ N/A',
}


class DiscordService:
    """Sends trading alerts to Discord via webhook — zero cost"""

    def __init__(self):
        self.webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        if not self.webhook_url:
            logger.warning(
                "DISCORD_WEBHOOK_URL not set — Discord alerts disabled")

    def _get_ist_time(self) -> str:
        return datetime.now(IST).strftime('%d %b %Y, %I:%M %p IST')

    def _get_tradingview_url(self, symbol: str) -> str:
        """
        Generate TradingView chart URL.
        FEDERALBNK.NS → https://in.tradingview.com/chart/?symbol=NSE:FEDERALBNK
        One tap in Discord → chart opens in TradingView app or browser.
        """
        clean = symbol.replace('.NS', '').replace('.BO', '')
        return f"https://in.tradingview.com/chart/?symbol=NSE:{clean}"

    def _clean(self, symbol: str) -> str:
        """Strip .NS suffix for display"""
        return symbol.replace('.NS', '').replace('.BO', '')

    def _send(self, payload: dict) -> bool:
        """Send payload to Discord webhook"""
        if not self.webhook_url:
            return False
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            if response.status_code in (200, 204):
                return True
            else:
                logger.warning(
                    f"Discord webhook returned {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.warning(f"Discord alert failed (non-critical): {e}")
            return False

    def send_trade_entry_alert(self, evaluation: dict) -> bool:
        """
        Send alert when bot finds a high-quality trade setup.
        Called from scan_market_job() when decision == 'ENTER'.

        Includes:
        - Position tier badge (how big the bet is)
        - Weekly EMA confirmation (long-term trend)
        - TradingView link (review chart instantly on phone)
        """
        symbol = evaluation.get('symbol', 'UNKNOWN')
        score = evaluation.get('score', 0)
        entry = evaluation.get('entry_price', 0)
        sl = evaluation.get('stop_loss', 0)
        t1 = evaluation.get('target_1', 0)
        t2 = evaluation.get('target_2', 0)
        rr = evaluation.get('rr_ratio', 0)
        patterns = evaluation.get('patterns', [])
        factors = evaluation.get('factors', [])
        position_tier = evaluation.get('position_tier', 'NORMAL')
        weekly_ema_reason = evaluation.get('weekly_ema_reason', '')

        risk_pct = round(((entry - sl) / entry) * 100, 2) if entry > 0 else 0
        reward_pct = round(((t1 - entry) / entry) * 100, 2) if entry > 0 else 0

        pattern_text = '\n'.join(
            [f"• {p.replace('_', ' ').title()}" for p in patterns]
        ) if patterns else '• No specific pattern'

        factors_text = '\n'.join(
            [f"• {f}" for f in factors[:4]]  # Increased from 3 to 4 to show ML bonus
        ) if factors else '• Score-based entry'

        tier_badge = TIER_DISPLAY.get(position_tier, f'⚪ {position_tier}')
        chart_url = self._get_tradingview_url(symbol)

        # Weekly EMA status — shows if we're above/below long-term trend
        weekly_ema_status = evaluation.get('weekly_ema_status', 'above')
        ema_icon = "✅" if weekly_ema_status == "above" else "⚠️"
        ema_label = "Above 50W EMA (uptrend)" if weekly_ema_status == "above" else "Below 50W EMA (downtrend, penalty applied)"

        fields = [
            {
                "name": "📊 Setup Score",
                "value": f"**{score}/100**",
                "inline": True
            },
            {
                "name": "⚖️ Risk:Reward",
                "value": f"**{rr}:1**",
                "inline": True
            },
            {
                "name": "💼 Position Size",
                "value": tier_badge,
                "inline": False
            },
            {
                "name": "‎",
                "value": "‎",
                "inline": False
            },
            {
                "name": "💰 Entry Price",
                "value": f"**₹{entry}**",
                "inline": True
            },
            {
                "name": "🛑 Stop Loss",
                "value": f"**₹{sl}** (-{risk_pct}%)",
                "inline": True
            },
            {
                "name": "‎",
                "value": "‎",
                "inline": False
            },
            {
                "name": "🎯 Target 1",
                "value": f"**₹{t1}** (+{reward_pct}%)",
                "inline": True
            },
            {
                "name": "🎯 Target 2",
                "value": f"**₹{t2}**",
                "inline": True
            },
            {
                "name": "📈 Patterns Detected",
                "value": pattern_text,
                "inline": False
            },
            {
                "name": "🧠 Why This Setup",
                "value": factors_text,
                "inline": False
            },
            {
                "name": "📅 Long-Term Trend",
                "value": f"{ema_icon} {ema_label}",
                "inline": False
            },
        ]

        fields.append({
            "name": "📉 Review Chart",
            "value": f"[Open {self._clean(symbol)} on TradingView]({chart_url})",
            "inline": False
        })

        payload = {
            "embeds": [{
                "title": f"🚨 TRADE ALERT — {self._clean(symbol)}",
                "color": 3066993,
                "fields": fields,
                "footer": {
                    "text": f"⚡ Place order manually on Zerodha • {self._get_ist_time()}"
                }
            }]
        }

        success = self._send(payload)
        if success:
            logger.info(
                f"Discord entry alert sent for {symbol} | Tier: {position_tier}")
        return success

    def send_trade_exit_alert(self, trade, exit_reason: str,
                              is_partial: bool = False) -> bool:
        """
        Send alert when a trade is exited (full or partial).
        Called from monitor_positions_job() on exit.
        Includes TradingView chart link.
        """
        symbol = trade.symbol
        entry = trade.entry_price
        exit_price = trade.exit_price or 0
        pnl = trade.profit_loss or 0
        pnl_pct = trade.profit_loss_pct or 0
        hold_days = trade.hold_duration_days or 0

        is_profit = pnl >= 0
        color = 3066993 if is_profit else 15158332
        emoji = "✅" if is_profit else "❌"
        prefix = "PARTIAL EXIT" if is_partial else "TRADE CLOSED"
        chart_url = self._get_tradingview_url(symbol)

        payload = {
            "embeds": [{
                "title": f"{emoji} {prefix} — {self._clean(symbol)}",
                "color": color,
                "fields": [
                    {
                        "name": "📥 Entry",
                        "value": f"₹{entry}",
                        "inline": True
                    },
                    {
                        "name": "📤 Exit",
                        "value": f"₹{exit_price}",
                        "inline": True
                    },
                    {
                        "name": "💸 Net P&L",
                        "value": (
                            f"**{'▲' if is_profit else '▼'} "
                            f"₹{abs(pnl):.2f} ({pnl_pct:.2f}%)**"
                        ),
                        "inline": False
                    },
                    {
                        "name": "📅 Held For",
                        "value": f"{hold_days} days",
                        "inline": True
                    },
                    {
                        "name": "🚪 Exit Reason",
                        "value": exit_reason,
                        "inline": True
                    },
                    {
                        "name": "📉 Chart",
                        "value": (
                            f"[View {self._clean(symbol)} on TradingView]"
                            f"({chart_url})"
                        ),
                        "inline": False
                    },
                ],
                "footer": {
                    "text": self._get_ist_time()
                }
            }]
        }

        success = self._send(payload)
        if success:
            logger.info(f"Discord exit alert sent for {symbol}")
        return success

    def send_partial_exit_alert(self, symbol: str, entry_price: float,
                                exit_price: float, quantity_exited: int,
                                pnl: float) -> bool:
        """
        Send alert when 50% of position is booked at T1.
        Includes TradingView chart link.
        """
        is_profit = pnl >= 0
        color = 3066993 if is_profit else 15158332
        chart_url = self._get_tradingview_url(symbol)

        payload = {
            "embeds": [{
                "title": f"🎯 PARTIAL EXIT (T1 HIT) — {self._clean(symbol)}",
                "color": color,
                "description": (
                    "50% position booked. Stop loss moved to breakeven. Riding to T2!"
                ),
                "fields": [
                    {
                        "name": "📥 Entry",
                        "value": f"₹{entry_price}",
                        "inline": True
                    },
                    {
                        "name": "📤 Partial Exit",
                        "value": f"₹{exit_price}",
                        "inline": True
                    },
                    {
                        "name": "📦 Qty Booked",
                        "value": f"{quantity_exited} shares",
                        "inline": True
                    },
                    {
                        "name": "💸 Booked P&L",
                        "value": f"**₹{pnl:.2f}**",
                        "inline": True
                    },
                    {
                        "name": "🛑 New Stop Loss",
                        "value": f"₹{entry_price} (Breakeven)",
                        "inline": True
                    },
                    {
                        "name": "📉 Chart",
                        "value": (
                            f"[View {self._clean(symbol)} on TradingView]"
                            f"({chart_url})"
                        ),
                        "inline": False
                    },
                ],
                "footer": {
                    "text": self._get_ist_time()
                }
            }]
        }

        success = self._send(payload)
        if success:
            logger.info(f"Discord partial exit alert sent for {symbol}")
        return success

    def send_daily_summary(self, performance: dict) -> bool:
        """
        Send EOD daily summary at 4 PM IST.
        Now includes weekly P&L and circuit breaker status.

        Pass get_weekly_pnl_summary() result merged into performance dict
        to get the weekly section.
        """
        total_trades = performance.get('total_trades', 0)
        win_rate = performance.get('win_rate', 0)
        total_pnl = performance.get('total_pnl', 0)
        open_positions = performance.get('open_positions', 0)
        today_trades = performance.get('today_trades', 0)

        week_pnl = performance.get('week_pnl', None)
        week_trades = performance.get('week_trades', None)
        week_wins = performance.get('week_wins', None)
        circuit_breaker_active = performance.get('circuit_breaker_active', False)
        loss_pct = performance.get('loss_pct_of_capital', 0)
        circuit_limit = performance.get('circuit_breaker_limit_pct', 3.0)

        is_profit = total_pnl >= 0
        color = 3066993 if is_profit else 15158332
        pnl_emoji = "📈" if is_profit else "📉"

        fields = [
            {
                "name": "🔄 Today's Trades",
                "value": str(today_trades),
                "inline": True
            },
            {
                "name": "📂 Open Positions",
                "value": str(open_positions),
                "inline": True
            },
            {
                "name": f"{pnl_emoji} Total P&L",
                "value": f"**₹{total_pnl:.2f}**",
                "inline": True
            },
            {
                "name": "🏆 Win Rate",
                "value": f"{win_rate:.1f}%",
                "inline": True
            },
            {
                "name": "📋 Total Trades",
                "value": str(total_trades),
                "inline": True
            },
        ]

        if week_pnl is not None:
            week_pnl_emoji = "📈" if week_pnl >= 0 else "📉"
            week_win_rate = (
                round(week_wins / week_trades * 100, 1)
                if week_trades and week_trades > 0 else 0
            )
            fields.append({"name": "‎", "value": "‎", "inline": False})
            fields.append({
                "name": f"{week_pnl_emoji} This Week P&L",
                "value": (
                    f"**₹{week_pnl:.2f}** "
                    f"({week_trades} trades, {week_win_rate}% WR)"
                ),
                "inline": False
            })

            if circuit_breaker_active:
                fields.append({
                    "name": "⛔ Circuit Breaker",
                    "value": (
                        f"**ACTIVE** — Week loss {loss_pct:.1f}% exceeds "
                        f"{circuit_limit}% limit.\nNo new trades until Monday."
                    ),
                    "inline": False
                })
            else:
                headroom = circuit_limit - loss_pct
                fields.append({
                    "name": "✅ Circuit Breaker",
                    "value": (
                        f"Inactive — {loss_pct:.1f}% of {circuit_limit}% "
                        f"limit used ({headroom:.1f}% headroom)"
                    ),
                    "inline": False
                })

        payload = {
            "embeds": [{
                "title": (
                    f"📊 Daily Summary — "
                    f"{datetime.now(IST).strftime('%d %b %Y')}"
                ),
                "color": color,
                "fields": fields,
                "footer": {
                    "text": f"Market closed • {self._get_ist_time()}"
                }
            }]
        }

        success = self._send(payload)
        if success:
            logger.info("Discord daily summary sent")
        return success

    def send_circuit_breaker_alert(self, week_pnl: float, loss_pct: float,
                                   limit_pct: float) -> bool:
        """
        Dedicated alert the moment circuit breaker triggers mid-day.
        Call this from portfolio_manager when circuit breaker fires for the
        first time in the week so you know immediately — don't wait for EOD.
        """
        payload = {
            "embeds": [{
                "title": "⛔ CIRCUIT BREAKER TRIGGERED",
                "color": 15158332,
                "description": (
                    f"Weekly loss has reached **{loss_pct:.1f}%** of capital "
                    f"(₹{abs(week_pnl):.2f}), exceeding the **{limit_pct}% limit**.\n\n"
                    f"**No new trades will be entered until Monday.**\n"
                    f"Existing positions continue to be monitored and can still exit."
                ),
                "footer": {
                    "text": f"Review your open positions • {self._get_ist_time()}"
                }
            }]
        }
        success = self._send(payload)
        if success:
            logger.warning("Discord circuit breaker alert sent")
        return success

    def send_health_alert(self, subject: str, body: str) -> bool:
        """Send system health alert"""
        payload = {
            "embeds": [{
                "title": f"🚨 {subject}",
                "description": body,
                "color": 15158332,
                "footer": {
                    "text": self._get_ist_time()
                }
            }]
        }
        return self._send(payload)

    def send_premarket_watchlist(self, candidates: list, market_context: dict) -> bool:
        """
        Send pre-market watchlist to Discord at 8:45 AM IST.
        Shows top ranked setups to watch today — bot will auto-enter if they trigger.

        Args:
            candidates: Ranked list of analysis dicts from scan_market_preopen()
            market_context: Today's market context dict
        """
        trend = market_context.get('trend', 'unknown').upper()
        nifty = market_context.get('nifty_price')
        vix = market_context.get('india_vix')
        nifty_str = f"₹{nifty:,.0f}" if isinstance(nifty, (int, float)) else "—"
        vix_str = f"{vix:.1f}" if isinstance(vix, (int, float)) else "—"

        trend_color = {
            'BULLISH': 3066993,
            'BEARISH': 15158332,
            'SIDEWAYS': 10181046,
        }.get(trend, 10181046)

        if not candidates:
            payload = {
                "embeds": [{
                    "title": f"🌅 Pre-Market Scan — {datetime.now(IST).strftime('%d %b %Y')}",
                    "description": (
                        f"**Nifty:** {nifty_str}  |  **Trend:** {trend}  |  **VIX:** {vix_str}\n\n"
                        "No actionable setups found — market may be quiet today."
                    ),
                    "color": trend_color,
                    "footer": {"text": f"Bot will scan every 5 min from 9:15 AM • {self._get_ist_time()}"}
                }]
            }
            return self._send(payload)

        # Build fields for top 8 setups
        fields = [
            {
                "name": "📊 Market Snapshot",
                "value": (
                    f"**Nifty:** {nifty_str}  **Trend:** {trend}  **VIX:** {vix_str}\n"
                    f"*{len(candidates)} setup(s) detected*"
                ),
                "inline": False
            }
        ]

        tier_icons = {'HIGH CONVICTION': '🔴', 'NORMAL': '🟠', 'CAUTIOUS': '🟡'}

        for i, opp in enumerate(candidates[:8], 1):
            sym = opp.get('symbol', '')
            patterns = opp.get('patterns', [])
            pattern_str = ', '.join(p.replace('_', ' ').title() for p in patterns[:2]) or 'n/a'
            vol_ratio = opp.get('volume_ratio', 1)
            rsi = opp.get('rsi')
            rs = opp.get('rs_positive')
            rs_str = ' 📈 Outperforming Nifty' if rs is True else (' 📉 Underperforming' if rs is False else '')
            rsi_str = f"RSI {rsi:.0f}" if rsi else ""
            chart_url = self._get_tradingview_url(sym)

            fields.append({
                "name": f"{i}. {self._clean(sym)}",
                "value": (
                    f"{pattern_str}\n"
                    f"{rsi_str}  Vol {vol_ratio:.1f}x{rs_str}\n"
                    f"[Chart]({chart_url})"
                ),
                "inline": True
            })

        fields.append({
            "name": "⚡ How it works",
            "value": "Bot will auto-enter high-scoring setups during market hours (9:15–3:30 PM).",
            "inline": False
        })

        payload = {
            "embeds": [{
                "title": f"🌅 Pre-Market Watchlist — {datetime.now(IST).strftime('%d %b %Y')}",
                "color": trend_color,
                "fields": fields,
                "footer": {
                    "text": f"Scan complete at {self._get_ist_time()} • Market opens 9:15 AM IST"
                }
            }]
        }

        success = self._send(payload)
        if success:
            logger.info(f"Discord pre-market watchlist sent ({len(candidates)} candidates)")
        return success