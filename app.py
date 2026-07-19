"""
AI Trading Bot - Main Flask Application
Autonomous swing trading bot for Indian stock market
"""

from flask import Flask, render_template, jsonify, request, abort
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from datetime import datetime
from functools import wraps
import os
import logging
import atexit
import pytz
import traceback

# Import core modules
from models.database import init_database, get_session, Portfolio, Trade
from core.market_monitor import MarketMonitor
from core.trading_brain import TradingBrain
from core.portfolio_manager import PortfolioManager
from core.risk_manager import RiskManager
from core.learning_engine import LearningEngine
from services.email_service import EmailService
from services.data_service import DataService
from services.discord_service import DiscordService
from services.reporting_service import ReportingService
from utils.helpers import get_ist_now, is_market_hours, get_market_status_message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv(
    'SECRET_KEY', 'dev-secret-key-change-in-production')
CORS(app)

# Initialize database
init_database()

# Initialize services
email_service = EmailService()
data_service = DataService()
discord_service = DiscordService()

# Timezone
IST = pytz.timezone('Asia/Kolkata')

# Startup timestamp — used by scan_market_job to skip scans during cold-start warmup
_APP_START_TIME = datetime.now(IST)
# Skip scans for 60s after startup (Render cold start takes 30-60s)
_WARMUP_SECONDS = 60

# ---------------------------------------------------------------------------
# Error alert rate-limiter: prevents a flapping job from spamming Discord.
# We track the last alert time per job name and suppress duplicates within
# ERROR_ALERT_COOLDOWN_SECONDS (default 10 min).
# ---------------------------------------------------------------------------
import time as _time
_last_error_alert: dict = {}
_ERROR_ALERT_COOLDOWN_SECONDS = 600  # 10 minutes


def _send_error_alert_guarded(job_name: str, exc: Exception) -> None:
    """Send a Discord error alert at most once per cooldown window per job."""
    now = _time.monotonic()
    last = _last_error_alert.get(job_name, 0)
    if now - last < _ERROR_ALERT_COOLDOWN_SECONDS:
        logger.debug(
            f"Error alert for '{job_name}' suppressed (cooldown active, "            f"{int(_ERROR_ALERT_COOLDOWN_SECONDS - (now - last))}s remaining)"
        )
        return
    _last_error_alert[job_name] = now
    try:
        discord_service.send_error_alert(
            job_name=job_name,
            error=exc,
            traceback_str=traceback.format_exc()
        )
    except Exception as alert_err:
        logger.warning(f"Could not send Discord error alert: {alert_err}")

# ---------------------------------------------------------------------------
# Singletons: TradingBrain and LearningEngine are expensive to construct
# (DB query + RandomForestClassifier init on every call).  We create each
# once and reuse them across all scheduler jobs, re-attaching a fresh DB
# session before each use so there is no stale-connection risk.
# ---------------------------------------------------------------------------
_brain_singleton: TradingBrain = None
_learning_engine_singleton: LearningEngine = None


def _get_brain(db_session, risk_manager=None) -> TradingBrain:
    """Return the shared TradingBrain, binding it to the current DB session."""
    global _brain_singleton
    if _brain_singleton is None:
        _brain_singleton = TradingBrain(db_session, risk_manager)
        logger.info("TradingBrain singleton created")
    else:
        # Re-attach a fresh session for this job's transaction scope
        _brain_singleton.db = db_session
        if risk_manager is not None:
            _brain_singleton.risk_manager = risk_manager
    return _brain_singleton


def _get_learning_engine(db_session) -> LearningEngine:
    """Return the shared LearningEngine, binding it to the current DB session."""
    global _learning_engine_singleton
    if _learning_engine_singleton is None:
        _learning_engine_singleton = LearningEngine(db_session)
        logger.info("LearningEngine singleton created")
    else:
        _learning_engine_singleton.db = db_session
    return _learning_engine_singleton

# API Security


def require_api_key(f):
    """Decorator to require a secret API key for sensitive endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = os.getenv('API_WEBHOOK_KEY')

        # If no key is set, it's open (not recommended)
        if not api_key:
            return f(*args, **kwargs)

        request_key = request.headers.get('X-API-KEY')
        if not request_key or request_key != api_key:
            logger.warning(
                f"Unauthorized API access attempt from {request.remote_addr}")
            return jsonify({'error': 'Unauthorized', 'message': 'Invalid or missing API key'}), 401

        return f(*args, **kwargs)
    return decorated_function


# Scheduler
scheduler = BackgroundScheduler(
    jobstores={'default': MemoryJobStore()},
    job_defaults={'coalesce': True, 'max_instances': 1, 'misfire_grace_time': 60},
    timezone=IST,
    daemon=True,
)


def initialize_portfolio():
    """Initialize portfolio with starting capital if not exists"""
    with get_session() as db:
        portfolio_count = db.query(Portfolio).count()

        if portfolio_count == 0:
            initial_capital = float(os.getenv('INITIAL_CAPITAL', 5000))

            portfolio = Portfolio(
                total_capital=initial_capital,
                deployed_capital=0,
                available_capital=initial_capital,
                unrealized_pnl=0,
                realized_pnl=0,
                total_return_pct=0,
                open_positions=0
            )

            db.add(portfolio)
            db.commit()

            logger.info(f"Portfolio initialized with ₹{initial_capital}")
        else:
            logger.info("Portfolio already exists")


# ===== SCHEDULED JOBS =====

def scan_market_job():
    """Market scanning job - runs every 5 minutes during market hours"""
    if not is_market_hours():
        logger.debug("Market closed - skipping scan")
        return

    # Guard: skip scans before NSE opens at 9:15 AM IST to avoid stale
    # previous-day data being treated as intraday signals
    if not data_service.is_market_open():
        logger.info(
            "Market not yet open (pre-9:15 AM) — skipping scan to avoid stale data")
        return

    # Guard: skip scans during cold-start warmup window (Render takes 30-60s to fully start)
    # APScheduler fires missed jobs immediately after startup; this prevents a scan
    # from running before the app is fully initialised.
    uptime_seconds = (datetime.now(IST) - _APP_START_TIME).total_seconds()
    if uptime_seconds < _WARMUP_SECONDS:
        logger.info(
            f"Cold-start warmup ({uptime_seconds:.0f}s < {_WARMUP_SECONDS}s) — skipping scan")
        return

    scan_start_time = datetime.now(IST)

    try:
        logger.info("=" * 50)
        logger.info("MARKET SCAN STARTED")
        logger.info("=" * 50)

        with get_session() as db:
            # Initialize components
            from services.reporting_service import ReportingService

            monitor = MarketMonitor(db)
            risk_manager = RiskManager()
            brain = _get_brain(db, risk_manager)          # reused singleton
            portfolio_mgr = PortfolioManager(db, risk_manager, email_service)
            reporting_service = ReportingService(db)

            # Get market context
            market_context = monitor.get_market_context()
            logger.info(
                f"Market Context: {market_context.get('trend', 'unknown')} trend")

            # Get portfolio state
            portfolio_state = portfolio_mgr.get_portfolio_state()

            # Scan market for opportunities
            opportunities = monitor.scan_market()

            # Calculate scan duration
            scan_duration = (datetime.now(IST) - scan_start_time).total_seconds()

            # Track scan statistics
            scan_stats = {
                'total_scanned': len(monitor.watchlist),
                'opportunities_found': len(opportunities),
                'trades_entered': 0
            }

            # Save scan report
            scan_report = reporting_service.save_scan_report(
                market_context, scan_stats, scan_duration
            )
            scan_report_id = scan_report.id if scan_report else None

            if not opportunities:
                logger.info("No trading opportunities found")
                return

            logger.info(f"Found {len(opportunities)} potential opportunities")

            # Pre-filter: build set of currently held symbols once before the loop.
            held_symbols = {
                t.symbol
                for t in db.query(Trade).filter(Trade.status == 'OPEN').all()
            }

            # Pre-compute adaptive thresholds once — avoids per-stock DB query inside loop
            brain.prime_adaptive_thresholds()

            # Evaluate each opportunity
            for opp in opportunities:
                try:
                    symbol = opp['symbol']

                    # Skip full evaluation for already-held positions
                    if symbol in held_symbols:
                        logger.info(f"⏭️  SKIPPED (already held): {symbol}")
                        # Still record the pattern occurrence for the learning engine
                        if scan_report_id and opp.get('patterns'):
                            skip_eval = {
                                'score': 0,
                                'decision': 'PASS',
                                'reason': f'Duplicate guard: {symbol} already held in portfolio',
                                'patterns': opp.get('patterns', []),
                                'weekly_ema_status': 'unknown',
                                'weekly_ema_reason': '',
                                'ema_penalty_applied': False,
                                'position_tier': 'CAUTIOUS',
                                'ml_model_active': False,
                            }
                            reporting_service._save_pattern_occurrences(
                                opp, skip_eval, scan_report_id
                            )
                        continue

                    evaluation = brain.evaluate_opportunity(
                        opp, market_context, portfolio_state)

                    # Always save pattern occurrences (for learning) regardless of score
                    if scan_report_id and opp.get('patterns'):
                        reporting_service._save_pattern_occurrences(
                            opp, evaluation, scan_report_id
                        )

                    # Save scan result (filtered by MIN_SCORE_TO_SAVE)
                    if scan_report_id:
                        reporting_service.save_scan_result(
                            scan_report_id, opp, evaluation
                        )

                    # Log detailed evaluation
                    logger.info(
                        f"📊 {opp['symbol']}: Score={evaluation['score']}/100, "
                        f"Decision={evaluation['decision']}, Reason={evaluation['reason']}"
                    )

                    if evaluation['decision'] == 'ENTER':
                        # Send Discord alert BEFORE entering trade
                        discord_service.send_trade_entry_alert(evaluation)

                        success = portfolio_mgr.enter_trade(evaluation)
                        if success:
                            logger.info(
                                f"✅ TRADE EXECUTED: {evaluation['symbol']} @ ₹{evaluation['entry_price']}")
                            scan_stats['trades_entered'] += 1
                            portfolio_state = portfolio_mgr.get_portfolio_state()
                            # Refresh held_symbols so the same ticker is not
                            # re-evaluated if it appears again in this scan cycle
                            held_symbols.add(symbol)
                    else:
                        logger.info(
                            f"⏭️  PASSED: {opp['symbol']} - {evaluation['reason']}")

                except Exception as e:
                    logger.error(f"Error evaluating {opp['symbol']}: {e}")
                    continue

            # Update scan report with final trade count
            if scan_report_id and scan_stats['trades_entered'] > 0:
                from models.scan_report import ScanReport as SR
                live_report = db.query(SR).filter_by(id=scan_report_id).first()
                if live_report:
                    live_report.trades_entered = scan_stats['trades_entered']
                    db.commit()

            logger.info(
                f"Market scan completed - {scan_stats['trades_entered']} trades entered")

    except Exception as e:
        logger.error(f"Error in market scan job: {e}")
        _send_error_alert_guarded("Market Scan", e)


def monitor_positions_job():
    """Position monitoring job - runs every 2 minutes during market hours"""
    if not is_market_hours():
        return

    try:
        logger.info("Monitoring open positions...")

        with get_session() as db:
            # Initialize components
            monitor = MarketMonitor(db)
            brain = _get_brain(db)                        # reused singleton
            portfolio_mgr = PortfolioManager(db, None, email_service)
            learning_engine = _get_learning_engine(db)   # reused singleton

            # Get open positions
            open_trades = db.query(Trade).filter(Trade.status == 'OPEN').all()

            if not open_trades:
                logger.debug("No open positions to monitor")
                return

            logger.info(f"Monitoring {len(open_trades)} open positions")

            # BATCH FETCH PRICES: Single API call to avoid database connection timeouts
            symbols = [t.symbol for t in open_trades]
            batch_prices = monitor.data_service.get_batch_prices(symbols)

            for trade in open_trades:
                try:
                    if trade.symbol not in batch_prices:
                        logger.warning(f"Could not fetch data for {trade.symbol}")
                        continue

                    current_price = batch_prices[trade.symbol]

                    # Check exit conditions (pass None for data as it only needs current_price)
                    exit_decision = brain.check_exit_conditions(
                        trade, current_price, None)

                    if exit_decision['action'] == 'PARTIAL_EXIT':
                        # Book 50% of position at T1, move SL to breakeven
                        partial_qty = max(1, trade.quantity // 2)
                        partial_pnl = round(
                            (current_price - trade.entry_price) * partial_qty, 2)

                        # Update trade in DB
                        trade.partially_exited = True
                        trade.partial_exit_price = current_price
                        trade.partial_exit_qty = partial_qty
                        trade.partial_exit_date = datetime.now(IST).replace(tzinfo=None)  # FIX: naive datetime for DB
                        trade.stop_loss = trade.entry_price  # Move SL to breakeven
                        db.commit()

                        # Send Discord alert for partial exit
                        discord_service.send_partial_exit_alert(
                            symbol=trade.symbol,
                            entry_price=trade.entry_price,
                            exit_price=current_price,
                            quantity_exited=partial_qty,
                            pnl=partial_pnl
                        )
                        logger.info(
                            f"🎯 PARTIAL EXIT: {trade.symbol} @ ₹{current_price:.2f} "
                            f"({partial_qty} shares booked, P&L: ₹{partial_pnl})")

                    elif exit_decision['action'] == 'EXIT':
                        success = portfolio_mgr.exit_trade(
                            trade,
                            current_price,
                            exit_decision['reason']
                        )

                        if success:
                            logger.info(
                                f"🔴 TRADE EXITED: {trade.symbol} @ ₹{current_price:.2f}")

                            # Refresh trade from DB
                            db.refresh(trade)

                            # Analyze trade for learning
                            insights = learning_engine.analyze_completed_trade(
                                trade)

                            # Send Discord exit alert
                            discord_service.send_trade_exit_alert(
                                trade, exit_decision['reason'])

                            # Send exit email as backup
                            email_service.send_trade_exit_email(
                                trade, exit_decision['reason'], insights)
                    else:
                        unrealized_pnl = (
                            current_price - trade.entry_price) * trade.quantity
                        logger.debug(
                            f"HOLDING {trade.symbol}: ₹{current_price:.2f}, P&L: ₹{unrealized_pnl:.2f}")

                except Exception as e:
                    logger.error(f"Error monitoring {trade.symbol}: {e}")
                    continue

            # ── UPDATE UNREALIZED P&L ─────────────────────────────────────────
            try:
                current_prices = {}
                still_open = db.query(Trade).filter(Trade.status == 'OPEN').all()
                for t in still_open:
                    if t.symbol in batch_prices:
                        current_prices[t.symbol] = batch_prices[t.symbol]
                    else:
                        price = monitor.data_service.get_current_price(t.symbol)
                        if price is not None:
                            current_prices[t.symbol] = float(price)
                if current_prices:
                    portfolio_mgr.update_unrealized_pnl(current_prices)
                    logger.debug(f"Unrealized P&L updated for {len(current_prices)} positions")
            except Exception as pnl_err:
                logger.debug(f"Unrealized P&L update skipped: {pnl_err}")
            # ─────────────────────────────────────────────────────

            logger.info("Position monitoring completed")

    except Exception as e:
        logger.error(f"Error in position monitoring job: {e}")
        _send_error_alert_guarded("Position Monitor", e)


def end_of_day_analysis_job():
    """End of day analysis and learning - runs at 4:00 PM IST"""
    try:
        logger.info("=" * 50)
        logger.info("END OF DAY ANALYSIS")
        logger.info("=" * 50)

        with get_session() as db:
            learning_engine = LearningEngine(db)
            brain = TradingBrain(db, None)
            portfolio_mgr = PortfolioManager(db, None, email_service)

            # Generate performance report
            performance = learning_engine.generate_performance_report()

            logger.info(f"Performance Summary:")
            logger.info(f"  Total Trades: {performance.get('total_trades', 0)}")
            logger.info(f"  Win Rate: {performance.get('win_rate', 0):.2f}%")
            logger.info(f"  Total P&L: ₹{performance.get('total_pnl', 0):.2f}")

            # Send daily summary email
            summary_data = {
                'date': datetime.now(IST).strftime('%d %b %Y'),
                'performance': performance
            }

            # FIX: compute open_positions and today_trades separately
            open_positions_count = db.query(Trade).filter(Trade.status == 'OPEN').count()
            today_date = datetime.now(IST).date()
            today_start_dt = datetime(today_date.year, today_date.month, today_date.day)
            today_trades_count = db.query(Trade).filter(
                Trade.entry_date >= today_start_dt
            ).count()

            today_closed_trades = db.query(Trade).filter(
                Trade.status == 'CLOSED',
                Trade.exit_date >= today_start_dt
            ).all()

            today_gross_pnl = sum(t.gross_profit_loss for t in today_closed_trades if t.gross_profit_loss is not None)
            today_charges = sum(t.brokerage_charges for t in today_closed_trades if t.brokerage_charges is not None)
            today_net_pnl = sum(t.profit_loss for t in today_closed_trades if t.profit_loss is not None)

            last_20_trades = db.query(Trade).filter(Trade.status == 'CLOSED').order_by(Trade.exit_date.desc()).limit(20).all()
            if last_20_trades:
                wins_20 = sum(1 for t in last_20_trades if t.profit_loss and t.profit_loss > 0)
                rolling_win_rate = (wins_20 / len(last_20_trades)) * 100
            else:
                rolling_win_rate = 0.0

            rejected_setups_count = 0
            try:
                from models.scan_report import ScanReport, ScanResult
                from datetime import timedelta
                today_scan_ids = [
                    r.id for r in db.query(ScanReport).filter(
                        ScanReport.timestamp >= today_start_dt,
                        ScanReport.timestamp < today_start_dt + timedelta(days=1)
                    ).all()
                ]
                if today_scan_ids:
                    rejected_results = db.query(ScanResult).filter(
                        ScanResult.scan_report_id.in_(today_scan_ids),
                        ScanResult.decision == 'PASS'
                    ).all()
                    rejected_symbols = {r.symbol for r in rejected_results}
                    rejected_setups_count = len(rejected_symbols)
            except Exception as scan_count_err:
                logger.error(f"Error counting rejected setups for EOD: {scan_count_err}")

            discord_data = {
                'total_trades': performance.get('total_trades', 0),
                'win_rate': performance.get('win_rate', 0),
                'total_pnl': performance.get('total_pnl', 0),
                'open_positions': open_positions_count,
                'today_trades': today_trades_count,
                'today_closed_count': len(today_closed_trades),
                'today_gross_pnl': today_gross_pnl,
                'today_charges': today_charges,
                'today_net_pnl': today_net_pnl,
                'rolling_win_rate': rolling_win_rate,
                'rejected_setups_count': rejected_setups_count,
            }

            weekly_summary = portfolio_mgr.get_weekly_pnl_summary()
            if weekly_summary:
                discord_data.update(weekly_summary)

            discord_service.send_daily_summary(discord_data)
            email_service.send_daily_summary(summary_data)

            # ── MISSED SETUPS EMAIL ──────────────────────────────────────────────
            try:
                from models.scan_report import ScanReport, ScanResult
                from datetime import timedelta

                today_start = datetime(today_date.year, today_date.month, today_date.day)
                today_end = today_start + timedelta(days=1)

                today_scan_ids = [
                    r.id for r in db.query(ScanReport).filter(
                        ScanReport.timestamp >= today_start,
                        ScanReport.timestamp < today_end
                    ).all()
                ]

                if today_scan_ids:
                    passed_results = db.query(ScanResult).filter(
                        ScanResult.scan_report_id.in_(today_scan_ids),
                        ScanResult.decision == 'PASS'
                    ).all()

                    # Deduplicate: keep the highest-score row per symbol
                    seen = {}
                    for row in passed_results:
                        sym = row.symbol
                        score = row.total_score or 0
                        if sym not in seen or score > (seen[sym].total_score or 0):
                            seen[sym] = row

                    # Sort: near-misses (score >= 75) first, then descending
                    missed_list = sorted(
                        seen.values(),
                        key=lambda r: (r.total_score or 0),
                        reverse=True
                    )

                    missed_stocks = [
                        {
                            'symbol': r.symbol,
                            'score': r.total_score,
                            'rejection_reason': r.rejection_reason,
                            'rsi': r.rsi,
                            'volume_ratio': r.volume_ratio,
                            'rr_ratio': r.rr_ratio,
                            'patterns_detected': r.patterns_detected,
                        }
                        for r in missed_list
                    ]

                    logger.info(
                        f"EOD: {len(missed_stocks)} missed setups found — sending missed setups email"
                    )
                    email_service.send_missed_setups_email(
                        missed_stocks,
                        date=datetime.now(IST).strftime('%d %b %Y')
                    )
                else:
                    logger.info("EOD: No scan reports found for today — skipping missed setups email")

            except Exception as missed_err:
                logger.error(f"Error collecting missed setups for EOD email: {missed_err}")
            # ─────────────────────────────────────────────────────────────────────

            logger.info("End of day analysis completed")

    except Exception as e:
        logger.error(f"Error in EOD analysis: {e}")
        _send_error_alert_guarded("EOD Analysis", e)


def premarket_scan_job():
    """
    Pre-market scan — runs at 8:45 AM IST Mon-Fri.
    """
    if os.getenv('PRE_MARKET_SCAN_ENABLED', 'true').lower() != 'true':
        logger.info("Pre-market scan disabled via PRE_MARKET_SCAN_ENABLED=false")
        return

    logger.info("=" * 50)
    logger.info("PRE-MARKET SCAN STARTED")
    logger.info("=" * 50)

    try:
        with get_session() as db:
            monitor = MarketMonitor(db)
            brain = TradingBrain(db, None)

            # Step 1: Get market context for the Discord embed header
            market_context = monitor.get_market_context()

            # Step 2: Scan all watchlist stocks (uses yesterday's closes)
            candidates = monitor.scan_market_preopen()

            # Step 3: Score each candidate
            scored = []
            for analysis in candidates:
                try:
                    score_breakdown = brain.calculate_setup_score(analysis, market_context)
                    levels = brain.calculate_entry_exit_levels(analysis)
                    evaluation = {
                        'symbol': analysis['symbol'],
                        'score': score_breakdown['total_score'],
                        'patterns': analysis.get('patterns', []),
                        'entry_price': levels.get('entry_price'),
                        'stop_loss': levels.get('stop_loss'),
                        'target_1': levels.get('target_1'),
                        'rr_ratio': levels.get('rr_ratio'),
                        'rs_positive': analysis.get('rs_positive'),
                        'rsi': analysis.get('rsi'),
                        'volume_ratio': analysis.get('volume_ratio'),
                        'position_tier': 'NORMAL',
                    }
                    scored.append(evaluation)
                except Exception as score_err:
                    logger.debug(f"Pre-market scoring error for {analysis.get('symbol')}: {score_err}")

            # Sort by score descending
            scored.sort(key=lambda x: x.get('score', 0), reverse=True)

            # Step 4: Send Discord embed
            discord_service.send_premarket_watchlist(scored, market_context)
            logger.info(f"Pre-market scan complete — {len(scored)} candidates sent to Discord")

    except Exception as e:
        logger.error(f"Error in pre-market scan job: {e}")


def weekly_portfolio_cleanup_job():
    """
    Weekly portfolio row cleanup — runs every Saturday at 6:00 AM IST.
    """
    try:
        with get_session() as db:
            latest = db.query(Portfolio).order_by(
                Portfolio.timestamp.desc()
            ).first()

            if not latest:
                logger.info("Portfolio cleanup: no portfolio rows found, nothing to do")
                return

            deleted = db.query(Portfolio).filter(
                Portfolio.id != latest.id
            ).delete(synchronize_session=False)

            db.commit()
            if deleted > 0:
                logger.info(f"Portfolio cleanup: removed {deleted} stale history rows (kept latest id={latest.id})")
            else:
                logger.info("Portfolio cleanup: nothing to delete — already clean")

    except Exception as e:
        logger.error(f"Error in portfolio cleanup job: {e}")

    try:
        with get_session() as db:
            reporting = ReportingService(db)
            reporting.cleanup_old_data()
    except Exception as e:
        logger.error(f"Error in scan-data cleanup job: {e}")


def daily_health_digest_job():
    """
    Daily system health digest - runs at 3:35 PM IST (after market close).
    """
    try:
        logger.info("Running daily health digest...")

        zero_days = _get_consecutive_zero_trade_days()
        context_ok = True

        try:
            monitor = MarketMonitor()
            ctx = monitor.get_market_context()
            context_ok = not ctx.get('fetch_failed', False)
        except Exception as e:
            context_ok = False
            logger.error(f"Health digest: market context check failed: {e}")

        alert_conditions = []

        if zero_days >= 3:
            alert_conditions.append(
                f"Bot has executed 0 trades for {zero_days} consecutive trading days."
            )

        if not context_ok:
            alert_conditions.append(
                "Nifty market context fetch is failing — scoring is using fallback values. "
                "Market context score may be inaccurate."
            )

        if alert_conditions:
            alert_body = (
                f"\U0001f6a8 Trading Bot Health Alert — {datetime.now(IST).strftime('%d %b %Y')}\n\n"
                + "\n".join(f"- {c}" for c in alert_conditions)
                + "\n\nAction required: check /health and /api/rejection-analysis endpoints."
            )
            logger.warning(
                f"Health digest: sending alert ({len(alert_conditions)} issue(s))")
            email_service.send_health_alert(
                subject=f"Trading Bot Alert: {len(alert_conditions)} issue(s) detected",
                body=alert_body
            )
        else:
            logger.info(
                f"Health digest: system OK — zero_trade_days={zero_days}, context_ok={context_ok}"
            )

    except Exception as e:
        logger.error(f"Error in daily health digest job: {e}")


scheduler.add_job(
    scan_market_job,
    'cron',
    day_of_week='mon-fri',
    hour='9-15',
    minute='*/10',
    id='market_scan'
)

scheduler.add_job(
    monitor_positions_job,
    'cron',
    day_of_week='mon-fri',
    hour='9-15',
    minute='2-57/5',
    id='position_monitor'
)

scheduler.add_job(
    end_of_day_analysis_job,
    'cron',
    day_of_week='mon-fri',
    hour=16,
    minute=0,
    id='eod_analysis'
)

scheduler.add_job(
    daily_health_digest_job,
    'cron',
    day_of_week='mon-fri',
    hour=15,
    minute=35,
    id='daily_health_digest'
)

# Pre-market scan: 8:45 AM IST Mon-Fri — surfaces top setups before market opens
scheduler.add_job(
    premarket_scan_job,
    'cron',
    day_of_week='mon-fri',
    hour=8,
    minute=45,
    id='premarket_scan'
)

# Weekly portfolio cleanup: Saturday 6:00 AM IST
scheduler.add_job(
    weekly_portfolio_cleanup_job,
    'cron',
    day_of_week='sat',
    hour=6,
    minute=0,
    id='weekly_portfolio_cleanup'
)

# Start scheduler
scheduler.start()
logger.info("Scheduler started successfully")

# Shutdown scheduler on app exit
atexit.register(lambda: scheduler.shutdown())

# Initialize portfolio on startup
initialize_portfolio()


def _get_consecutive_zero_trade_days() -> int:
    """Count how many consecutive trading days have had zero trades entered"""
    try:
        with get_session() as db:
            from models.scan_report import ScanReport
            from datetime import timedelta

            # Check last 14 days of scan reports grouped by date
            cutoff = datetime.now(IST) - timedelta(days=14)
            recent_scans = db.query(ScanReport).filter(
                ScanReport.timestamp >= cutoff
            ).order_by(ScanReport.timestamp.desc()).all()

            if not recent_scans:
                return 0

            # Group by date and check consecutive zero-trade days
            date_trades = {}
            for scan in recent_scans:
                day = scan.timestamp.date()
                date_trades.setdefault(day, 0)
                date_trades[day] += scan.trades_entered or 0

            # Count from today backwards
            consecutive = 0
            check_date = datetime.now(IST).date()
            for _ in range(14):
                if check_date.weekday() >= 5:  # skip weekends
                    check_date -= timedelta(days=1)
                    continue
                if date_trades.get(check_date, 0) == 0:
                    consecutive += 1
                    check_date -= timedelta(days=1)
                else:
                    break
            return consecutive
    except Exception as e:
        logger.error(f"Error counting zero trade days: {e}")
        return 0


# ===== FLASK ROUTES =====

@app.route('/')
def dashboard():
    """Main dashboard"""
    with get_session() as db:
        # Get portfolio
        portfolio = db.query(Portfolio).order_by(
            Portfolio.timestamp.desc()).first()

        # Get trades
        all_trades = db.query(Trade).order_by(
            Trade.entry_date.desc()).limit(50).all()
        open_trades = [t for t in all_trades if t.status == 'OPEN']
        closed_trades = [t for t in all_trades if t.status == 'CLOSED'][:20]

        # Calculate statistics
        total_closed = db.query(Trade).filter(Trade.status == 'CLOSED').count()
        winning_trades = db.query(Trade).filter(
            Trade.status == 'CLOSED',
            Trade.profit_loss > 0
        ).count()

        win_rate = (winning_trades / total_closed *
                    100) if total_closed > 0 else 0

        # Pull only the plain data we need before the session closes —
        # avoids holding a DB connection during the slow yfinance call below
        open_symbols = list({t.symbol for t in open_trades})

    # --- DB session is closed here; connection returned to pool ---
    
    current_prices = {}
    if open_symbols:
        from services.data_service import DataService
        ds = DataService()
        try:
            current_prices = ds.get_batch_prices(open_symbols)
        except Exception as price_err:
            logger.warning(f"Could not fetch current prices for dashboard: {price_err}")
    
    # Market status
    market_status = get_market_status_message()

    return render_template(
        'dashboard.html',
        portfolio=portfolio,
        open_trades=open_trades,
        closed_trades=closed_trades,
        win_rate=win_rate,
        total_trades=total_closed,
        market_status=market_status,
        now=datetime.now(IST),
        current_prices=current_prices
    )


@app.route('/api/portfolio')
def api_portfolio():
    """Portfolio API endpoint"""
    with get_session() as db:
        portfolio = db.query(Portfolio).order_by(
            Portfolio.timestamp.desc()).first()

        if not portfolio:
            return jsonify({
                'total_capital': 5000,
                'available_capital': 5000,
                'deployed_capital': 0,
                'unrealized_pnl': 0,
                'realized_pnl': 0,
                'total_return_pct': 0,
                'open_positions': 0
            })

        return jsonify(portfolio.to_dict())


@app.route('/api/trades')
def api_trades():
    """Trades API endpoint"""
    with get_session() as db:
        trades = db.query(Trade).order_by(
            Trade.entry_date.desc()).limit(100).all()
        return jsonify([trade.to_dict() for trade in trades])


@app.route('/api/open-positions')
def api_open_positions():
    """Open positions API endpoint"""
    with get_session() as db:
        open_trades = db.query(Trade).filter(Trade.status == 'OPEN').all()
        return jsonify([trade.to_dict() for trade in open_trades])


@app.route('/health')
def health():
    """Health check endpoint for UptimeRobot"""
    db_status = "unknown"
    ml_health = {
        'is_trained': False,
        'closed_trades_count': 0,
        'trades_needed_for_training': 20
    }

    try:
        with get_session() as db:
            db.query(Portfolio).first()
            db_status = "connected"

            # Check ML model status
            brain = _get_brain(db)
            is_trained = brain.is_model_trained()
            closed_count = db.query(Trade).filter(Trade.status == 'CLOSED').count()
            ml_health = {
                'is_trained': is_trained,
                'closed_trades_count': closed_count,
                'trades_needed_for_training': max(0, 20 - closed_count) if not is_trained else 0
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = f"error: {str(e)}"

    # Check if market context is working (Nifty fetch is live)
    context_working = True
    try:
        monitor = MarketMonitor()
        ctx = monitor.get_market_context()
        context_working = not ctx.get('fetch_failed', False)
    except Exception:
        context_working = False

    zero_trade_days = _get_consecutive_zero_trade_days()

    overall_healthy = (db_status == "connected")

    return jsonify({
        'status': 'healthy' if overall_healthy else 'unhealthy',
        'database': db_status,
        'ml_health': ml_health,
        'market_context_working': context_working,
        'consecutive_zero_trade_days': zero_trade_days,
        'timestamp': datetime.now(IST).isoformat(),
        'scheduler_running': scheduler.running,
        'market_status': get_market_status_message()
    }), 200 if overall_healthy else 500


@app.route('/api/performance')
@require_api_key
def api_performance():
    """Performance metrics API"""
    with get_session() as db:
        learning_engine = LearningEngine(db)
        performance = learning_engine.generate_performance_report()
        return jsonify(performance)


@app.route('/api/market-context')
@require_api_key
def api_market_context():
    """Get current market context"""
    try:
        monitor = MarketMonitor()
        context = monitor.get_market_context()
        context['market_status'] = get_market_status_message()
        return jsonify(context)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trigger-scan', methods=['POST'])
@require_api_key
def trigger_scan():
    """Manually trigger a market scan"""
    try:
        scan_market_job()
        return jsonify({'status': 'Scan triggered successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scan-history')
def api_scan_history():
    """Get recent scan history"""
    try:
        with get_session() as db:
            from services.reporting_service import ReportingService
            reporting = ReportingService(db)
            limit = request.args.get('limit', 20, type=int)
            history = reporting.get_scan_history(limit=limit)
            return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scan-details/<int:scan_id>')
def api_scan_details(scan_id):
    """Get detailed results for a specific scan"""
    try:
        with get_session() as db:
            from services.reporting_service import ReportingService
            reporting = ReportingService(db)
            details = reporting.get_scan_details(scan_id)
            if not details:
                return jsonify({'error': 'Scan not found'}), 404
            return jsonify(details)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pattern-performance')
def api_pattern_performance():
    """Get pattern performance statistics"""
    try:
        with get_session() as db:
            from services.reporting_service import ReportingService
            reporting = ReportingService(db)
            days = request.args.get('days', 30, type=int)
            stats = reporting.get_pattern_statistics(days=days)
            return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rejection-analysis')
def api_rejection_analysis():
    """Get analysis of why opportunities are being rejected"""
    try:
        with get_session() as db:
            from services.reporting_service import ReportingService
            reporting = ReportingService(db)
            days = request.args.get('days', 7, type=int)
            analysis = reporting.get_rejection_analysis(days=days)
            return jsonify(analysis)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/learning-insights')
def api_learning_insights():
    """Get AI learning insights"""
    try:
        with get_session() as db:
            learning_engine = LearningEngine(db)
            insights = learning_engine.generate_learning_insights()
            return jsonify(insights)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trades/summary')
def api_trades_summary():
    """
    Comprehensive trade summary with real P&L (after Groww charges).
    """
    try:
        with get_session() as db:
            all_trades = db.query(Trade).order_by(Trade.entry_date.desc()).all()
            closed = [t for t in all_trades if t.status == 'CLOSED']
            open_trades = [t for t in all_trades if t.status == 'OPEN']

            wins = [t for t in closed if t.profit_loss and t.profit_loss > 0]
            losses = [t for t in closed if t.profit_loss and t.profit_loss <= 0]

            total_net_pnl = sum(
                t.profit_loss for t in closed if t.profit_loss) or 0
            total_gross_pnl = sum(t.gross_profit_loss for t in closed
                                  if t.gross_profit_loss) or 0
            total_charges = sum(t.brokerage_charges for t in closed
                                if t.brokerage_charges) or 0

            win_rate = (len(wins) / len(closed) * 100) if closed else 0
            avg_win = (sum(t.profit_loss for t in wins) / len(wins)) if wins else 0
            avg_loss = (sum(abs(t.profit_loss)
                        for t in losses) / len(losses)) if losses else 0
            avg_hold = (sum(t.hold_duration_days for t in closed
                            if t.hold_duration_days) / len(closed)) if closed else 0

            # Pattern breakdown
            pattern_stats = {}
            for t in closed:
                p = t.pattern or 'unknown'
                if p not in pattern_stats:
                    pattern_stats[p] = {'trades': 0, 'wins': 0, 'total_pnl': 0.0,
                                        'total_charges': 0.0}
                pattern_stats[p]['trades'] += 1
                if t.profit_loss and t.profit_loss > 0:
                    pattern_stats[p]['wins'] += 1
                pattern_stats[p]['total_pnl'] += t.profit_loss or 0
                pattern_stats[p]['total_charges'] += t.brokerage_charges or 0

            for p in pattern_stats:
                s = pattern_stats[p]
                s['win_rate'] = round(
                    (s['wins'] / s['trades'] * 100), 1) if s['trades'] else 0
                s['total_pnl'] = round(s['total_pnl'], 2)
                s['total_charges'] = round(s['total_charges'], 2)

            # Last 10 closed trades with charges breakdown
            recent = []
            for t in closed[:10]:
                recent.append({
                    'id': t.id,
                    'symbol': t.symbol,
                    'pattern': t.pattern,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'quantity': t.quantity,
                    'gross_pnl': t.gross_profit_loss,
                    'charges': t.brokerage_charges,
                    'net_pnl': t.profit_loss,
                    'pnl_pct': round(t.profit_loss_pct, 2) if t.profit_loss_pct else None,
                    'hold_days': t.hold_duration_days,
                    'exit_reason': t.exit_reason,
                    'entry_score': t.entry_score
                })

            portfolio = db.query(Portfolio).order_by(
                Portfolio.timestamp.desc()).first()

            return jsonify({
                'summary': {
                    'total_trades': len(all_trades),
                    'open_trades': len(open_trades),
                    'closed_trades': len(closed),
                    'wins': len(wins),
                    'losses': len(losses),
                    'win_rate': round(win_rate, 1),
                    'total_gross_pnl': round(total_gross_pnl, 2),
                    'total_charges_paid': round(total_charges, 2),
                    'total_net_pnl': round(total_net_pnl, 2),
                    'avg_win': round(avg_win, 2),
                    'avg_loss': round(avg_loss, 2),
                    'avg_hold_days': round(avg_hold, 1),
                    'current_capital': portfolio.total_capital if portfolio else None
                },
                'by_pattern': pattern_stats,
                'recent_closed': recent,
                'open_positions': [{
                    'symbol': t.symbol,
                    'entry_price': t.entry_price,
                    'quantity': t.quantity,
                    'stop_loss': t.stop_loss,
                    'target': t.target,
                    'entry_score': t.entry_score,
                    'entry_date': t.entry_date.isoformat() if t.entry_date else None
                } for t in open_trades]
            })
    except Exception as e:
        logger.error(f"Error in trades summary: {e}")
        return jsonify({'error': str(e)}), 500


# ===== ADMIN ENDPOINTS (all require X-API-KEY header) =====

@app.route('/api/admin/top-up-capital', methods=['POST'])
@require_api_key
def admin_top_up_capital():
    """
    Add capital to the existing portfolio WITHOUT resetting trade history.
    """
    try:
        body = request.get_json(silent=True) or {}
        amount = float(body.get('amount', 0))

        if amount <= 0:
            return jsonify({
                'status': 'rejected',
                'message': 'amount must be a positive number.'
            }), 400

        with get_session() as db:
            portfolio = db.query(Portfolio).order_by(
                Portfolio.timestamp.desc()).first()

            if not portfolio:
                return jsonify({'status': 'error', 'message': 'Portfolio not found'}), 404

            prev_total = portfolio.total_capital
            prev_available = portfolio.available_capital

            # Create new portfolio snapshot with topped-up capital
            new_portfolio = Portfolio(
                total_capital=portfolio.total_capital + amount,
                deployed_capital=portfolio.deployed_capital,
                available_capital=portfolio.available_capital + amount,
                unrealized_pnl=portfolio.unrealized_pnl,
                realized_pnl=portfolio.realized_pnl,
                open_positions=portfolio.open_positions,
                timestamp=datetime.now(IST)
            )
            db.add(new_portfolio)
            db.commit()

            logger.info(
                f"[ADMIN] top-up-capital: ₹{amount} added. "
                f"Total: ₹{prev_total} → ₹{new_portfolio.total_capital}"
            )

            return jsonify({
                'status': 'success',
                'message': f'Portfolio topped up by ₹{amount:.0f}. Trade history preserved.',
                'previous_capital': round(prev_total, 2),
                'added': amount,
                'new_total_capital': round(new_portfolio.total_capital, 2),
                'previous_available': round(prev_available, 2),
                'new_available_capital': round(new_portfolio.available_capital, 2),
                'timestamp': datetime.now(IST).isoformat()
            })

    except Exception as e:
        logger.error(f"[ADMIN] top-up-capital error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/flush-history', methods=['DELETE'])
@require_api_key
def admin_flush_history():
    """
    Wipe scan history, pattern occurrences, and learning metrics.
    """
    try:
        with get_session() as db:
            from models.scan_report import ScanReport, ScanResult, PatternOccurrence
            from models.database import LearningMetrics

            po_count = db.query(PatternOccurrence).delete()
            sr_count = db.query(ScanResult).delete()
            rep_count = db.query(ScanReport).delete()
            lm_count = db.query(LearningMetrics).delete()
            db.commit()

            logger.warning(
                f"[ADMIN] flush-history executed: "
                f"pattern_occurrences={po_count}, scan_results={sr_count}, "
                f"scan_reports={rep_count}, learning_metrics={lm_count}"
            )

            return jsonify({
                'status': 'success',
                'message': 'Scan history and learning metrics cleared. Trades and portfolio untouched.',
                'deleted': {
                    'pattern_occurrences': po_count,
                    'scan_results': sr_count,
                    'scan_reports': rep_count,
                    'learning_metrics': lm_count,
                },
                'timestamp': datetime.now(IST).isoformat()
            })

    except Exception as e:
        logger.error(f"[ADMIN] flush-history error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/flush-trades', methods=['DELETE'])
@require_api_key
def admin_flush_trades():
    """
    Wipe all trade records (OPEN and CLOSED) and reset the portfolio snapshot.
    """
    try:
        body = request.get_json(silent=True) or {}
        if body.get('confirm') != 'FLUSH_TRADES':
            return jsonify({
                'status': 'rejected',
                'message': 'Safety check failed. Send JSON body: {"confirm": "FLUSH_TRADES"} to proceed.'
            }), 400

        with get_session() as db:
            # Delete all trades — both OPEN and CLOSED
            tr_count = db.query(Trade).delete()

            # Reset portfolio to INITIAL_CAPITAL (wipe deployed/unrealized state)
            port_count = db.query(Portfolio).delete()
            db.commit()

            initial_capital = float(os.getenv('INITIAL_CAPITAL', 5000))
            db.add(Portfolio(
                total_capital=initial_capital,
                deployed_capital=0,
                available_capital=initial_capital,
                unrealized_pnl=0,
                realized_pnl=0,
                open_positions=0,
                timestamp=datetime.now(IST).replace(tzinfo=None)
            ))
            db.commit()

            logger.warning(
                f"[ADMIN] flush-trades executed: {tr_count} trade(s) deleted. "
                f"Portfolio reset to ₹{initial_capital}. ML model preserved."
            )

            return jsonify({
                'status': 'success',
                'message': (
                    f'All trades cleared. Portfolio reset to ₹{initial_capital}. '
                    'ML model, scan history and learning metrics are untouched.'
                ),
                'deleted': {
                    'trades': tr_count,
                    'portfolio_snapshots': port_count,
                },
                'preserved': ['ml_models', 'learning_metrics', 'scan_reports',
                              'scan_results', 'pattern_occurrences'],
                'timestamp': datetime.now(IST).isoformat()
            })

    except Exception as e:
        logger.error(f"[ADMIN] flush-trades error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/flush-all', methods=['DELETE'])
@require_api_key
def admin_flush_all():
    """
    Nuclear option: wipe ALL data — trades, scans, patterns, learning, portfolio.
    """
    try:
        body = request.get_json(silent=True) or {}
        if body.get('confirm') != 'RESET':
            return jsonify({
                'status': 'rejected',
                'message': 'Safety check failed. Send JSON body: {"confirm": "RESET"} to proceed.'
            }), 400

        with get_session() as db:
            from models.scan_report import ScanReport, ScanResult, PatternOccurrence
            from models.database import LearningMetrics, MLModel, Trade, Portfolio

            po_count = db.query(PatternOccurrence).delete()
            sr_count = db.query(ScanResult).delete()
            rep_count = db.query(ScanReport).delete()
            lm_count = db.query(LearningMetrics).delete()
            ml_count = db.query(MLModel).delete()
            tr_count = db.query(Trade).delete()
            port_count = db.query(Portfolio).delete()
            db.commit()

            # Re-initialise portfolio with current INITIAL_CAPITAL
            initial_capital = float(os.getenv('INITIAL_CAPITAL', 5000))
            db.add(Portfolio(
                total_capital=initial_capital,
                deployed_capital=0,
                available_capital=initial_capital,
                unrealized_pnl=0,
                realized_pnl=0,
                open_positions=0,
                timestamp=datetime.now(IST).replace(tzinfo=None)
            ))
            db.commit()

            logger.warning(
                f"[ADMIN] flush-all executed: full system reset. "
                f"Capital reinitialised to ₹{initial_capital}"
            )

            return jsonify({
                'status': 'success',
                'message': f'Full system reset complete. Portfolio reinitialised with ₹{initial_capital}.',
                'deleted': {
                    'pattern_occurrences': po_count,
                    'scan_results': sr_count,
                    'scan_reports': rep_count,
                    'learning_metrics': lm_count,
                    'ml_models': ml_count,
                    'trades': tr_count,
                    'portfolio_snapshots': port_count,
                },
                'timestamp': datetime.now(IST).isoformat()
            })

    except Exception as e:
        logger.error(f"[ADMIN] flush-all error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/system-status', methods=['GET'])
@require_api_key
def admin_system_status():
    """
    Deep diagnostic snapshot of the system.
    """
    try:
        with get_session() as db:
            from models.scan_report import ScanReport, ScanResult, PatternOccurrence
            from models.database import LearningMetrics, MLModel, Trade, Portfolio

            # DB row counts
            db_counts = {
                'trades_open': db.query(Trade).filter_by(status='OPEN').count(),
                'trades_closed': db.query(Trade).filter_by(status='CLOSED').count(),
                'scan_reports': db.query(ScanReport).count(),
                'scan_results': db.query(ScanResult).count(),
                'pattern_occurrences': db.query(PatternOccurrence).count(),
                'learning_metrics': db.query(LearningMetrics).count(),
                'ml_models_active': db.query(MLModel).filter_by(is_active=True).count(),
            }

            # ML Cold Start Status
            ml_model_active = db.query(MLModel).filter_by(
                model_name='pattern_classifier',
                is_active=True
            ).first() is not None
            trades_needed_for_ml = max(0, 20 - db_counts['trades_closed'])
            cold_start_active = not ml_model_active and trades_needed_for_ml > 0

            # Portfolio state
            portfolio = db.query(Portfolio).order_by(
                Portfolio.timestamp.desc()).first()
            portfolio_state = {
                'total_capital': portfolio.total_capital if portfolio else None,
                'available_capital': portfolio.available_capital if portfolio else None,
                'deployed_capital': portfolio.deployed_capital if portfolio else None,
                'open_positions': portfolio.open_positions if portfolio else 0,
            } if portfolio else {}

            # Market context
            context_ok = True
            context_info = {}
            try:
                monitor = MarketMonitor(db)
                ctx = monitor.get_market_context()
                context_ok = not ctx.get('fetch_failed', False)
                context_info = {
                    'trend': ctx.get('trend'),
                    'strength': ctx.get('strength'),
                    'nifty_price': ctx.get('nifty_price'),
                    'fetch_failed': ctx.get('fetch_failed', False),
                }
            except Exception as ce:
                context_ok = False
                context_info = {'error': str(ce)}

            # Scheduler jobs
            jobs = []
            try:
                jobs = [
                    {'id': job.id, 'next_run': job.next_run_time.isoformat()
                     if job.next_run_time else None}
                    for job in scheduler.get_jobs()
                ]
            except:
                pass

            # Uptime
            uptime_seconds = (datetime.now(IST) - _APP_START_TIME).total_seconds()

            # Config summary
            config = {
                'min_confidence_score': int(os.getenv('MIN_CONFIDENCE_SCORE', 60)),
                'min_score_to_save': int(os.getenv('MIN_SCORE_TO_SAVE', 50)),
                'initial_capital': float(os.getenv('INITIAL_CAPITAL', 5000)),
                'risk_per_trade': float(os.getenv('RISK_PER_TRADE', 0.02)),
                'max_positions': int(os.getenv('MAX_POSITIONS', 5)),
                'watchlist_type': os.getenv('WATCHLIST_TYPE', 'custom'),
            }

            return jsonify({
                'status': 'healthy',
                'uptime_seconds': round(uptime_seconds),
                'timestamp': datetime.now(IST).isoformat(),
                'market_context_working': context_ok,
                'market_context': context_info,
                'consecutive_zero_trade_days': _get_consecutive_zero_trade_days(),
                'scheduler': {
                    'running': scheduler.running if scheduler else False,
                    'jobs': jobs,
                },
                'database_counts': db_counts,
                'portfolio': portfolio_state,
                'config': config,
                'ml_cold_start': {
                    'active': cold_start_active,
                    'ml_model_trained': ml_model_active,
                    'trades_completed': db_counts['trades_closed'],
                    'trades_needed_for_ml': trades_needed_for_ml,
                    'bonus_applied': '+10 score bonus' if cold_start_active else 'N/A',
                },
                'effective_thresholds': {
                    'min_confidence_score': int(os.getenv('MIN_CONFIDENCE_SCORE', 58)),
                    'bearish_market_formula': '70 + (strength * 2), capped at 80',
                    'weekly_ema': 'penalty (-10 pts) not binary block',
                }
            })

    except Exception as e:
        logger.error(f"[ADMIN] system-status error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/force-scan', methods=['POST'])
@require_api_key
def admin_force_scan():
    """
    Immediately trigger a market scan outside the scheduler.
    """
    scan_start_time = datetime.now(IST)
    try:
        logger.info("[ADMIN] force-scan triggered via API")

        with get_session() as db:
            # Initialize components
            from services.reporting_service import ReportingService

            monitor = MarketMonitor(db)
            risk_manager = RiskManager()
            brain = TradingBrain(db, risk_manager)
            portfolio_mgr = PortfolioManager(db, risk_manager, email_service)
            reporting_service = ReportingService(db)

            # 1. Get market context
            market_context = monitor.get_market_context()

            # 2. Get portfolio state
            portfolio_state = portfolio_mgr.get_portfolio_state()

            # 3. Scan market
            opportunities = monitor.scan_market()

            # 4. Create scan report
            scan_duration = (datetime.now(IST) - scan_start_time).total_seconds()
            scan_stats = {
                'total_scanned': len(monitor.watchlist),
                'opportunities_found': len(opportunities),
                'trades_entered': 0
            }

            scan_report = reporting_service.save_scan_report(
                market_context, scan_stats, scan_duration
            )
            scan_report_id = scan_report.id if scan_report else None

            passed_stocks = []

            # 5. Evaluate each opportunity
            for opp in opportunities:
                try:
                    evaluation = brain.evaluate_opportunity(
                        opp, market_context, portfolio_state)

                    # Save patterns for learning
                    if scan_report_id and opp.get('patterns'):
                        reporting_service._save_pattern_occurrences(
                            opp, evaluation, scan_report_id
                        )

                    # Save scan result (filtered by MIN_SCORE_TO_SAVE)
                    if scan_report_id:
                        reporting_service.save_scan_result(
                            scan_report_id, opp, evaluation
                        )

                    if evaluation['decision'] == 'ENTER':
                        passed_stocks.append({
                            'symbol': evaluation['symbol'],
                            'score': evaluation['score'],
                            'reason': evaluation['reason']
                        })

                except Exception as e:
                    logger.error(f"Error evaluating {opp.get('symbol')}: {e}")
                    continue

            return jsonify({
                'status': 'success',
                'message': 'Force scan complete.',
                'scan_duration_secs': round(scan_duration, 1),
                'stocks_with_patterns': len(opportunities),
                'opportunities_passed': len(passed_stocks),
                'market_context': market_context,
                'top_opportunities': passed_stocks[:10],
                'timestamp': datetime.now(IST).isoformat()
            })

    except Exception as e:
        logger.error(f"[ADMIN] force-scan error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/admin/reload-model', methods=['POST'])
@require_api_key
def admin_reload_model():
    try:
        with get_session() as db:
            brain = _get_brain(db)
            brain.reload_ml_model()
        logger.info("ML model reloaded successfully")
        return jsonify({'status': 'success', 'message': 'ML model reloaded.'})
    except Exception as e:
        logger.error(f"Error reloading ML model: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
