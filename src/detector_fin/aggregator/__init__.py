"""Aggregator: RawItem streams -> per-ticker, per-day snapshots (section 1.2).

Modules:
    sanitize      -- the sanitisation boundary for text fragments
    dedup         -- language-aware near-duplicate removal
    entities      -- mention -> ticker resolution and entity ids
    events        -- deterministic event classification
    sentiment     -- pluggable per-language sentiment scorers (pinned versions)
    translate     -- pluggable fragment translation
    market_stats  -- MarketStats from MarketBar history + MarketConfig
    snapshot      -- TickerDaySnapshot builder (the ONLY Judge input)
"""

from __future__ import annotations

from .dedup import dedup_items
from .entities import entity_id_for, resolve_items
from .events import EVENT_CLASSIFIER_VERSION, classify_event, count_events
from .market_stats import compute_market_stats
from .sanitize import sanitize_text
from .sentiment import LexiconScorer, SentimentScorer, rolling_sentiment_z
from .snapshot import build_snapshot
from .translate import IdentityTranslator, Translator

__all__ = [
    "sanitize_text",
    "dedup_items",
    "resolve_items",
    "entity_id_for",
    "classify_event",
    "count_events",
    "EVENT_CLASSIFIER_VERSION",
    "SentimentScorer",
    "LexiconScorer",
    "rolling_sentiment_z",
    "Translator",
    "IdentityTranslator",
    "compute_market_stats",
    "build_snapshot",
]
