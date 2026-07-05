"""Authoritative data schemas for the Detector_Fin pipeline.

These models are the contract between pipeline stages (Fetcher -> Aggregator
-> Judge -> Report). They mirror section 2 of the Design Contract v0.2.2.

Design invariants enforced here:

* ``event_time`` and ``observed_at`` are timezone-aware UTC instants. Temporal
  discipline (section 3) depends on ``observed_at`` being a comparable UTC
  instant, so we normalise and validate it on construction.
* ``TickerDaySnapshot`` is the ONLY input the Judge accepts. It carries no raw
  text beyond the sanitised, length-capped ``top_fragments``.
* Text fragments that survive into a snapshot are marked untrusted and carry
  both the original-language string and a machine translation to English.

Every persisted record implements :class:`StorageRecord` so the storage layer
can partition it by ``market_id`` and a calendar date without hard-coding field
names per model.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

# ``en`` (English), ``zh`` (Chinese), ``ko`` (Korean). Sentiment scoring is
# per-language with pinned model versions; raw scores never cross languages.
Lang = Literal["en", "zh", "ko"]

# Instrument taxonomy. An ETF is not just a labelled equity: it carries extra
# risk dimensions (NAV premium/discount, tracking error) and its own price-limit
# regime, so ``instrument_type`` is a first-class field, never an after-the-fact
# tag (Design Contract v0.2.2, sections 0 and 2).
InstrumentType = Literal["equity", "etf"]

# Event taxonomy used by the Aggregator's event classifier (section 1.2).
EventType = Literal[
    "earnings",
    "guidance",
    "litigation",
    "regulation",
    "macro",
    "rumor",
    "suspension",
]

# Market identifiers are short upper-case codes ("US", "CN", "KR", ...). Kept as
# a validated string rather than an enum so new markets can be added by config
# alone (the market abstraction goal of v0.2).
MarketId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=8),
]

MAX_FRAGMENTS = 10
MAX_FRAGMENT_CHARS = 280


def _as_utc(value: datetime) -> datetime:
    """Return ``value`` as a timezone-aware UTC datetime.

    Naive datetimes are rejected: an instant without a timezone cannot be
    ordered against a decision time and would silently break the temporal
    discipline guarantees in section 3.
    """
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware (UTC); got a naive value")
    return value.astimezone(timezone.utc)


class StorageRecord(BaseModel):
    """Base for every append-only, on-disk record.

    Subclasses expose ``partition_keys`` (market + calendar date) so the
    storage layer can lay records out under ``market_id=.../date=...`` without
    knowing anything model-specific.
    """

    model_config = ConfigDict(extra="forbid")

    def partition_keys(self) -> tuple[str, date]:
        raise NotImplementedError

    def record_key(self) -> str:
        """A short, human-meaningful key for the row (ticker or id)."""
        raise NotImplementedError


class RawItem(StorageRecord):
    """A single raw observation from a source, persisted append-only.

    The Fetcher does NO interpretation: fidelity, language tag, and timestamps
    only. Partitioned by ingestion date, derived from ``observed_at`` in UTC.
    """

    id: str
    source: str
    market_id: MarketId
    lang: Lang
    ticker_hints: list[str] = Field(default_factory=list)
    text: str
    url: str | None = None
    author_hash: str | None = None
    event_time: datetime  # when the underlying event happened (UTC)
    observed_at: datetime  # when we fetched/observed it (UTC)
    meta: dict = Field(default_factory=dict)

    @field_validator("event_time", "observed_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _as_utc(v)

    def partition_keys(self) -> tuple[str, date]:
        # Raw items have no local trading date; partition by UTC ingestion date.
        return self.market_id, self.observed_at.date()

    def record_key(self) -> str:
        return self.id


class MarketBar(StorageRecord):
    """A single daily OHLCV bar for one instrument (market-data fetcher output).

    Prices and volume are in the market's local currency and share units; no FX
    conversion happens in the pipeline (section 0). ``observed_at`` is the UTC
    instant the bar was fetched, so bars obey the same point-in-time discipline
    as every other record. Partitioned by ``market_id`` / ``date_local``.
    """

    ticker: str
    market_id: MarketId
    instrument_type: InstrumentType
    date_local: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    currency: str
    source: str  # adapter name, e.g. "yfinance", "akshare", "pykrx"
    observed_at: datetime  # UTC fetch instant

    @field_validator("observed_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _as_utc(v)

    def partition_keys(self) -> tuple[str, date]:
        return self.market_id, self.date_local

    def record_key(self) -> str:
        return self.ticker


class Fragment(BaseModel):
    """A sanitised text fragment surfaced to the human reviewer (section 2).

    Text fields are untrusted external content; URLs, instructions, and markup
    are stripped at the Aggregator's sanitisation boundary before construction.
    ``source_url`` propagates VERBATIM from ``RawItem.url`` per the section 3
    provenance rule -- never backfilled or rewritten.
    """

    model_config = ConfigDict(extra="forbid")

    text_original: Annotated[str, StringConstraints(max_length=MAX_FRAGMENT_CHARS)]
    text_en: Annotated[str, StringConstraints(max_length=MAX_FRAGMENT_CHARS)]
    source_name: str
    source_url: str | None = None


class MarketStats(BaseModel):
    """Per-ticker, per-day market statistics block of a snapshot.

    Halts/suspensions produce explicit gaps: ``suspended`` is set and price
    fields may be ``None`` rather than forward-filled. A limit-hit day sets
    ``limit_hit``. ``dist_to_upper_limit`` / ``dist_to_lower_limit`` are only
    meaningful for markets with price limits (CN, KR) and are ``None`` for the
    US.
    """

    model_config = ConfigDict(extra="forbid")

    close: float | None = None
    ret_1d: float | None = None
    rv_20d: float | None = None
    drawdown_60d: float | None = None
    limit_hit: bool = False
    suspended: bool = False
    dist_to_upper_limit: float | None = None
    dist_to_lower_limit: float | None = None


class TickerDaySnapshot(StorageRecord):
    """Per-ticker, per-day structured features -- the ONLY Judge input.

    ADR vs local line are DISTINCT tickers linked via ``entity_id``.
    ``sentiment_z`` is a within-ticker rolling z-score (window >= 60 trading
    days); raw sentiment is never carried here or compared across languages.
    """

    ticker: str
    entity_id: str
    market_id: MarketId
    instrument_type: InstrumentType = "equity"
    date_local: date
    n_items_by_source: dict[str, int] = Field(default_factory=dict)
    sentiment_z: float | None = None
    sentiment_model_version: str | None = None
    burst_score: float | None = None
    event_counts: dict[EventType, int] = Field(default_factory=dict)
    top_fragments: list[Fragment] = Field(default_factory=list)
    market: MarketStats = Field(default_factory=MarketStats)

    @field_validator("top_fragments")
    @classmethod
    def _cap_fragments(cls, v: list[Fragment]) -> list[Fragment]:
        if len(v) > MAX_FRAGMENTS:
            raise ValueError(f"top_fragments capped at {MAX_FRAGMENTS}; got {len(v)}")
        return v

    def partition_keys(self) -> tuple[str, date]:
        return self.market_id, self.date_local

    def record_key(self) -> str:
        return self.ticker


class RiskScore(StorageRecord):
    """Deterministic quant-path output with component breakdown (section 1.3)."""

    ticker: str
    market_id: MarketId
    instrument_type: InstrumentType = "equity"
    date_local: date
    score: Annotated[float, Field(ge=0.0, le=1.0)]
    components: dict[str, float] = Field(default_factory=dict)
    method_version: str

    def partition_keys(self) -> tuple[str, date]:
        return self.market_id, self.date_local

    def record_key(self) -> str:
        return self.ticker


class EvidenceDossier(StorageRecord):
    """LLM-path structured output. Never a buy/sell verdict (section 1.3)."""

    ticker: str
    market_id: MarketId
    date_local: date
    summary_claims: list[str] = Field(default_factory=list)
    supporting_counts: dict[str, int] = Field(default_factory=dict)
    uncertainty_notes: list[str] = Field(default_factory=list)
    contrarian_case: str | None = None
    model_version: str
    prompt_hash: str

    def partition_keys(self) -> tuple[str, date]:
        return self.market_id, self.date_local

    def record_key(self) -> str:
        return self.ticker


__all__ = [
    "Lang",
    "EventType",
    "InstrumentType",
    "MarketId",
    "MAX_FRAGMENTS",
    "MAX_FRAGMENT_CHARS",
    "StorageRecord",
    "RawItem",
    "MarketBar",
    "Fragment",
    "MarketStats",
    "TickerDaySnapshot",
    "RiskScore",
    "EvidenceDossier",
]
