"""
Discord Webhook Alert Service
Sends instant trade alerts to your Discord channel — completely free!

Setup:
1. Create a Discord server (or use existing)
2. Go to channel settings → Integrations → Webhooks → New Webhook
3. Copy the webhook URL
4. Add to Render environment: DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
"""

import requests
import logging
import os
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

IST = pytz.timezone('Asia/Kolkata')


class DiscordService:
    """Sends trading alerts to Discord via webhook — zero cost"""

    def __init__(self):
        self.webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        if not self.webhook_url:
            logger.warning(
                "DISCORD_WEBHOOK_URL not set — Discord alerts disabled")

    def _get_ist_time(self) -> str:
        return datetime.now(IST).strftime('%d %b %Y, %I:%M %p IST')

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
        Called from scan_market_job() when decision == 'ENTER'
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

        # Calculate risk percent
        risk_pct = round(((entry - sl) / entry) * 100, 2) if entry > 0 else 0
        reward_pct = round(((t1 - entry) / entry) * 100, 2) if entry > 0 else 0

        # Format patterns nicely
        pattern_text = '\n'.join(
            [f"• {p.replace('_', ' ').title()}" for p in patterns]
        ) if patterns else '• No specific pattern'

        # Top 3 factors
        factors_text = '\n'.join(
            [f"• {f}" for f in factors[:3]]
        ) if factors else '• Score-based entry'

        payload = {
            "embeds": [{
                "title": f"🚨 TRADE ALERT — {symbol}",
                "color": 3066993,  # Green
                "fields": [
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
                        "name": "‎",  # Empty spacer
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
                ],
                "footer": {
                    "text": f"⚡ Place order manually on Zerodha • {self._get_ist_time()}"
                }
            }]
        }

        success = self._send(payload)
        if success:
            logger.info(f"Discord entry alert sent for {symbol}")
        return success

    def send_trade_exit_alert(self, trade, exit_reason: str, is_partial: bool = False) -> bool:
        """
        Send alert when a trade is exited (full or partial).
        Called from monitor_positions_job() on exit.
        """
        symbol = trade.symbol
        entry = trade.entry_price
        exit_price = trade.exit_price or 0
        pnl = trade.profit_loss or 0
        pnl_pct = trade.profit_loss_pct or 0
        hold_days = trade.hold_duration_days or 0

        is_profit = pnl >= 0
        color = 3066993 if is_profit else 15158332  # Green or Red
        emoji = "✅" if is_profit else "❌"
        prefix = "PARTIAL EXIT" if is_partial else "TRADE CLOSED"

        payload = {
            "embeds": [{
                "title": f"{emoji} {prefix} — {symbol}",
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
                        "value": f"**{'▲' if is_profit else '▼'} ₹{abs(pnl):.2f} ({pnl_pct:.2f}%)**",
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
        """Send alert when 50% of position is booked at T1"""
        is_profit = pnl >= 0
        color = 3066993 if is_profit else 15158332

        payload = {
            "embeds": [{
                "title": f"🎯 PARTIAL EXIT (T1 HIT) — {symbol}",
                "color": color,
                "description": "50% position booked. Stop loss moved to breakeven. Riding to T2!",
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
        Send EOD daily summary.
        Called from end_of_day_analysis_job() at 4 PM IST.
        """
        total_trades = performance.get('total_trades', 0)
        win_rate = performance.get('win_rate', 0)
        total_pnl = performance.get('total_pnl', 0)
        open_positions = performance.get('open_positions', 0)
        today_trades = performance.get('today_trades', 0)

        is_profit = total_pnl >= 0
        color = 3066993 if is_profit else 15158332
        pnl_emoji = "📈" if is_profit else "📉"

        payload = {
            "embeds": [{
                "title": f"📊 Daily Summary — {datetime.now(IST).strftime('%d %b %Y')}",
                "color": color,
                "fields": [
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
                ],
                "footer": {
                    "text": f"Market closed • {self._get_ist_time()}"
                }
            }]
        }

        success = self._send(payload)
        if success:
            logger.info("Discord daily summary sent")
        return success

    def send_health_alert(self, subject: str, body: str) -> bool:
        """Send system health alert"""
        payload = {
            "embeds": [{
                "title": f"🚨 {subject}",
                "description": body,
                "color": 15158332,  # Red
                "footer": {
                    "text": self._get_ist_time()
                }
            }]
        }
        return self._send(payload)
