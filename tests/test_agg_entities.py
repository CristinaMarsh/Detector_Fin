"""Tests for entity resolution (mention -> ticker)."""

from __future__ import annotations

from datetime import datetime, timezone

from detector_fin.aggregator.entities import entity_id_for, resolve_items
from detector_fin.schemas import RawItem
from detector_fin.universe import Instrument

NVDA = Instrument(
    ticker="NVDA", name_en="NVIDIA", market_id="US", instrument_type="equity"
)
MOUTAI = Instrument(
    ticker="600519.SS",
    name_en="Kweichow Moutai",
    market_id="CN",
    instrument_type="equity",
)


def _item(id_: str, text: str, hints: list[str] | None = None, lang="en") -> RawItem:
    return RawItem(
        id=id_,
        source="rss_news",
        market_id="US",
        lang=lang,
        ticker_hints=hints or [],
        text=text,
        event_time=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
        observed_at=datetime(2026, 6, 16, 12, 5, tzinfo=timezone.utc),
    )


def test_hints_trusted_directly():
    item = _item("a", "no mention in text at all", hints=["NVDA"])
    resolved = resolve_items([item], [NVDA, MOUTAI])
    assert [i.id for i in resolved["NVDA"]] == ["a"]


def test_cashtag_and_name_matching():
    by_tag = _item("a", "loading up on $NVDA calls")
    by_name = _item("b", "NVIDIA announced its new datacenter line")
    resolved = resolve_items([by_tag, by_name], [NVDA])
    assert {i.id for i in resolved["NVDA"]} == {"a", "b"}


def test_cn_code_matching_without_digit_bleed():
    hit = _item("a", "关注600519的走势", lang="zh")
    no_bleed = _item("b", "订单号16005190001与股票无关", lang="zh")
    resolved = resolve_items([hit, no_bleed], [MOUTAI])
    assert [i.id for i in resolved.get("600519.SS", [])] == ["a"]


def test_unresolved_items_dropped_never_guessed():
    item = _item("a", "generic market chatter about nothing specific")
    assert resolve_items([item], [NVDA, MOUTAI]) == {}


def test_item_may_resolve_to_multiple_tickers():
    item = _item("a", "pair trade: $NVDA vs Kweichow Moutai")
    resolved = resolve_items([item], [NVDA, MOUTAI])
    assert set(resolved) == {"NVDA", "600519.SS"}


def test_entity_id_is_deterministic_slug():
    assert entity_id_for(NVDA) == "nvidia"
    assert entity_id_for(MOUTAI) == "kweichow-moutai"
