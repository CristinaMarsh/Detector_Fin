"""Tests for the fetch_sentiment CLI, driven with a stubbed adapter."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from detector_fin import fetch_sentiment
from detector_fin.schemas import RawItem
from detector_fin.storage import ParquetStore

OBSERVED = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)


class StubAdapter:
    name = "stub"

    def __init__(self):
        self.calls = []

    def fetch_items(self, market, instruments, since, observed_at=None):
        self.calls.append((market.market_id, [i.ticker for i in instruments], since))
        return [
            RawItem(
                id="stocktwits:612345001",
                source="stocktwits",
                market_id="US",
                lang="en",
                ticker_hints=["NVDA"],
                text="NVDA breaking out on volume",
                url="https://stocktwits.com/message/612345001",
                event_time=datetime(2026, 6, 16, 14, 5, 31, tzinfo=timezone.utc),
                observed_at=observed_at or OBSERVED,
            )
        ]


def test_run_appends_items_to_store(tmp_path):
    stub = StubAdapter()
    items = fetch_sentiment.run(
        "US",
        date(2026, 6, 1),
        store_root=tmp_path,
        adapter=stub,
        observed_at=OBSERVED,
    )
    assert len(items) == 1
    market_id, tickers, since = stub.calls[0]
    assert market_id == "US" and "NVDA" in tickers
    assert since == datetime(2026, 6, 1, tzinfo=timezone.utc)

    stored = ParquetStore(tmp_path).read("raw_items", RawItem, market_id="US")
    assert len(stored) == 1
    assert stored[0].source == "stocktwits"


def test_build_adapter_registry():
    from detector_fin.fetcher.sentiment import (
        EastmoneyGubaAdapter,
        NaverBoardAdapter,
        StocktwitsAdapter,
    )

    assert isinstance(fetch_sentiment.build_adapter("US"), StocktwitsAdapter)
    assert isinstance(fetch_sentiment.build_adapter("cn"), EastmoneyGubaAdapter)
    assert isinstance(fetch_sentiment.build_adapter("KR"), NaverBoardAdapter)


def test_build_adapter_unknown_market_exits():
    with pytest.raises(SystemExit):
        fetch_sentiment.build_adapter("JP")


def test_main_with_stub(tmp_path, monkeypatch, capsys):
    stub = StubAdapter()
    monkeypatch.setattr(fetch_sentiment, "build_adapter", lambda market_id: stub)
    rc = fetch_sentiment.main(
        ["--market", "US", "--since", "2026-06-01", "--store", str(tmp_path)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 sentiment items" in out and "US" in out
