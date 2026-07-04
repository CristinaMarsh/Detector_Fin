"""Fixture-based tests for the CN akshare market-data adapter (no network)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from detector_fin.fetcher.base import cn_code_to_ticker, to_source_code
from detector_fin.fetcher.market_data import AkshareAdapter
from detector_fin.market_config import load_market_config
from detector_fin.schemas import MarketBar
from detector_fin.universe import Instrument

from ._marketdata import load_akshare

MARKET = load_market_config("CN")
OBSERVED = datetime(2026, 6, 8, 0, 30, tzinfo=timezone.utc)

MOUTAI = Instrument(
    ticker="600519.SS",
    name_en="Kweichow Moutai",
    market_id="CN",
    instrument_type="equity",
)
CSI300_ETF = Instrument(
    ticker="510300.SS", name_en="CSI 300 ETF", market_id="CN", instrument_type="etf"
)


def test_suffix_stripped_for_source_code():
    assert to_source_code("600519.SS", MARKET) == "600519"
    assert to_source_code("300750.SZ", MARKET) == "300750"


def test_code_to_ticker_maps_exchange():
    # Shanghai: 5/6/9 leading; Shenzhen: everything else.
    assert cn_code_to_ticker("600519") == "600519.SS"
    assert cn_code_to_ticker("510300") == "510300.SS"
    assert cn_code_to_ticker("588000") == "588000.SS"
    assert cn_code_to_ticker("300750") == "300750.SZ"
    assert cn_code_to_ticker("159915") == "159915.SZ"


def test_transform_maps_chinese_columns():
    bars = AkshareAdapter()._transform(
        MOUTAI, load_akshare("akshare_stock_600519.csv"), MARKET, OBSERVED
    )
    assert all(isinstance(b, MarketBar) for b in bars)
    first = next(b for b in bars if b.date_local == date(2026, 6, 1))
    assert first.ticker == "600519.SS"
    assert first.instrument_type == "equity"
    assert first.currency == "CNY"
    assert first.source == "akshare"
    # 开盘/收盘/最高/最低 -> open/close/high/low
    assert (first.open, first.close, first.high, first.low) == (
        1700.0,
        1710.0,
        1720.0,
        1695.0,
    )
    assert first.volume == 30000.0


def test_fetch_bars_filters_non_sessions(monkeypatch):
    adapter = AkshareAdapter()
    monkeypatch.setattr(
        adapter,
        "_fetch_raw",
        lambda inst, market, since: load_akshare("akshare_stock_600519.csv"),
    )
    bars = adapter.fetch_bars(MARKET, [MOUTAI], date(2026, 6, 1), observed_at=OBSERVED)
    dates = {b.date_local for b in bars}
    assert date(2026, 6, 6) not in dates
    assert dates == {date(2026, 6, d) for d in (1, 2, 3, 4, 5)}
    assert all(b.observed_at == OBSERVED for b in bars)


def test_etf_uses_etf_frame_and_type(monkeypatch):
    adapter = AkshareAdapter()
    monkeypatch.setattr(
        adapter,
        "_fetch_raw",
        lambda inst, market, since: load_akshare("akshare_etf_510300.csv"),
    )
    bars = adapter.fetch_bars(
        MARKET, [CSI300_ETF], date(2026, 6, 1), observed_at=OBSERVED
    )
    assert bars
    assert all(b.instrument_type == "etf" for b in bars)
    assert all(b.ticker == "510300.SS" for b in bars)
    first = next(b for b in bars if b.date_local == date(2026, 6, 1))
    assert first.close == 3.920
