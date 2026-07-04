"""Fixture-based tests for the KR pykrx market-data adapter (no network)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from detector_fin.fetcher.base import to_source_code
from detector_fin.fetcher.market_data import PykrxAdapter
from detector_fin.market_config import load_market_config
from detector_fin.schemas import MarketBar
from detector_fin.universe import Instrument

from ._marketdata import load_pykrx

MARKET = load_market_config("KR")
OBSERVED = datetime(2026, 6, 7, 23, 0, tzinfo=timezone.utc)

SAMSUNG = Instrument(
    ticker="005930.KS",
    name_en="Samsung Electronics",
    market_id="KR",
    instrument_type="equity",
)
KODEX200 = Instrument(
    ticker="069500.KS", name_en="KODEX 200", market_id="KR", instrument_type="etf"
)


def test_suffix_stripped_for_source_code():
    assert to_source_code("005930.KS", MARKET) == "005930"
    assert to_source_code("069500.KS", MARKET) == "069500"


def test_transform_maps_korean_columns():
    bars = PykrxAdapter()._transform(
        SAMSUNG, load_pykrx("pykrx_stock_005930.csv"), MARKET, OBSERVED
    )
    assert all(isinstance(b, MarketBar) for b in bars)
    first = next(b for b in bars if b.date_local == date(2026, 6, 1))
    assert first.ticker == "005930.KS"
    assert first.instrument_type == "equity"
    assert first.currency == "KRW"
    assert first.source == "pykrx"
    # 시가/고가/저가/종가 -> open/high/low/close
    assert (first.open, first.high, first.low, first.close) == (
        80000.0,
        81000.0,
        79500.0,
        80500.0,
    )
    assert first.volume == 10000000.0


def test_observed_at_utc_preserved():
    bars = PykrxAdapter()._transform(
        SAMSUNG, load_pykrx("pykrx_stock_005930.csv"), MARKET, OBSERVED
    )
    assert bars
    assert all(
        b.observed_at == OBSERVED and b.observed_at.tzinfo == timezone.utc for b in bars
    )


def test_fetch_bars_filters_non_sessions(monkeypatch):
    adapter = PykrxAdapter()
    monkeypatch.setattr(
        adapter,
        "_fetch_raw",
        lambda inst, market, since: load_pykrx("pykrx_stock_005930.csv"),
    )
    bars = adapter.fetch_bars(MARKET, [SAMSUNG], date(2026, 6, 1), observed_at=OBSERVED)
    dates = {b.date_local for b in bars}
    assert date(2026, 6, 6) not in dates
    assert dates == {date(2026, 6, d) for d in (1, 2, 3, 4, 5)}


def test_etf_frame_and_type(monkeypatch):
    adapter = PykrxAdapter()
    monkeypatch.setattr(
        adapter,
        "_fetch_raw",
        lambda inst, market, since: load_pykrx("pykrx_etf_069500.csv"),
    )
    bars = adapter.fetch_bars(
        MARKET, [KODEX200], date(2026, 6, 1), observed_at=OBSERVED
    )
    assert bars
    assert all(b.instrument_type == "etf" and b.ticker == "069500.KS" for b in bars)
    assert date(2026, 6, 6) not in {b.date_local for b in bars}
