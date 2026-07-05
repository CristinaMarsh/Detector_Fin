"""Fixture-based tests for the Naver board sentiment adapter (no network)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from detector_fin.fetcher.sentiment import NaverBoardAdapter
from detector_fin.market_config import load_market_config
from detector_fin.universe import Instrument

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sentiment"
MARKET = load_market_config("KR")
OBSERVED = datetime(2026, 6, 17, 0, 0, tzinfo=timezone.utc)
SINCE = datetime(2026, 6, 1, tzinfo=timezone.utc)

SAMSUNG = Instrument(
    ticker="005930.KS",
    name_en="Samsung Electronics",
    market_id="KR",
    instrument_type="equity",
)


def _payload() -> str:
    return (FIXTURES / "naver_005930.html").read_text()


def test_transform_parses_board_rows():
    items = NaverBoardAdapter()._transform(SAMSUNG, _payload(), MARKET, OBSERVED)
    assert len(items) == 3
    first = items[0]
    assert first.id == "naver_finance_board:005930:310000123"
    assert first.lang == "ko"
    assert first.text == "실적 발표 앞두고 외국인 순매수 지속"
    assert first.url == (
        "https://finance.naver.com/item/board_read.naver?code=005930&nid=310000123"
    )


def test_kst_normalised_to_utc():
    items = NaverBoardAdapter()._transform(SAMSUNG, _payload(), MARKET, OBSERVED)
    # 2026.06.16 09:12 KST (+9) == 00:12 UTC.
    assert items[0].event_time == datetime(2026, 6, 16, 0, 12, tzinfo=timezone.utc)


def test_fetch_items_since_filter_and_degradation(monkeypatch):
    adapter = NaverBoardAdapter()
    adapter.request_delay_seconds = 0  # stubbed fetch: no politeness delay needed
    monkeypatch.setattr(adapter, "_fetch_raw", lambda inst, market, since: _payload())
    items = adapter.fetch_items(MARKET, [SAMSUNG], SINCE, observed_at=OBSERVED)
    # The May post falls before the since cutoff.
    assert [i.meta["nid"] for i in items] == ["310000123", "310000098"]

    def boom(inst, market, since):
        raise ConnectionError("blocked")

    monkeypatch.setattr(adapter, "_fetch_raw", boom)
    assert adapter.fetch_items(MARKET, [SAMSUNG], SINCE, observed_at=OBSERVED) == []


def test_empty_page_yields_no_items():
    assert NaverBoardAdapter()._transform(SAMSUNG, "", MARKET, OBSERVED) == []
