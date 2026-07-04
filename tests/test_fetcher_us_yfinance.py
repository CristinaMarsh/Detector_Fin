"""Fixture-based tests for the US yfinance market-data adapter (no network)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from detector_fin.fetcher.base import to_source_code
from detector_fin.fetcher.market_data import YFinanceAdapter
from detector_fin.market_config import load_market_config
from detector_fin.schemas import MarketBar
from detector_fin.universe import Instrument

from ._marketdata import load_yfinance

MARKET = load_market_config("US")
OBSERVED = datetime(2026, 6, 8, 12, 30, tzinfo=timezone.utc)

NVDA = Instrument(
    ticker="NVDA", name_en="NVIDIA", market_id="US", instrument_type="equity"
)
SPY = Instrument(
    ticker="SPY", name_en="SPDR S&P 500 ETF", market_id="US", instrument_type="etf"
)


def test_us_symbols_have_no_suffix_mapping():
    # US tickers are bare; source code equals the ticker.
    assert to_source_code("NVDA", MARKET) == "NVDA"
    assert to_source_code("SPY", MARKET) == "SPY"


def test_transform_maps_columns_and_fields():
    bars = YFinanceAdapter()._transform(
        NVDA, load_yfinance("yfinance_NVDA.csv"), MARKET, OBSERVED
    )
    assert all(isinstance(b, MarketBar) for b in bars)
    first = next(b for b in bars if b.date_local == date(2026, 6, 1))
    assert first.ticker == "NVDA"
    assert first.market_id == "US"
    assert first.instrument_type == "equity"
    assert first.currency == "USD"
    assert first.source == "yfinance"
    assert (first.open, first.high, first.low, first.close) == (
        100.0,
        102.5,
        99.5,
        101.0,
    )
    assert first.volume == 10000000.0


def test_observed_at_is_utc_and_preserved():
    bars = YFinanceAdapter()._transform(
        NVDA, load_yfinance("yfinance_NVDA.csv"), MARKET, OBSERVED
    )
    assert bars, "expected bars"
    for b in bars:
        assert b.observed_at == OBSERVED
        assert b.observed_at.tzinfo == timezone.utc


def test_fetch_bars_filters_non_sessions(monkeypatch):
    adapter = YFinanceAdapter()
    monkeypatch.setattr(
        adapter,
        "_fetch_raw",
        lambda inst, market, since: load_yfinance("yfinance_NVDA.csv"),
    )
    bars = adapter.fetch_bars(MARKET, [NVDA], date(2026, 6, 1), observed_at=OBSERVED)
    dates = {b.date_local for b in bars}
    # Saturday 2026-06-06 is not an XNYS session and must be dropped.
    assert date(2026, 6, 6) not in dates
    assert dates == {date(2026, 6, d) for d in (1, 2, 3, 4, 5)}


def test_etf_instrument_type_propagates(monkeypatch):
    adapter = YFinanceAdapter()
    monkeypatch.setattr(
        adapter,
        "_fetch_raw",
        lambda inst, market, since: load_yfinance("yfinance_SPY.csv"),
    )
    bars = adapter.fetch_bars(MARKET, [SPY], date(2026, 6, 1), observed_at=OBSERVED)
    assert bars
    assert all(b.instrument_type == "etf" for b in bars)
    assert all(b.ticker == "SPY" for b in bars)
    assert date(2026, 6, 6) not in {b.date_local for b in bars}


def test_empty_frame_yields_no_bars():
    import pandas as pd

    assert YFinanceAdapter()._transform(NVDA, pd.DataFrame(), MARKET, OBSERVED) == []
