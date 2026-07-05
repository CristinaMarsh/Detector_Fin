"""Tests for the fetch_disclosures CLI, driven with a stubbed adapter."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from detector_fin import fetch_disclosures
from detector_fin.schemas import RawItem
from detector_fin.storage import ParquetStore

OBSERVED = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)


class StubAdapter:
    name = "stub"

    def __init__(self):
        self.calls = []

    def fetch_items(self, market, instruments, since, observed_at=None):
        self.calls.append((market.market_id, [i.ticker for i in instruments], since))
        return [
            RawItem(
                id="sec_edgar:0001045810-26-000123",
                source="sec_edgar",
                market_id="US",
                lang="en",
                ticker_hints=["NVDA"],
                text="8-K: 8-K (filed 2026-06-15)",
                url="https://www.sec.gov/Archives/edgar/data/1045810/000104581026000123/nvda-20260615.htm",
                event_time=datetime(2026, 6, 15, 20, 31, 22, tzinfo=timezone.utc),
                observed_at=observed_at or OBSERVED,
            )
        ]


def test_run_appends_items_to_store(tmp_path):
    stub = StubAdapter()
    items = fetch_disclosures.run(
        "US",
        date(2026, 6, 1),
        store_root=tmp_path,
        adapter=stub,
        observed_at=OBSERVED,
    )
    assert len(items) == 1

    market_id, tickers, since = stub.calls[0]
    assert market_id == "US"
    assert "NVDA" in tickers
    assert since == datetime(2026, 6, 1, tzinfo=timezone.utc)  # tz-aware cutoff

    stored = ParquetStore(tmp_path).read("raw_items", RawItem, market_id="US")
    assert len(stored) == 1
    assert stored[0].source == "sec_edgar"
    # Partitioned by observed_at UTC date.
    assert (tmp_path / "raw_items" / "market_id=US" / "date=2026-06-20").is_dir()


def test_build_adapter_registry():
    from detector_fin.fetcher.disclosures import (
        CninfoAdapter,
        DartAdapter,
        SecEdgarAdapter,
    )

    assert isinstance(fetch_disclosures.build_adapter("US"), SecEdgarAdapter)
    assert isinstance(fetch_disclosures.build_adapter("cn"), CninfoAdapter)
    assert isinstance(fetch_disclosures.build_adapter("KR"), DartAdapter)


def test_build_adapter_unknown_market_exits():
    with pytest.raises(SystemExit):
        fetch_disclosures.build_adapter("JP")


def test_main_with_stub(tmp_path, monkeypatch, capsys):
    stub = StubAdapter()
    monkeypatch.setattr(fetch_disclosures, "build_adapter", lambda market_id: stub)
    rc = fetch_disclosures.main(
        ["--market", "US", "--since", "2026-06-01", "--store", str(tmp_path)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 disclosure items" in out and "US" in out
