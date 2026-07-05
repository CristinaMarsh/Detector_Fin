"""Fixture-based tests for the SEC EDGAR disclosure adapter (no network)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from detector_fin.fetcher.disclosures import SecEdgarAdapter
from detector_fin.market_config import load_market_config
from detector_fin.universe import Instrument

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "disclosures"
MARKET = load_market_config("US")
OBSERVED = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)

NVDA = Instrument(
    ticker="NVDA",
    name_en="NVIDIA",
    market_id="US",
    instrument_type="equity",
    ids={"edgar_cik": "0001045810"},
)
NO_CIK = Instrument(
    ticker="XXXX", name_en="No Cik Corp", market_id="US", instrument_type="equity"
)


def _payload() -> dict:
    return json.loads((FIXTURES / "edgar_nvda.json").read_text())


def test_transform_emits_only_forms_of_interest():
    items = SecEdgarAdapter()._transform(NVDA, _payload(), MARKET, OBSERVED)
    forms = [i.meta["form"] for i in items]
    assert forms == ["8-K", "10-Q", "10-K"]  # Form 4 filtered out
    assert all(i.source == "sec_edgar" and i.lang == "en" for i in items)
    assert all(i.ticker_hints == ["NVDA"] for i in items)


def test_filing_url_and_id_construction():
    items = SecEdgarAdapter()._transform(NVDA, _payload(), MARKET, OBSERVED)
    first = items[0]
    assert first.id == "sec_edgar:0001045810-26-000123"
    # CIK loses zero-padding, accession loses dashes, document verbatim.
    assert first.url == (
        "https://www.sec.gov/Archives/edgar/data/1045810/"
        "000104581026000123/nvda-20260615.htm"
    )


def test_event_time_is_utc_instant():
    items = SecEdgarAdapter()._transform(NVDA, _payload(), MARKET, OBSERVED)
    first = items[0]
    # 2026-06-15T16:31:22-04:00 == 20:31:22 UTC
    assert first.event_time == datetime(2026, 6, 15, 20, 31, 22, tzinfo=timezone.utc)
    assert first.observed_at == OBSERVED


def test_fetch_items_applies_since_filter(monkeypatch):
    adapter = SecEdgarAdapter()
    monkeypatch.setattr(adapter, "_fetch_raw", lambda inst, market, since: _payload())
    since = datetime(2026, 6, 1, tzinfo=timezone.utc)
    items = adapter.fetch_items(MARKET, [NVDA], since, observed_at=OBSERVED)
    # The February 10-K falls before the since cutoff.
    assert [i.meta["form"] for i in items] == ["8-K", "10-Q"]


def test_instrument_without_cik_is_skipped(monkeypatch):
    adapter = SecEdgarAdapter()
    calls = []

    def fake_fetch(inst, market, since):
        calls.append(inst.ticker)
        return _payload()

    monkeypatch.setattr(adapter, "_fetch_raw", fake_fetch)
    since = datetime(2026, 6, 1, tzinfo=timezone.utc)
    items = adapter.fetch_items(MARKET, [NO_CIK, NVDA], since, observed_at=OBSERVED)
    assert calls == ["NVDA"]  # NO_CIK never fetched, never guessed
    assert items


def test_fetch_failure_degrades_to_empty_batch(monkeypatch):
    adapter = SecEdgarAdapter()

    def boom(inst, market, since):
        raise ConnectionError("network down")

    monkeypatch.setattr(adapter, "_fetch_raw", boom)
    since = datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert adapter.fetch_items(MARKET, [NVDA], since, observed_at=OBSERVED) == []
