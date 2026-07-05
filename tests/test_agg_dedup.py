"""Tests for language-aware near-duplicate removal."""

from __future__ import annotations

from datetime import datetime, timezone

from detector_fin.aggregator.dedup import dedup_items
from detector_fin.schemas import RawItem


def _item(id_: str, text: str, lang: str = "en", hour: int = 12) -> RawItem:
    return RawItem(
        id=id_,
        source="rss_news",
        market_id="US",
        lang=lang,
        text=text,
        event_time=datetime(2026, 6, 16, hour, 0, tzinfo=timezone.utc),
        observed_at=datetime(2026, 6, 16, hour, 5, tzinfo=timezone.utc),
    )


def test_near_duplicates_collapse_to_earliest():
    a = _item("a", "NVIDIA beats earnings expectations for Q1 2026", hour=9)
    b = _item("b", "NVIDIA beats earnings expectations for Q1 2026!", hour=11)
    c = _item("c", "Completely different macro story about rates", hour=10)
    survivors = dedup_items([b, a, c])
    ids = {i.id for i in survivors}
    assert ids == {"a", "c"}  # earliest of the near-dupe pair survives


def test_cjk_near_duplicates_collapse():
    a = _item("a", "贵州茅台一季度业绩超预期，股价大涨", lang="zh", hour=9)
    b = _item("b", "贵州茅台一季度业绩超预期，股价大涨。", lang="zh", hour=10)
    c = _item("c", "宁德时代发布新一代电池技术", lang="zh", hour=9)
    survivors = dedup_items([a, b, c])
    assert {i.id for i in survivors} == {"a", "c"}


def test_same_text_across_languages_not_compared():
    # Identical byte content but different lang tags must both survive:
    # comparison is within-language only.
    a = _item("a", "identical text 123", lang="en")
    b = _item("b", "identical text 123", lang="ko")
    assert {i.id for i in dedup_items([a, b])} == {"a", "b"}


def test_short_texts_do_not_false_positive():
    a = _item("a", "up")
    b = _item("b", "down")
    assert len(dedup_items([a, b])) == 2
