"""Tests for the deterministic event classifier."""

from __future__ import annotations

from datetime import datetime, timezone

from detector_fin.aggregator.events import (
    EVENT_CLASSIFIER_VERSION,
    classify_event,
    count_events,
)
from detector_fin.schemas import RawItem


def test_classification_per_language():
    assert classify_event("Q1 earnings beat expectations") == "earnings"
    assert classify_event("贵州茅台2026年第一季度报告") == "earnings"
    assert classify_event("분기보고서 (2026.03)") == "earnings"
    assert classify_event("证监会下发问询函") == "regulation"
    assert classify_event("회사 상대 소송 제기") == "litigation"
    assert classify_event("股票临时停牌公告") == "suspension"
    assert classify_event("据传公司将重组") == "rumor"
    assert classify_event("Fed signals interest rate path") == "macro"
    assert classify_event("management raises full-year guidance") == "guidance"


def test_priority_order_suspension_beats_rumor():
    assert classify_event("据传明日临时停牌") == "suspension"


def test_unclassified_returns_none():
    assert classify_event("nice weather today") is None


def test_count_events_ignores_unclassified():
    def item(id_, text, lang="en"):
        return RawItem(
            id=id_,
            source="rss_news",
            market_id="US",
            lang=lang,
            text=text,
            event_time=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
            observed_at=datetime(2026, 6, 16, 12, 5, tzinfo=timezone.utc),
        )

    counts = count_events(
        [
            item("a", "earnings beat"),
            item("b", "业绩预告", lang="zh"),
            item("c", "irrelevant chatter"),
        ]
    )
    assert counts == {"earnings": 1, "guidance": 1}
    assert EVENT_CLASSIFIER_VERSION.startswith("keyword-")
