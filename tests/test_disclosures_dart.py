"""Fixture-based tests for the DART disclosure adapter (no network)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from detector_fin.fetcher.disclosures import DartAdapter
from detector_fin.market_config import load_market_config
from detector_fin.universe import Instrument

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "disclosures"
MARKET = load_market_config("KR")
OBSERVED = datetime(2026, 6, 20, 0, 0, tzinfo=timezone.utc)

SAMSUNG = Instrument(
    ticker="005930.KS",
    name_en="Samsung Electronics",
    market_id="KR",
    instrument_type="equity",
    ids={"dart_corp_code": "00126380"},
)
NO_CODE = Instrument(
    ticker="000660.KS", name_en="SK Hynix", market_id="KR", instrument_type="equity"
)


def _payload() -> dict:
    return json.loads((FIXTURES / "dart_005930.json").read_text())


def test_transform_maps_filings():
    items = DartAdapter()._transform(SAMSUNG, _payload(), MARKET, OBSERVED)
    assert len(items) == 2
    first = items[0]
    assert first.id == "dart:20260615000321"
    assert first.source == "dart"
    assert first.lang == "ko"
    assert first.text == "분기보고서 (2026.03)"
    assert first.url == "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260615000321"


def test_event_time_is_midnight_kst_as_utc():
    items = DartAdapter()._transform(SAMSUNG, _payload(), MARKET, OBSERVED)
    kst_midnight = datetime(2026, 6, 15, 0, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    assert items[0].event_time == kst_midnight
    # Stored value is normalised to UTC (previous day 15:00 UTC).
    assert items[0].event_time == datetime(2026, 6, 14, 15, 0, tzinfo=timezone.utc)


def test_error_status_yields_empty_batch():
    payload = {"status": "013", "message": "no data", "list": []}
    assert DartAdapter()._transform(SAMSUNG, payload, MARKET, OBSERVED) == []


def test_requires_api_key_and_corp_code(monkeypatch):
    adapter = DartAdapter()
    monkeypatch.setattr(adapter, "_fetch_raw", lambda inst, market, since: _payload())
    since = datetime(2026, 6, 1, tzinfo=timezone.utc)

    monkeypatch.delenv("DART_API_KEY", raising=False)
    assert adapter.fetch_items(MARKET, [SAMSUNG], since, observed_at=OBSERVED) == []

    monkeypatch.setenv("DART_API_KEY", "test-key")
    items = adapter.fetch_items(MARKET, [SAMSUNG, NO_CODE], since, observed_at=OBSERVED)
    assert items  # SAMSUNG fetched
    assert all(i.ticker_hints == ["005930.KS"] for i in items)  # NO_CODE skipped


def test_since_filter(monkeypatch):
    adapter = DartAdapter()
    monkeypatch.setenv("DART_API_KEY", "test-key")
    monkeypatch.setattr(adapter, "_fetch_raw", lambda inst, market, since: _payload())
    since = datetime(2026, 6, 10, tzinfo=timezone.utc)
    items = adapter.fetch_items(MARKET, [SAMSUNG], since, observed_at=OBSERVED)
    assert [i.id for i in items] == ["dart:20260615000321"]  # June 2 filing cut off
