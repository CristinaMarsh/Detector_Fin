"""Per-language sentiment scoring with pinned model versions (section 1.2).

The contract pins the production path to per-language FinBERT variants (or an
LLM scorer): en -> FinBERT, zh -> a Chinese FinBERT variant, ko ->
KR-FinBERT-SC. :class:`TransformersScorer` is that path -- it lazily imports
``transformers`` (optional extra ``sentiment``) and persists the exact model
id as the score version.

:class:`LexiconScorer` is a deterministic, dependency-free BASELINE for tests
and for the market-only baseline runs of section 4. It is not a FinBERT
substitute and its version string says so.

Raw scores are never compared across languages; only within-ticker rolling
z-scores (window >= 60 trading days) enter the Judge
(:func:`rolling_sentiment_z`).
"""

from __future__ import annotations

import statistics
from typing import Protocol, runtime_checkable

from ..schemas import Lang

MIN_Z_WINDOW = 60

# Production model ids per language. zh has no pinned default yet: configure
# one explicitly rather than inheriting a wrong model (never guess).
DEFAULT_MODEL_IDS: dict[str, str | None] = {
    "en": "ProsusAI/finbert",
    "ko": "snunlp/KR-FinBert-SC",
    "zh": None,
}


@runtime_checkable
class SentimentScorer(Protocol):
    """Protocol every sentiment scorer implements."""

    model_version: str

    def score(self, text: str, lang: Lang) -> float:
        """Polarity in [-1, 1]."""
        ...


_POSITIVE = {
    "en": ("beat", "surge", "growth", "record", "profit", "upgrade", "buy"),
    "zh": ("利好", "大涨", "超预期", "增长", "创新高", "回购", "买入"),
    "ko": ("상승", "호실적", "성장", "매수", "신고가"),
}
_NEGATIVE = {
    "en": ("miss", "plunge", "fraud", "lawsuit", "downgrade", "loss", "sell"),
    "zh": ("利空", "跌停", "亏损", "诉讼", "减持", "暴跌", "卖出"),
    "ko": ("하락", "적자", "소송", "매도", "급락"),
}


class LexiconScorer:
    """Deterministic keyword-polarity baseline. Not a FinBERT substitute."""

    model_version = "baseline-lexicon-0.1"

    def score(self, text: str, lang: Lang) -> float:
        lowered = text.lower()
        positives = sum(lowered.count(w) for w in _POSITIVE.get(lang, ()))
        negatives = sum(lowered.count(w) for w in _NEGATIVE.get(lang, ()))
        total = positives + negatives
        if total == 0:
            return 0.0
        return (positives - negatives) / total


class TransformersScorer:
    """FinBERT-family scorer backed by HuggingFace transformers.

    ``model_id`` is pinned per language (see DEFAULT_MODEL_IDS) and persisted
    verbatim as ``model_version`` alongside every score, per the
    generated-regressor rule. Requires the optional ``sentiment`` extra.
    """

    def __init__(self, model_id: str):
        self.model_version = model_id
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            from transformers import pipeline  # lazy: optional dependency

            self._pipeline = pipeline("sentiment-analysis", model=self.model_version)
        return self._pipeline

    def score(self, text: str, lang: Lang) -> float:
        result = self._load()(text[:512])[0]
        label = result["label"].lower()
        signed = result["score"] if "pos" in label else -result["score"]
        if "neu" in label:
            signed = 0.0
        return max(-1.0, min(1.0, signed))


def rolling_sentiment_z(
    today_mean: float, history_means: list[float], window: int = MIN_Z_WINDOW
) -> float | None:
    """Within-ticker rolling z-score of the daily mean raw score.

    Returns None until at least ``window`` (>= 60 per contract) days of
    history exist, or when the history is degenerate (zero variance).
    """
    if window < MIN_Z_WINDOW:
        raise ValueError(f"window must be >= {MIN_Z_WINDOW} trading days")
    if len(history_means) < window:
        return None
    trailing = history_means[-window:]
    stdev = statistics.pstdev(trailing)
    if stdev == 0:
        return None
    return (today_mean - statistics.fmean(trailing)) / stdev


__all__ = [
    "SentimentScorer",
    "LexiconScorer",
    "TransformersScorer",
    "rolling_sentiment_z",
    "DEFAULT_MODEL_IDS",
    "MIN_Z_WINDOW",
]
