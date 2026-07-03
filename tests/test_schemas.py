"""Tests for the authoritative schemas (section 2)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from detector_fin.schemas import (
    MAX_FRAGMENTS,
    EvidenceDossier,
    Fragment,
    MarketStats,
    RawItem,
    RiskScore,
    TickerDaySnapshot,
)


def _raw(**overrides) -> RawItem:
    base = dict(
        id="itm-1",
        source="stocktwits",
        market_id="US",
        lang="en",
        ticker_hints=["AAPL"],
        text="some text",
        event_time=datetime(2026, 1, 2, 13, 0, tzinfo=timezone.utc),
        observed_at=datetime(2026, 1, 2, 13, 5, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return RawItem(**base)


def test_rawitem_roundtrip_and_partition():
    item = _raw()
    assert item.market_id == "US"
    assert item.partition_keys() == ("US", date(2026, 1, 2))
    assert item.record_key() == "itm-1"
    # JSON round-trip preserves UTC instants.
    again = RawItem.model_validate_json(item.model_dump_json())
    assert again == item


def test_market_id_is_upper_cased():
    item = _raw(market_id="us")
    assert item.market_id == "US"


def test_naive_datetime_rejected():
    with pytest.raises(ValidationError):
        _raw(observed_at=datetime(2026, 1, 2, 13, 5))  # no tzinfo


def test_non_utc_datetime_normalised_to_utc():
    from zoneinfo import ZoneInfo

    ny = datetime(2026, 1, 2, 8, 5, tzinfo=ZoneInfo("America/New_York"))
    item = _raw(observed_at=ny)
    assert item.observed_at.tzinfo == timezone.utc
    assert item.observed_at == ny  # same instant, different representation


def test_invalid_lang_rejected():
    with pytest.raises(ValidationError):
        _raw(lang="fr")


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        _raw(unexpected="nope")


def test_snapshot_partition_uses_local_date():
    snap = TickerDaySnapshot(
        ticker="600519.SS",
        entity_id="kweichow-moutai",
        market_id="CN",
        date_local=date(2026, 1, 5),
        market=MarketStats(close=1700.0, limit_hit=True, dist_to_upper_limit=0.0),
    )
    assert snap.partition_keys() == ("CN", date(2026, 1, 5))
    assert snap.record_key() == "600519.SS"
    assert snap.market.limit_hit is True


def test_fragment_length_cap():
    with pytest.raises(ValidationError):
        Fragment(lang="en", original="x" * 281, en="ok")


def test_top_fragments_capped():
    frags = [Fragment(lang="en", original=f"f{i}", en=f"f{i}") for i in range(MAX_FRAGMENTS + 1)]
    with pytest.raises(ValidationError):
        TickerDaySnapshot(
            ticker="AAPL",
            entity_id="apple",
            market_id="US",
            date_local=date(2026, 1, 2),
            top_fragments=frags,
        )


def test_fragments_default_untrusted():
    f = Fragment(lang="zh", original="利好", en="good news")
    assert f.untrusted is True


def test_riskscore_bounds():
    RiskScore(
        ticker="AAPL",
        market_id="US",
        date_local=date(2026, 1, 2),
        score=0.5,
        components={"rv": 0.4, "sentiment": 0.1},
        method_version="quant-0.1",
    )
    with pytest.raises(ValidationError):
        RiskScore(
            ticker="AAPL",
            market_id="US",
            date_local=date(2026, 1, 2),
            score=1.5,
            method_version="quant-0.1",
        )


def test_evidence_dossier_roundtrip():
    dossier = EvidenceDossier(
        ticker="AAPL",
        market_id="US",
        date_local=date(2026, 1, 2),
        summary_claims=["earnings beat"],
        supporting_counts={"news": 3},
        uncertainty_notes=["thin coverage"],
        contrarian_case="guidance was soft",
        model_version="llm-0.1",
        prompt_hash="abc123",
    )
    again = EvidenceDossier.model_validate_json(dossier.model_dump_json())
    assert again == dossier
