import logging

import numpy as np
import pandas as pd
import pytest

from core import market_monitor as mm


def frame(symbols, rows):
    idx = pd.date_range('2026-09-01', periods=rows, freq='B')
    cols = pd.MultiIndex.from_product([symbols, ['High', 'Close', 'Volume']])
    data = pd.DataFrame(np.nan, index=idx, columns=cols)
    for s in symbols:
        data[(s, 'High')] = np.linspace(100, 110, rows)
        data[(s, 'Close')] = np.linspace(99, 108, rows)
        data[(s, 'Volume')] = 1000.0
    return data


class StubData:
    def fetch_nifty_return(self, lookback):
        return -2.0


def monitor(symbols):
    m = object.__new__(mm.MarketMonitor)
    m.watchlist = symbols
    m.data_service = StubData()
    return m


def test_summary_logged_and_ranking_unchanged(monkeypatch, caplog):
    syms = ['A.NS', 'B.NS', 'C.NS']
    monkeypatch.setattr(mm.yf, 'download', lambda chunk, **kw: frame(chunk, 25))
    with caplog.at_level(logging.INFO, logger='core.market_monitor'):
        top = monitor(syms).pre_rank_watchlist(limit=30)
    assert sorted(top) == sorted(syms)
    assert any('eligible=3/3' in r.message for r in caplog.records)
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)


def test_too_few_rows_is_reported_loudly(monkeypatch, caplog):
    syms = ['A.NS', 'B.NS']
    monkeypatch.setattr(mm.yf, 'download', lambda chunk, **kw: frame(chunk, 18))
    with caplog.at_level(logging.INFO, logger='core.market_monitor'):
        top = monitor(syms).pre_rank_watchlist(limit=30)
    assert top == []
    warn = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warn and 'NO symbol could be ranked' in warn[0].message
    assert "('A.NS', 18)" in warn[0].message


def test_per_symbol_errors_are_reported(monkeypatch, caplog):
    syms = ['A.NS', 'B.NS']
    # download returns columns for other tickers, so data[symbol] raises KeyError
    monkeypatch.setattr(mm.yf, 'download', lambda chunk, **kw: frame(['Z.NS', 'Y.NS'], 25))
    with caplog.at_level(logging.INFO, logger='core.market_monitor'):
        top = monitor(syms).pre_rank_watchlist(limit=30)
    assert top == []
    warn = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warn and 'KeyError' in warn[0].message