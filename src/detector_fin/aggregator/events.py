"""Deterministic event classification (section 1.2).

Keyword tables per language map an item's text to the contract's event
taxonomy {earnings, guidance, litigation, regulation, macro, rumor,
suspension}. Deliberately simple and fully unit-testable; the classifier
version is persisted so future upgrades (an ML classifier) are
distinguishable in stored data, mirroring the generated-regressor rule for
sentiment scores.
"""

from __future__ import annotations

from collections import Counter

from ..schemas import EventType, RawItem

EVENT_CLASSIFIER_VERSION = "keyword-0.1"

# Ordered: the first matching event type wins (suspension outranks rumor etc.).
_KEYWORDS: list[tuple[EventType, tuple[str, ...]]] = [
    (
        "suspension",
        ("suspension", "suspended", "trading halt", "停牌", "临时停牌", "거래정지"),
    ),
    # Guidance outranks earnings: a forecast OF earnings (e.g. 业绩预告) is
    # guidance, while realised-results keywords fall through to earnings.
    (
        "guidance",
        ("guidance", "outlook", "forecast", "预告", "指引", "전망", "가이던스"),
    ),
    (
        "earnings",
        (
            "earnings",
            "quarterly report",
            "annual report",
            "10-k",
            "10-q",
            "业绩",
            "季度报告",
            "年度报告",
            "季报",
            "年报",
            "financial results",
            "실적",
            "분기보고서",
            "사업보고서",
        ),
    ),
    (
        "litigation",
        ("lawsuit", "litigation", "sued", "court", "诉讼", "起诉", "仲裁", "소송"),
    ),
    (
        "regulation",
        (
            "regulator",
            "regulation",
            "regulatory",
            "sec probe",
            "investigation",
            "监管",
            "证监会",
            "问询函",
            "调查",
            "규제",
            "금융위",
            "조사",
        ),
    ),
    (
        "macro",
        (
            "fed",
            "interest rate",
            "inflation",
            "gdp",
            "central bank",
            "宏观",
            "央行",
            "利率",
            "降准",
            "금리",
            "물가",
            "중앙은행",
        ),
    ),
    (
        "rumor",
        (
            "rumor",
            "rumour",
            "unconfirmed",
            "据传",
            "传闻",
            "小道消息",
            "루머",
            "찌라시",
        ),
    ),
]


def classify_event(text: str) -> EventType | None:
    """Return the first matching event type for ``text``, or None."""
    lowered = text.lower()
    for event_type, keywords in _KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return event_type
    return None


def count_events(items: list[RawItem]) -> dict[EventType, int]:
    """Event-type counts over a batch of items (unclassified items ignored)."""
    counts: Counter[EventType] = Counter()
    for item in items:
        event_type = classify_event(item.text)
        if event_type is not None:
            counts[event_type] += 1
    return dict(counts)


__all__ = ["classify_event", "count_events", "EVENT_CLASSIFIER_VERSION"]
