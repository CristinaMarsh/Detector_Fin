"""Fixture-based tests for the StockTwits sentiment adapter (no network)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from detector_fin.fetcher.item_adapters import hash_author
from detector_fin.fetcher.sentiment import StocktwitsAdapter
from detector_fin.market_config import load_market_config
from detector_fin.universe import Instrument

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sentiment"
MARKET = load_market_config("US")
OBSERVED = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)
SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)

NVDA = Instrument(
    ticker="NVDA", name_en="NVIDIA", market_id="US", instrument_type="equity"
)


def _payload() -> dict:
    return json.loads((FIXTURES / "stocktwits_nvda.json").read_text())


def test_transform_maps_messages():
    items = StocktwitsAdapter()._transform(NVDA, _payload(), MARKET, OBSERVED)
    assert len(items) == 3  # malformed row skipped
    first = items[0]
    assert first.id == "stocktwits:612345001"
    assert first.source == "stocktwits"
    assert first.lang == "en"
    assert first.text.startswith("NVDA breaking out")
    assert first.url == "https://stocktwits.com/message/612345001"
    assert first.event_time == datetime(2026, 6, 16, 14, 5, 31, tzinfo=timezone.utc)


def test_usernames_are_hashed_never_stored_raw():
    items = StocktwitsAdapter()._transform(NVDA, _payload(), MARKET, OBSERVED)
    first = items[0]
    assert first.author_hash == hash_author("chiptrader88")
    dumped = first.model_dump_json()
    assert "chiptrader88" not in dumped


def test_fetch_items_since_filter_and_degradation(monkeypatch):
    adapter = StocktwitsAdapter()
    monkeypatch.setattr(adapter, "_fetch_raw", lambda inst, market, since: _payload())
    items = adapter.fetch_items(MARKET, [NVDA], SINCE, observed_at=OBSERVED)
    ids = [i.id for i in items]
    assert "stocktwits:612300000" not in ids  # May message cut off
    assert len(items) == 2

    def boom(inst, market, since):
        raise ConnectionError("rate limited")

    monkeypatch.setattr(adapter, "_fetch_raw", boom)
    assert adapter.fetch_items(MARKET, [NVDA], SINCE, observed_at=OBSERVED) == []
