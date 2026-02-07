# 🤖 AI Swing Trading Bot

An autonomous, self-improving swing trading bot for the Indian stock market (NSE/BSE), optimized for Render.com's free tier.

## Features

- 📈 **Autonomous Trading**: Scans Nifty 50 stocks every 5 minutes during market hours
- 🧠 **AI-Powered Decisions**: ML-based pattern recognition and scoring system
- 📊 **Pattern Detection**: Identifies bullish setups (MA crossovers, RSI bounces, breakouts)
- 💼 **Portfolio Management**: Automatic position sizing and risk management
- 📧 **Email Alerts**: Beautiful HTML notifications via Resend
- 🔄 **Self-Improvement**: Learns from every trade to optimize strategies
- 🎨 **Beautiful Dashboard**: Dark-themed, responsive web interface

## Tech Stack

- **Backend**: Python 3.11, Flask, APScheduler
- **Database**: PostgreSQL (Render free tier)
- **ML**: scikit-learn, pandas, numpy
- **Market Data**: yfinance
- **Email**: Resend (100 emails/day free)

## Quick Start

### 1. Local Development

```bash
# Clone the repository
cd ai-trading-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your settings

# Run the application
python app.py
```

### 2. Environment Variables

Create a `.env` file with:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/trading_bot
INITIAL_CAPITAL=5000
MAX_POSITIONS=5
RISK_PER_TRADE=0.02
MIN_CONFIDENCE_SCORE=70
NOTIFICATION_EMAIL=your_email@example.com
RESEND_API_KEY=re_your_api_key_here
```

### 3. Deploy to Render.com

1. **Sign up** at [render.com](https://render.com) (no credit card needed)

2. **Create PostgreSQL Database**:
   - Dashboard → New → PostgreSQL
   - Name: `trading-bot-db`
   - Plan: Free
   - Copy the Internal Database URL

3. **Create Web Service**:
   - Dashboard → New → Web Service
   - Connect your GitHub repository
   - Settings:
     - Name: `ai-trading-bot`
     - Region: Singapore
     - Build Command: `pip install -r requirements.txt`
     - Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120`

4. **Add Environment Variables** in Render dashboard

5. **Set up UptimeRobot** (keeps app awake):
   - Go to [uptimerobot.com](https://uptimerobot.com)
   - Add New Monitor → HTTP(s)
   - URL: `https://your-app.onrender.com/health`
   - Interval: 5 minutes

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard |
| `GET /health` | Health check |
| `GET /api/portfolio` | Portfolio state |
| `GET /api/trades` | Trade history |
| `GET /api/open-positions` | Open positions |
| `GET /api/performance` | Performance metrics |
| `POST /api/trigger-scan` | Manual market scan |

## Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| Market Scan | Every 5 min (9:15 AM - 3:30 PM) | Scans for trading opportunities |
| Position Monitor | Every 2 min (market hours) | Monitors open positions |
| EOD Analysis | 4:00 PM | Daily performance review |

## Project Structure

```
ai-trading-bot/
├── app.py                 # Main Flask application
├── requirements.txt       # Dependencies
├── render.yaml           # Render deployment config
├── core/
│   ├── market_monitor.py # Market scanning
│   ├── trading_brain.py  # AI decision engine
│   ├── portfolio_manager.py
│   ├── risk_manager.py
│   └── learning_engine.py
├── models/
│   └── database.py       # SQLAlchemy models
├── services/
│   ├── data_service.py   # yfinance integration
│   ├── email_service.py  # Resend emails
│   └── indicator_service.py
├── templates/
│   └── dashboard.html    # Web dashboard
└── utils/
    └── helpers.py        # Utility functions
```

## Trading Strategy

The bot uses a multi-factor scoring system (0-100):

- **Technical Indicators** (40 pts): RSI, MACD, Volume
- **Pattern Recognition** (30 pts): MA crossovers, breakouts, pullbacks
- **Market Context** (20 pts): Overall market trend
- **ML Prediction** (10 pts): Historical pattern success

Trades are entered when:
- Score ≥ 70
- Risk:Reward ≥ 1.5:1
- Open positions < 5
- Sufficient capital

## ⚠️ Important Notes

1. **Paper Trading Only**: This bot uses virtual money. Start with paper trading for 2-4 weeks.
2. **Database Backup**: Render's free PostgreSQL expires after 90 days. Export data monthly.
3. **Not Financial Advice**: This is for educational purposes only.

## License

MIT License
