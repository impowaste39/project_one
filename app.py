"""
AI Trading Bot - Main Flask Application
Autonomous swing trading bot for Indian stock market
"""

from flask import Flask, render_template, jsonify, request, abort
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from functools import wraps
import os
import logging
import atexit
import pytz

# Import core modules
from models.database import init_database, get_session, Portfolio, Trade
from core.market_monitor import MarketMonitor
from core.trading_brain import TradingBrain
from core.portfolio_manager import PortfolioManager
from core.risk_manager import RiskManager
from core.learning_engine import LearningEngine
from services.email_service import EmailService
from services.data_service import DataService
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

# Timezone
IST = pytz.timezone('Asia/Kolkata')

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
scheduler = BackgroundScheduler(timezone=IST)


def initialize_portfolio():
    """Initialize portfolio with starting capital if not exists"""
    db = get_session()
    try:
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

    except Exception as e:
        logger.error(f"Error initializing portfolio: {e}")
        db.rollback()
    finally:
        db.close()


# ===== SCHEDULED JOBS =====

def scan_market_job():
    """Market scanning job - runs every 5 minutes during market hours"""
    if not is_market_hours():
        logger.debug("Market closed - skipping scan")
        return

    db = get_session()

    try:
        logger.info("=" * 50)
        logger.info("MARKET SCAN STARTED")
        logger.info("=" * 50)

        # Initialize components
        monitor = MarketMonitor(db)
        risk_manager = RiskManager()
        brain = TradingBrain(db, risk_manager)
        portfolio_mgr = PortfolioManager(db, risk_manager, email_service)

        # Get market context
        market_context = monitor.get_market_context()
        logger.info(
            f"Market Context: {market_context.get('trend', 'unknown')} trend")

        # Get portfolio state
        portfolio_state = portfolio_mgr.get_portfolio_state()

        # Scan market for opportunities
        opportunities = monitor.scan_market()

        if not opportunities:
            logger.info("No trading opportunities found")
            return

        logger.info(f"Found {len(opportunities)} potential opportunities")

        # Evaluate each opportunity
        for opp in opportunities:
            try:
                evaluation = brain.evaluate_opportunity(
                    opp, market_context, portfolio_state)

                if evaluation['decision'] == 'ENTER':
                    success = portfolio_mgr.enter_trade(evaluation)

                    if success:
                        logger.info(
                            f"✅ TRADE EXECUTED: {evaluation['symbol']} @ ₹{evaluation['entry_price']}")
                        portfolio_state = portfolio_mgr.get_portfolio_state()
                else:
                    logger.info(
                        f"⏭️  PASSED: {opp['symbol']} - {evaluation['reason']}")

            except Exception as e:
                logger.error(f"Error evaluating {opp['symbol']}: {e}")
                continue

        logger.info("Market scan completed")

    except Exception as e:
        logger.error(f"Error in market scan job: {e}")

    finally:
        db.close()


def monitor_positions_job():
    """Position monitoring job - runs every 2 minutes during market hours"""
    if not is_market_hours():
        return

    db = get_session()

    try:
        logger.info("Monitoring open positions...")

        # Initialize components
        monitor = MarketMonitor(db)
        brain = TradingBrain(db, None)
        portfolio_mgr = PortfolioManager(db, None, email_service)
        learning_engine = LearningEngine(db)

        # Get open positions
        open_trades = db.query(Trade).filter(Trade.status == 'OPEN').all()

        if not open_trades:
            logger.debug("No open positions to monitor")
            return

        logger.info(f"Monitoring {len(open_trades)} open positions")

        for trade in open_trades:
            try:
                # Fetch current price
                data = monitor.fetch_stock_data(trade.symbol, period='5d')

                if data is None or data.empty:
                    logger.warning(f"Could not fetch data for {trade.symbol}")
                    continue

                current_price = data['Close'].iloc[-1]

                # Check exit conditions
                exit_decision = brain.check_exit_conditions(
                    trade, current_price, data)

                if exit_decision['action'] == 'EXIT':
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

                        # Send exit email
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

        logger.info("Position monitoring completed")

    except Exception as e:
        logger.error(f"Error in position monitoring job: {e}")

    finally:
        db.close()


def end_of_day_analysis_job():
    """End of day analysis and learning - runs at 4:00 PM IST"""
    db = get_session()

    try:
        logger.info("=" * 50)
        logger.info("END OF DAY ANALYSIS")
        logger.info("=" * 50)

        learning_engine = LearningEngine(db)
        brain = TradingBrain(db, None)

        # Generate performance report
        performance = learning_engine.generate_performance_report()

        logger.info(f"Performance Summary:")
        logger.info(f"  Total Trades: {performance.get('total_trades', 0)}")
        logger.info(f"  Win Rate: {performance.get('win_rate', 0):.2f}%")
        logger.info(f"  Total P&L: ₹{performance.get('total_pnl', 0):.2f}")

        # Retrain ML model if enough data
        if performance.get('total_trades', 0) >= 50:
            logger.info("Retraining ML model...")
            learning_engine.retrain_ml_model(brain)

        # Send daily summary email
        summary_data = {
            'date': datetime.now(IST).strftime('%d %b %Y'),
            'performance': performance
        }

        email_service.send_daily_summary(summary_data)

        logger.info("End of day analysis completed")

    except Exception as e:
        logger.error(f"Error in EOD analysis: {e}")

    finally:
        db.close()


# Schedule jobs
scheduler.add_job(
    scan_market_job,
    'cron',
    day_of_week='mon-fri',
    hour='9-15',
    minute='*/15',
    id='market_scan'
)

scheduler.add_job(
    monitor_positions_job,
    'cron',
    day_of_week='mon-fri',
    hour='9-15',
    minute='*/2',
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

# Start scheduler
scheduler.start()
logger.info("Scheduler started successfully")

# Shutdown scheduler on app exit
atexit.register(lambda: scheduler.shutdown())

# Initialize portfolio on startup
initialize_portfolio()


# ===== FLASK ROUTES =====

@app.route('/')
def dashboard():
    """Main dashboard"""
    db = get_session()

    try:
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
            now=datetime.now(IST)
        )

    finally:
        db.close()


@app.route('/api/portfolio')
@require_api_key
def api_portfolio():
    """Portfolio API endpoint"""
    db = get_session()

    try:
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

    finally:
        db.close()


@app.route('/api/trades')
@require_api_key
def api_trades():
    """Trades API endpoint"""
    db = get_session()

    try:
        trades = db.query(Trade).order_by(
            Trade.entry_date.desc()).limit(100).all()
        return jsonify([trade.to_dict() for trade in trades])

    finally:
        db.close()


@app.route('/api/open-positions')
@require_api_key
def api_open_positions():
    """Open positions API endpoint"""
    db = get_session()

    try:
        open_trades = db.query(Trade).filter(Trade.status == 'OPEN').all()
        return jsonify([trade.to_dict() for trade in open_trades])

    finally:
        db.close()


@app.route('/health')
def health():
    """Health check endpoint for UptimeRobot"""
    db_status = "unknown"
    db = get_session()
    try:
        # Try a simple query to verify connection
        db.query(Portfolio).first()
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = f"error: {str(e)}"
    finally:
        db.close()

    return jsonify({
        'status': 'healthy' if db_status == "connected" else "unhealthy",
        'database': db_status,
        'timestamp': datetime.now(IST).isoformat(),
        'scheduler_running': scheduler.running,
        'market_status': get_market_status_message()
    }), 200 if db_status == "connected" else 500


@app.route('/api/performance')
@require_api_key
def api_performance():
    """Performance metrics API"""
    db = get_session()

    try:
        learning_engine = LearningEngine(db)
        performance = learning_engine.generate_performance_report()

        return jsonify(performance)

    finally:
        db.close()


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


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
