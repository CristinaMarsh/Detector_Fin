"""TickerDaySnapshot builder -- the ONLY input the Judge accepts (section 1.2).

Assembles one snapshot per (ticker, date) from already-resolved items and bar
history. Discipline enforced here:

* Temporal cutoff: only items with ``observed_at`` strictly before the
  market's decision instant for the date enter the snapshot (section 3).
* Fragments pass the sanitisation boundary; ``source_url`` propagates
  VERBATIM from ``RawItem.url`` (section 3 provenance rule).
* ``sentiment_model_version`` and the translator version are persisted with
  the snapshot (generated-regressor rule).
"""

from __future__ import annotations

import statistics
from collections import Counter
from datetime import date

from ..market_config import MarketConfig
from ..schemas import Fragment, MAX_FRAGMENTS, MarketBar, RawItem, TickerDaySnapshot
from ..universe import Instrument
from .dedup import dedup_items
from .entities import entity_id_for
from .events import count_events
from .market_stats import compute_market_stats
from .sanitize import sanitize_text
from .sentiment import SentimentScorer, rolling_sentiment_z
from .translate import IdentityTranslator, Translator


def _fragment(item: RawItem, translator: Translator) -> Fragment:
    text = sanitize_text(item.text)
    text_en = (
        text
        if item.lang == "en"
        else sanitize_text(translator.to_english(item.text, item.lang))
    )
    return Fragment(
        text_original=text,
        text_en=text_en,
        source_name=item.source,
        source_url=item.url,  # verbatim from RawItem.url, never rewritten
    )


def build_snapshot(
    *,
    ticker: str,
    date_local: date,
    items: list[RawItem],
    bars: list[MarketBar],
    market: MarketConfig,
    instrument: Instrument,
    scorer: SentimentScorer,
    translator: Translator | None = None,
    sentiment_history: list[float] | None = None,
    item_count_history: list[int] | None = None,
) -> TickerDaySnapshot:
    """Build the snapshot for one ticker and one local trading date.

    ``sentiment_history`` / ``item_count_history`` are trailing per-day series
    (oldest first, excluding today) used for the rolling z-score and the burst
    ratio; both stay None in the snapshot until enough history exists.
    """
    translator = translator or IdentityTranslator()
    cutoff = market.decision_datetime_utc(date_local)
    usable = dedup_items([i for i in items if i.observed_at < cutoff])

    n_items_by_source = dict(Counter(i.source for i in usable))

    sentiment_z = None
    raw_scores = [scorer.score(i.text, i.lang) for i in usable]
    if raw_scores and sentiment_history is not None:
        sentiment_z = rolling_sentiment_z(
            statistics.fmean(raw_scores), sentiment_history
        )

    burst_score = None
    if item_count_history:
        trailing_mean = statistics.fmean(item_count_history)
        if trailing_mean > 0:
            burst_score = len(usable) / trailing_mean

    fragments = [
        _fragment(item, translator)
        for item in sorted(usable, key=lambda i: i.event_time, reverse=True)[
            :MAX_FRAGMENTS
        ]
    ]

    return TickerDaySnapshot(
        ticker=ticker,
        entity_id=entity_id_for(instrument),
        market_id=market.market_id,
        instrument_type=instrument.instrument_type,
        date_local=date_local,
        n_items_by_source=n_items_by_source,
        sentiment_z=sentiment_z,
        sentiment_model_version=scorer.model_version,
        burst_score=burst_score,
        event_counts=count_events(usable),
        top_fragments=fragments,
        market=compute_market_stats(bars, date_local, market, instrument),
    )


__all__ = ["build_snapshot"]
