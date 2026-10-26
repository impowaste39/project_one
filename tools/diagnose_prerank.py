"""Run on your own machine while the market is open (read-only, no DB, no credentials).

Reproduces the pre-rank download for the first 10 watchlist symbols and prints, per symbol,
how many rows come back, how many survive dropna(), and whether the latest row has NaNs.
Usage:  python tools/diagnose_prerank.py
Best run inside a venv with the repo's pinned requirements (pip install -r requirements.txt).
"""
import sys

import pandas as pd
import yfinance as yf

sys.path.insert(0, '.')
try:
    from services.data_service import DataService
    chunk = DataService().get_watchlist('custom')[:10]
except Exception as exc:  # fall back so the script still runs standalone
    print('could not load watchlist from repo:', exc)
    chunk = ['PNB.NS', 'UNIONBANK.NS', 'SWIGGY.NS', 'INDIACEM.NS', 'KARURVYSYA.NS',
             'SBIN.NS', 'ONGC.NS', 'IOC.NS', 'BEL.NS', 'TATASTEEL.NS']

print('yfinance', yf.__version__, '| pandas', pd.__version__)
data = yf.download(chunk, period='1mo', interval='1d', progress=False,
                   group_by='ticker', auto_adjust=True)
print('shape', data.shape, '| column levels', data.columns.nlevels)
print('last 3 index values:', [str(i) for i in data.index[-3:]])
for symbol in chunk:
    try:
        sub = data[symbol][['High', 'Close', 'Volume']]
        print(f'{symbol:15s} raw_rows={len(sub):3d} after_dropna={len(sub.dropna()):3d} '
              f'last_row_NaN={sub.iloc[-1].isna().to_dict()}')
    except Exception as exc:
        print(f'{symbol:15s} ERROR {type(exc).__name__}: {exc}')
print('\nRule in the bot: a symbol is skipped when after_dropna < 20.')