"""Tests for sentiment scorers and the rolling z-score guardrails."""

from __future__ import annotations

import pytest

from detector_fin.aggregator.sentiment import (
    DEFAULT_MODEL_IDS,
    MIN_Z_WINDOW,
    LexiconScorer,
    SentimentScorer,
    rolling_sentiment_z,
)


def test_lexicon_scorer_polarity_per_language():
    scorer = LexiconScorer()
    assert scorer.score("record profit and growth", "en") > 0
    assert scorer.score("fraud lawsuit and loss", "en") < 0
    assert scorer.score("利好 超预期 大涨", "zh") > 0
    assert scorer.score("跌停 亏损", "zh") < 0
    assert scorer.score("호실적 상승", "ko") > 0
    assert scorer.score("nothing polar here", "en") == 0.0


def test_lexicon_scorer_bounds_and_version():
    scorer = LexiconScorer()
    assert isinstance(scorer, SentimentScorer)
    assert -1.0 <= scorer.score("profit loss profit", "en") <= 1.0
    assert scorer.model_version == "baseline-lexicon-0.1"


def test_zh_production_model_requires_explicit_pin():
    # No default zh model id: configuring one is a deliberate act, never a guess.
    assert DEFAULT_MODEL_IDS["zh"] is None
    assert DEFAULT_MODEL_IDS["en"] == "ProsusAI/finbert"
    assert DEFAULT_MODEL_IDS["ko"] == "snunlp/KR-FinBert-SC"


def test_rolling_z_requires_sixty_days():
    assert rolling_sentiment_z(0.5, [0.1] * 59) is None
    with pytest.raises(ValueError):
        rolling_sentiment_z(0.5, [0.1] * 90, window=30)


def test_rolling_z_computation_and_degenerate_history():
    history = [0.0] * 59 + [1.0]
    z = rolling_sentiment_z(1.0, history)
    assert z is not None and z > 0
    # Zero-variance history cannot be standardised.
    assert rolling_sentiment_z(0.5, [0.2] * MIN_Z_WINDOW) is None
