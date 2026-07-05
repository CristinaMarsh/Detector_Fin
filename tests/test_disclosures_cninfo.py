"""Fixture-based tests for the cninfo disclosure adapter (no network)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from detector_fin.fetcher.disclosures import CninfoAdapter
from detector_fin.fetcher.disclosures.cn_cninfo import _column_for
from detector_fin.market_config import load_market_config
from detector_fin.universe import Instrument

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "disclosures"
MARKET = load_market_config("CN")
OBSERVED = datetime(2026, 6, 20, 1, 0, tzinfo=timezone.utc)

MOUTAI = Instrument(
    ticker="600519.SS",
    name_en="Kweichow Moutai",
    market_id="CN",
    instrument_type="equity",
)


def _payload() -> dict:
    return json.loads((FIXTURES / "cninfo_600519.json").read_text())


def test_exchange_column_from_suffix():
    assert _column_for("600519.SS") == "sse"
    assert _column_for("300750.SZ") == "szse"


def test_transform_maps_announcements():
    items = CninfoAdapter()._transform(MOUTAI, _payload(), MARKET, OBSERVED)
    assert len(items) == 2  # malformed third row skipped, never repaired
    first = items[0]
    assert first.id == "cninfo:1220345678"
    assert first.source == "cninfo"
    assert first.lang == "zh"
    assert first.text == "贵州茅台2026年第一季度报告"
    assert first.ticker_hints == ["600519.SS"]


def test_document_url_is_official_static_host():
    items = CninfoAdapter()._transform(MOUTAI, _payload(), MARKET, OBSERVED)
    assert items[0].url == (
        "https://static.cninfo.com.cn/finalpage/2026-06-16/1220345678.PDF"
    )
    assert all(i.url.startswith("https://static.cninfo.com.cn/") for i in items)


def test_event_time_from_epoch_millis():
    items = CninfoAdapter()._transform(MOUTAI, _payload(), MARKET, OBSERVED)
    # 1750032000000 ms == 2026-06-16T00:00:00Z
    assert items[0].event_time == datetime(2026, 6, 16, 0, 0, tzinfo=timezone.utc)
    assert items[0].observed_at == OBSERVED


def test_fetch_items_since_filter_and_degradation(monkeypatch):
    adapter = CninfoAdapter()
    monkeypatch.setattr(adapter, "_fetch_raw", lambda inst, market, since: _payload())
    since = datetime(2026, 6, 10, tzinfo=timezone.utc)
    items = adapter.fetch_items(MARKET, [MOUTAI], since, observed_at=OBSERVED)
    assert [i.id for i in items] == ["cninfo:1220345678"]  # June 2 row cut off

    def boom(inst, market, since):
        raise TimeoutError("slow upstream")

    monkeypatch.setattr(adapter, "_fetch_raw", boom)
    assert adapter.fetch_items(MARKET, [MOUTAI], since, observed_at=OBSERVED) == []
