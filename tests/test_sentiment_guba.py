"""Fixture-based tests for the East Money guba sentiment adapter (no network)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from detector_fin.fetcher.item_adapters import hash_author
from detector_fin.fetcher.sentiment import EastmoneyGubaAdapter
from detector_fin.market_config import load_market_config
from detector_fin.universe import Instrument

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sentiment"
MARKET = load_market_config("CN")
OBSERVED = datetime(2026, 6, 17, 1, 0, tzinfo=timezone.utc)
SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)

MOUTAI = Instrument(
    ticker="600519.SS",
    name_en="Kweichow Moutai",
    market_id="CN",
    instrument_type="equity",
)


def _payload() -> dict:
    return json.loads((FIXTURES / "guba_600519.json").read_text())


def test_transform_maps_posts():
    items = EastmoneyGubaAdapter()._transform(MOUTAI, _payload(), MARKET, OBSERVED)
    assert len(items) == 2  # malformed row skipped
    first = items[0]
    assert first.id == "eastmoney_guba:1456789001"
    assert first.lang == "zh"
    assert first.text == "茅台一季度业绩超预期，白酒板块要启动了吗"
    assert first.url == "https://guba.eastmoney.com/news,600519,1456789001.html"
    assert first.author_hash == hash_author("价值老兵")


def test_beijing_time_normalised_to_utc():
    items = EastmoneyGubaAdapter()._transform(MOUTAI, _payload(), MARKET, OBSERVED)
    # 2026-06-16 10:30:00 Asia/Shanghai (+8) == 02:30:00 UTC.
    assert items[0].event_time == datetime(2026, 6, 16, 2, 30, tzinfo=timezone.utc)


def test_fetch_items_since_filter_and_degradation(monkeypatch):
    adapter = EastmoneyGubaAdapter()
    adapter.request_delay_seconds = 0  # stubbed fetch: no politeness delay needed
    monkeypatch.setattr(adapter, "_fetch_raw", lambda inst, market, since: _payload())
    items = adapter.fetch_items(MARKET, [MOUTAI], SINCE, observed_at=OBSERVED)
    assert len(items) == 2
    assert all(i.event_time >= SINCE for i in items)

    def boom(inst, market, since):
        raise TimeoutError("upstream slow")

    monkeypatch.setattr(adapter, "_fetch_raw", boom)
    assert adapter.fetch_items(MARKET, [MOUTAI], SINCE, observed_at=OBSERVED) == []


def test_raw_nickname_absent_from_stored_record():
    items = EastmoneyGubaAdapter()._transform(MOUTAI, _payload(), MARKET, OBSERVED)
    assert "价值老兵" not in items[0].model_dump_json()
