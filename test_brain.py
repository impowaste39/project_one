import sys
sys.path.append('.')
from core.trading_brain import TradingBrain
from core.market_monitor import MarketMonitor
from core.risk_manager import RiskManager

m = MarketMonitor()
rm = RiskManager()
brain = TradingBrain(risk_manager=rm)

ctx = m.get_market_context()
analysis = m.scan_stock('SBIN.NS')

portfolio_state = {
    'available_capital': 5000,
    'positions_count': 0
}

res = brain.evaluate_opportunity(analysis, ctx, portfolio_state)

for k, v in res.items():
    if k != 'factors':
        print(f"{k}: {v}")
print("\nFactors:")
for f in res['factors']:
    print(f"- {f}")
