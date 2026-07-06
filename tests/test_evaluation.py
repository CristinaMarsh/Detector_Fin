"""Tests for the evaluation protocol: labels, metrics, DM test, splits."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from detector_fin.evaluation import (
    auc,
    brier,
    diebold_mariano,
    forward_label,
    persistence_forecast,
    skill_score,
    walk_forward_splits,
)
from detector_fin.market_config import load_market_config
from detector_fin.schemas import MarketStats, TickerDaySnapshot

CN = load_market_config("CN")
US = load_market_config("US")


def _series(n: int, market_id: str = "CN", **defaults) -> list[TickerDaySnapshot]:
    base = date(2026, 1, 5)
    stats = dict(close=100.0, rv_20d=0.01, ret_1d=0.001, drawdown_60d=-0.01)
    stats.update(defaults)
    return [
        TickerDaySnapshot(
            ticker="T",
            entity_id="t",
            market_id=market_id,
            date_local=base + timedelta(days=i),
            market=MarketStats(**stats),
        )
        for i in range(n)
    ]


def _set(series, index, **kwargs):
    m = series[index].market.model_copy(update=kwargs)
    series[index] = series[index].model_copy(update={"market": m})


def test_label_limit_hit_within_horizon():
    series = _series(40)
    _set(series, 32, limit_hit=True)  # within k=5 of index 30
    assert forward_label(series, 30, CN) == 1
    assert forward_label(series, 20, CN) == 0


def test_label_drawdown_trigger():
    series = _series(40)
    _set(series, 33, drawdown_60d=-0.15)  # beyond d=0.10
    assert forward_label(series, 30, CN) == 1


def test_label_suspension_start_only():
    series = _series(40)
    for i in (31, 32):
        _set(series, i, suspended=True)
    assert forward_label(series, 30, CN) == 1  # start at 31
    # From index 26, window 27..31: suspension starts inside -> also 1;
    # but a window fully inside an ongoing suspension is no new event.
    for i in range(27, 40):
        _set(series, i, suspended=True)
    assert forward_label(series, 30, CN) == 0


def test_return_jump_censored_under_limits():
    cn = _series(40, market_id="CN")
    us = _series(40, market_id="US")
    # Alternate small returns so trailing sigma is positive (~0.005).
    for i in range(30):
        wobble = 0.005 if i % 2 == 0 else -0.005
        _set(cn, i, ret_1d=wobble)
        _set(us, i, ret_1d=wobble)
    _set(cn, 32, ret_1d=0.08)  # huge jump, but CN has price limits: censored
    _set(us, 32, ret_1d=0.08)  # same jump in the limit-free market: triggers
    assert forward_label(cn, 30, CN) == 0
    assert forward_label(us, 30, US) == 1


def test_label_right_censored_tail_is_none():
    series = _series(10)
    assert forward_label(series, 8, CN) is None  # fewer than k forward days


def test_auc_perfect_and_uninformative():
    assert auc([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]) == 1.0
    assert auc([1, 0], [0.5, 0.5]) == 0.5
    assert auc([1, 1], [0.5, 0.6]) is None  # one class absent


def test_brier_and_skill():
    assert brier([1, 0], [1.0, 0.0]) == 0.0
    assert brier([1, 0], [0.0, 1.0]) == 1.0
    assert skill_score(0.1, 0.2) == pytest.approx(0.5)
    assert skill_score(0.1, 0.0) is None


def test_persistence_forecast_shifts_labels():
    labels = [0, 1, 1, 0]
    forecast = persistence_forecast(labels)
    assert forecast[1:] == [0.0, 1.0, 1.0]
    assert 0.0 <= forecast[0] <= 1.0  # base rate for day one


def test_diebold_mariano_degenerate_and_directional():
    same = [0.1] * 30
    assert diebold_mariano(same, same) is None  # identical losses: no verdict

    worse = [0.3] * 15 + [0.31] * 15
    better = [0.1] * 15 + [0.11] * 15
    result = diebold_mariano(worse, better)
    assert result is not None
    stat, p = result
    assert stat > 0  # first series has higher loss
    assert p < 0.05


def test_walk_forward_splits_chronological():
    splits = walk_forward_splits(100, train_min=60, test_size=20)
    assert [(s.start, s.stop) for _, s in splits] == [(60, 80), (80, 100)]
    for train, test in splits:
        assert max(train) < min(test)  # never trains on the future
    with pytest.raises(ValueError):
        walk_forward_splits(10, train_min=0, test_size=5)
