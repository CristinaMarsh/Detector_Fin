"""Tests for the deterministic quant risk score."""

from __future__ import annotations

from datetime import date, timedelta

from detector_fin.judge import MARKET_ONLY_VERSION, METHOD_VERSION, score_snapshot
from detector_fin.schemas import MarketStats, TickerDaySnapshot


def _snap(day: date, **market_kwargs) -> TickerDaySnapshot:
    return TickerDaySnapshot(
        ticker="600519.SS",
        entity_id="kweichow-moutai",
        market_id="CN",
        date_local=day,
        market=MarketStats(**market_kwargs),
    )


def _history(n: int = 60, rv: float = 0.01, ret: float = 0.001):
    base = date(2026, 3, 2)
    return [
        _snap(base + timedelta(days=i), rv_20d=rv, ret_1d=ret, close=100.0)
        for i in range(n)
    ]


TODAY = date(2026, 6, 16)


def test_score_bounds_and_determinism():
    snap = _snap(TODAY, close=100.0, rv_20d=0.02, ret_1d=-0.05, drawdown_60d=-0.08)
    a = score_snapshot(snap, _history())
    b = score_snapshot(snap, _history())
    assert a.score == b.score  # deterministic
    assert 0.0 <= a.score <= 1.0
    assert a.method_version == METHOD_VERSION
    assert a.components  # breakdown persisted


def test_limit_hit_and_suspension_raise_score():
    calm = score_snapshot(_snap(TODAY, close=100.0, rv_20d=0.01), _history())
    hit = score_snapshot(
        _snap(TODAY, close=110.0, rv_20d=0.01, limit_hit=True), _history()
    )
    halted = score_snapshot(_snap(TODAY, suspended=True), _history())
    assert hit.score > calm.score
    assert halted.components["suspended"] == 1.0
    assert hit.components["limit_hit"] == 1.0


def test_rv_percentile_uses_history():
    spike = _snap(TODAY, close=100.0, rv_20d=0.05)
    scored = score_snapshot(spike, _history(rv=0.01))
    assert scored.components["rv_percentile"] == 1.0  # above all history


def test_negative_sentiment_raises_market_only_ignores():
    snap = TickerDaySnapshot(
        ticker="600519.SS",
        entity_id="kweichow-moutai",
        market_id="CN",
        date_local=TODAY,
        sentiment_z=-3.0,
        burst_score=5.0,
        market=MarketStats(close=100.0, rv_20d=0.01),
    )
    full = score_snapshot(snap, _history())
    market_only = score_snapshot(snap, _history(), include_text=False)
    assert full.components["sentiment"] == 1.0
    assert full.components["burst"] == 1.0
    assert "sentiment" not in market_only.components
    assert "burst" not in market_only.components
    assert market_only.method_version == MARKET_ONLY_VERSION
    assert full.score > market_only.score


def test_distance_to_limit_component():
    # Close sits right at the upper band: dist_up=0, dist_low=2*band.
    snap = _snap(
        TODAY,
        close=110.0,
        ret_1d=0.10,
        limit_hit=True,
        dist_to_upper_limit=0.0,
        dist_to_lower_limit=0.20,
    )
    scored = score_snapshot(snap, _history())
    assert scored.components["dist_to_limit"] == 1.0


def test_positive_sentiment_is_neutral_not_protective():
    happy = TickerDaySnapshot(
        ticker="600519.SS",
        entity_id="kweichow-moutai",
        market_id="CN",
        date_local=TODAY,
        sentiment_z=3.0,
        market=MarketStats(close=100.0, rv_20d=0.01),
    )
    scored = score_snapshot(happy, _history())
    assert scored.components["sentiment"] == 0.0


def test_no_history_degrades_components_not_score_validity():
    snap = _snap(TODAY, close=100.0, rv_20d=0.02)
    scored = score_snapshot(snap, [])
    assert "rv_percentile" not in scored.components  # needs history
    assert "hist_es" not in scored.components
    assert 0.0 <= scored.score <= 1.0
