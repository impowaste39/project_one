"""
Email Service using Resend
Sends trade notifications and daily summaries
"""

import os
import resend
import logging
from datetime import datetime
from jinja2 import Template

logger = logging.getLogger(__name__)


class EmailService:
    """Email notification service using Resend"""

    def __init__(self):
        self.api_key = os.getenv('RESEND_API_KEY')
        self.from_email = os.getenv(
            'FROM_EMAIL', 'AI Trading Bot <trading@resend.dev>')
        self.to_email = os.getenv('NOTIFICATION_EMAIL')

        if self.api_key:
            resend.api_key = self.api_key
            logger.info("Resend email service initialized")
        else:
            logger.warning(
                "RESEND_API_KEY not configured - emails will not be sent")

    def send_email(self, subject: str, html_content: str) -> bool:
        """
        Send an email using Resend

        Args:
            subject: Email subject
            html_content: HTML body of the email

        Returns:
            True if sent successfully
        """
        if not self.api_key:
            logger.warning("Email not sent - API key not configured")
            return False

        if not self.to_email:
            logger.warning(
                "Email not sent - NOTIFICATION_EMAIL not configured")
            return False

        try:
            params = {
                "from": self.from_email,
                "to": [self.to_email],
                "subject": subject,
                "html": html_content
            }

            response = resend.Emails.send(params)
            logger.info(f"Email sent successfully: {subject}")
            return True

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False

    def send_trade_entry_email(self, trade, evaluation: dict) -> bool:
        """
        Send email notification for trade entry

        Args:
            trade: Trade object
            evaluation: Trade evaluation dict

        Returns:
            True if sent successfully
        """
        subject = f"🟢 NEW TRADE: {trade.symbol} - Score {evaluation.get('score', 0)}/100"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #16213e; border-radius: 12px; padding: 24px; }}
                .header {{ background: linear-gradient(135deg, #00d4aa, #00a67e); padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px; }}
                .header h1 {{ margin: 0; color: #fff; font-size: 24px; }}
                .stock-symbol {{ font-size: 32px; font-weight: bold; color: #00d4aa; text-align: center; margin: 16px 0; }}
                .metrics {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin: 20px 0; }}
                .metric {{ background: #0f3460; padding: 16px; border-radius: 8px; text-align: center; }}
                .metric-label {{ color: #888; font-size: 12px; text-transform: uppercase; }}
                .metric-value {{ font-size: 20px; font-weight: bold; color: #fff; margin-top: 4px; }}
                .factors {{ background: #0f3460; padding: 16px; border-radius: 8px; margin: 16px 0; }}
                .factors h3 {{ margin-top: 0; color: #00d4aa; }}
                .factors ul {{ margin: 0; padding-left: 20px; }}
                .factors li {{ margin: 8px 0; color: #ccc; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 New Trade Entry</h1>
                </div>
                
                <div class="stock-symbol">{trade.symbol.replace('.NS', '')}</div>
                
                <div class="metrics">
                    <div class="metric">
                        <div class="metric-label">Entry Price</div>
                        <div class="metric-value">₹{trade.entry_price:.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Quantity</div>
                        <div class="metric-value">{trade.quantity}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Stop Loss</div>
                        <div class="metric-value" style="color: #ff6b6b;">₹{trade.stop_loss:.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Target</div>
                        <div class="metric-value" style="color: #51cf66;">₹{trade.target:.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Investment</div>
                        <div class="metric-value">₹{trade.entry_price * trade.quantity:.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Score</div>
                        <div class="metric-value">{evaluation.get('score', 0)}/100</div>
                    </div>
                </div>
                
                <div class="factors">
                    <h3>📊 Analysis Factors</h3>
                    <ul>
                        {"".join(f"<li>{factor}</li>" for factor in evaluation.get('factors', ['No factors available']))}
                    </ul>
                </div>
                
                <div class="factors">
                    <h3>🎯 Trade Details</h3>
                    <ul>
                        <li><strong>Pattern:</strong> {trade.pattern or 'Multiple signals'}</li>
                        <li><strong>R:R Ratio:</strong> {evaluation.get('rr_ratio', 0):.2f}:1</li>
                        <li><strong>Confidence:</strong> {evaluation.get('confidence', 0) * 100:.0f}%</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p>AI Trading Bot • {datetime.now().strftime('%d %b %Y, %I:%M %p IST')}</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send_email(subject, html_content)

    def send_trade_exit_email(self, trade, exit_reason: str, insights: dict) -> bool:
        """
        Send email notification for trade exit

        Args:
            trade: Trade object with exit details
            exit_reason: Reason for exit
            insights: Analysis insights dict

        Returns:
            True if sent successfully
        """
        is_profit = trade.profit_loss is not None and trade.profit_loss >= 0
        emoji = "✅" if is_profit else "❌"
        result_text = "PROFIT" if is_profit else "LOSS"
        color = "#51cf66" if is_profit else "#ff6b6b"

        profit_pct = trade.profit_loss_pct or 0

        subject = f"{emoji} TRADE CLOSED: {trade.symbol} - {profit_pct:+.2f}%"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #16213e; border-radius: 12px; padding: 24px; }}
                .header {{ background: linear-gradient(135deg, {color}, {'#3d8c40' if is_profit else '#a63232'}); padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px; }}
                .header h1 {{ margin: 0; color: #fff; font-size: 24px; }}
                .stock-symbol {{ font-size: 32px; font-weight: bold; color: {color}; text-align: center; margin: 16px 0; }}
                .result {{ font-size: 48px; text-align: center; color: {color}; font-weight: bold; }}
                .metrics {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin: 20px 0; }}
                .metric {{ background: #0f3460; padding: 16px; border-radius: 8px; text-align: center; }}
                .metric-label {{ color: #888; font-size: 12px; text-transform: uppercase; }}
                .metric-value {{ font-size: 20px; font-weight: bold; color: #fff; margin-top: 4px; }}
                .insights {{ background: #0f3460; padding: 16px; border-radius: 8px; margin: 16px 0; }}
                .insights h3 {{ margin-top: 0; color: #00d4aa; }}
                .insights ul {{ margin: 0; padding-left: 20px; }}
                .insights li {{ margin: 8px 0; color: #ccc; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{emoji} Trade Closed - {result_text}</h1>
                </div>
                
                <div class="stock-symbol">{trade.symbol.replace('.NS', '')}</div>
                <div class="result">₹{trade.profit_loss:+.2f} ({profit_pct:+.2f}%)</div>
                
                <div class="metrics">
                    <div class="metric">
                        <div class="metric-label">Entry Price</div>
                        <div class="metric-value">₹{trade.entry_price:.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Exit Price</div>
                        <div class="metric-value">₹{trade.exit_price:.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Quantity</div>
                        <div class="metric-value">{trade.quantity}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Hold Duration</div>
                        <div class="metric-value">{trade.hold_duration_days or 0} days</div>
                    </div>
                </div>
                
                <div class="insights">
                    <h3>📝 Exit Reason</h3>
                    <p style="color: #ccc;">{exit_reason}</p>
                </div>
                
                <div class="insights">
                    <h3>💡 Insights</h3>
                    <ul>
                        {"".join(f"<li>{insight}</li>" for insight in insights.get('insights', ['No insights available']))}
                    </ul>
                </div>
                
                <div class="insights">
                    <h3>📚 Learning Points</h3>
                    <ul>
                        {"".join(f"<li>{point}</li>" for point in insights.get('learning_points', ['No learning points']))}
                    </ul>
                </div>
                
                <div class="footer">
                    <p>AI Trading Bot • {datetime.now().strftime('%d %b %Y, %I:%M %p IST')}</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send_email(subject, html_content)

    def send_daily_summary(self, summary_data: dict) -> bool:
        """
        Send end-of-day summary email

        Args:
            summary_data: Dict with performance metrics

        Returns:
            True if sent successfully
        """
        performance = summary_data.get('performance', {})
        date = summary_data.get('date', datetime.now().strftime('%d %b %Y'))

        total_pnl = performance.get('total_pnl', 0)
        is_profit = total_pnl >= 0

        subject = f"📊 Daily Summary - {date} | ₹{total_pnl:+.2f}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #16213e; border-radius: 12px; padding: 24px; }}
                .header {{ background: linear-gradient(135deg, #667eea, #764ba2); padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px; }}
                .header h1 {{ margin: 0; color: #fff; font-size: 24px; }}
                .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 20px 0; }}
                .metric {{ background: #0f3460; padding: 16px; border-radius: 8px; text-align: center; }}
                .metric-label {{ color: #888; font-size: 12px; text-transform: uppercase; }}
                .metric-value {{ font-size: 18px; font-weight: bold; color: #fff; margin-top: 4px; }}
                .section {{ background: #0f3460; padding: 16px; border-radius: 8px; margin: 16px 0; }}
                .section h3 {{ margin-top: 0; color: #00d4aa; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Daily Trading Summary</h1>
                    <p style="color: #ddd; margin: 8px 0 0 0;">{date}</p>
                </div>
                
                <div class="metrics">
                    <div class="metric">
                        <div class="metric-label">Total P&L</div>
                        <div class="metric-value" style="color: {'#51cf66' if is_profit else '#ff6b6b'};">₹{total_pnl:.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Win Rate</div>
                        <div class="metric-value">{performance.get('win_rate', 0):.1f}%</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Total Trades</div>
                        <div class="metric-value">{performance.get('total_trades', 0)}</div>
                    </div>
                </div>
                
                <div class="metrics">
                    <div class="metric">
                        <div class="metric-label">Wins</div>
                        <div class="metric-value" style="color: #51cf66;">{performance.get('wins', 0)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Losses</div>
                        <div class="metric-value" style="color: #ff6b6b;">{performance.get('losses', 0)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Expectancy</div>
                        <div class="metric-value">{performance.get('expectancy', 0):.2f}%</div>
                    </div>
                </div>
                
                <div class="section">
                    <h3>📈 Performance Highlights</h3>
                    <ul style="margin: 0; padding-left: 20px; color: #ccc;">
                        <li>Average Win: ₹{performance.get('avg_win', 0):.2f}</li>
                        <li>Average Loss: ₹{performance.get('avg_loss', 0):.2f}</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p>AI Trading Bot • End of Day Report</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send_email(subject, html_content)

    def send_alert_email(self, title: str, message: str, alert_type: str = 'info') -> bool:
        """
        Send a general alert email

        Args:
            title: Alert title
            message: Alert message
            alert_type: 'info', 'warning', or 'error'

        Returns:
            True if sent successfully
        """
        emoji_map = {'info': 'ℹ️', 'warning': '⚠️', 'error': '🚨'}
        color_map = {'info': '#00d4aa',
                     'warning': '#ffd43b', 'error': '#ff6b6b'}

        emoji = emoji_map.get(alert_type, 'ℹ️')
        color = color_map.get(alert_type, '#00d4aa')

        subject = f"{emoji} {title}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #16213e; border-radius: 12px; padding: 24px; }}
                .header {{ background: {color}; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px; }}
                .header h1 {{ margin: 0; color: #fff; font-size: 24px; }}
                .content {{ background: #0f3460; padding: 20px; border-radius: 8px; color: #ccc; line-height: 1.6; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{emoji} {title}</h1>
                </div>
                <div class="content">
                    {message}
                </div>
                <div class="footer">
                    <p>AI Trading Bot • {datetime.now().strftime('%d %b %Y, %I:%M %p IST')}</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send_email(subject, html_content)

    def send_missed_setups_email(self, missed_stocks: list, date: str = None) -> bool:
        """
        Send end-of-day email listing stocks that were evaluated but rejected today.

        Each item in missed_stocks should be a dict with:
            symbol, score, rejection_reason, rsi, volume_ratio, patterns_detected, rr_ratio

        Args:
            missed_stocks: List of evaluated-but-rejected stock dicts
            date: Optional date string (defaults to today)

        Returns:
            True if sent successfully
        """
        if not missed_stocks:
            logger.info("No missed setups to report today — skipping missed setups email")
            return True

        date = date or datetime.now().strftime('%d %b %Y')
        count = len(missed_stocks)
        subject = f"🔍 Missed Setups Today ({count} stocks) — {date}"

        def score_color(score):
            if score >= 75:
                return "#f0c040"   # amber — close call
            elif score >= 60:
                return "#6ec6ff"   # blue — moderate
            else:
                return "#aaaaaa"   # grey — weak

        rows_html = ""
        for s in missed_stocks:
            sym = s.get('symbol', '').replace('.NS', '')
            score = s.get('score', 0) or 0
            reason = s.get('rejection_reason') or 'N/A'
            rsi = s.get('rsi')
            vol = s.get('volume_ratio')
            rr = s.get('rr_ratio')
            patterns = s.get('patterns_detected') or ''

            rsi_str = f"{rsi:.1f}" if rsi else "—"
            vol_str = f"{vol:.2f}x" if vol else "—"
            rr_str = f"{rr:.2f}:1" if rr else "—"

            rows_html += f"""
            <tr>
                <td style="padding:10px 12px; font-weight:bold; font-size:15px; color:#fff;">{sym}</td>
                <td style="padding:10px 12px; text-align:center;">
                    <span style="background:{score_color(score)}; color:#111; padding:3px 10px;
                                 border-radius:12px; font-weight:bold; font-size:13px;">{score}/100</span>
                </td>
                <td style="padding:10px 12px; color:#ccc; font-size:12px;">{reason}</td>
                <td style="padding:10px 12px; color:#aaa; font-size:12px; text-align:center;">{rsi_str}</td>
                <td style="padding:10px 12px; color:#aaa; font-size:12px; text-align:center;">{vol_str}</td>
                <td style="padding:10px 12px; color:#aaa; font-size:12px; text-align:center;">{rr_str}</td>
            </tr>
            <tr>
                <td colspan="6" style="padding:2px 12px 10px; color:#555; font-size:11px; border-bottom:1px solid #1a2744;">
                    🔖 {patterns if patterns else 'No patterns detected'}
                </td>
            </tr>"""

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; margin: 0; }}
                .container {{ max-width: 700px; margin: 0 auto; background: #16213e; border-radius: 12px; padding: 24px; }}
                .header {{ background: linear-gradient(135deg, #764ba2, #667eea); padding: 20px; border-radius: 8px;
                           text-align: center; margin-bottom: 20px; }}
                .header h1 {{ margin: 0; color: #fff; font-size: 22px; }}
                .header p {{ margin: 6px 0 0 0; color: #ddd; font-size: 13px; }}
                .summary-bar {{ display: flex; gap: 12px; margin-bottom: 20px; }}
                .stat {{ flex: 1; background: #0f3460; border-radius: 8px; padding: 14px; text-align: center; }}
                .stat-val {{ font-size: 26px; font-weight: bold; color: #fff; }}
                .stat-lbl {{ font-size: 11px; color: #888; text-transform: uppercase; margin-top: 4px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                thead th {{ background: #0f3460; color: #00d4aa; font-size: 11px; text-transform: uppercase;
                             padding: 10px 12px; text-align: left; letter-spacing: 0.05em; }}
                tbody tr:nth-child(4n+1) {{ background: #111d3c; }}
                tbody tr:nth-child(4n+3) {{ background: #101935; }}
                .note {{ background: #0f3460; border-radius: 8px; padding: 14px; margin-top: 16px;
                         font-size: 12px; color: #aaa; line-height: 1.6; }}
                .footer {{ text-align: center; color: #555; font-size: 11px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔍 Missed Setups — {date}</h1>
                    <p>Stocks evaluated by the bot today that didn't meet our entry criteria</p>
                </div>

                <div class="summary-bar">
                    <div class="stat">
                        <div class="stat-val">{count}</div>
                        <div class="stat-lbl">Stocks Evaluated</div>
                    </div>
                    <div class="stat">
                        <div class="stat-val">{sum(1 for s in missed_stocks if (s.get('score') or 0) >= 60)}</div>
                        <div class="stat-lbl">Score ≥ 60</div>
                    </div>
                    <div class="stat">
                        <div class="stat-val">{sum(1 for s in missed_stocks if (s.get('score') or 0) >= 75)}</div>
                        <div class="stat-lbl">Near Miss (≥75)</div>
                    </div>
                </div>

                <table>
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th>Score</th>
                            <th>Rejection Reason</th>
                            <th>RSI</th>
                            <th>Volume</th>
                            <th>R:R</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>

                <div class="note">
                    💡 <strong>How to use this:</strong> Near-miss stocks (Score ≥ 75) are the closest to our setup.
                    Review them manually — if the rejection reason was capital or position limits rather than
                    signal quality, these would have been great trades.
                </div>

                <div class="footer">
                    <p>AI Trading Bot • Missed Setups Report • {datetime.now().strftime('%d %b %Y, %I:%M %p IST')}</p>
                </div>
            </div>
        </body>
        </html>
        """

        return self.send_email(subject, html_content)

    def send_health_alert(self, subject: str, body: str) -> bool:

        """
        Send a system health alert email.
        Called by the daily health digest job when critical issues are detected
        (e.g. 3+ consecutive zero-trade days, market context fetch failing).

        Args:
            subject: Alert subject line
            body: Plain-text alert body (will be wrapped in HTML)

        Returns:
            True if sent successfully
        """
        # Convert plain-text body to basic HTML (preserve newlines)
        html_body = body.replace('\n', '<br>')
        return self.send_alert_email(
            title=subject,
            message=html_body,
            alert_type='warning'
        )
