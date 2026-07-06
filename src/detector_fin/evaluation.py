"""Evaluation protocol: labels, metrics, baselines, splits (section 4).

Risk judgment is framed as event prediction. The forward label L(t, k) is 1
if within the next k trading days the ticker experiences ANY of: (a) realized
volatility above its trailing 95th percentile, (b) drawdown beyond d,
(c) absolute return jump > j sigma (limit-free markets only; censored under
price limits), (d) a limit-hit day, (e) a suspension start.

Everything here is deterministic and dependency-free: rank-based AUC, Brier
score, skill vs a persistence baseline, a Diebold-Mariano test with a
Newey-West variance (h = k lags), and chronological walk-forward splits --
never random shuffles.
"""

from __future__ import annotations

import math
import statistics

from .market_config import LabelParams, MarketConfig
from .schemas import TickerDaySnapshot


# -- forward labels ----------------------------------------------------------


def forward_label(
    snapshots: list[TickerDaySnapshot],
    index: int,
    market: MarketConfig,
    params: LabelParams | None = None,
) -> int | None:
    """L(t, k) for ``snapshots[index]`` over the ordered per-ticker series.

    Returns None when fewer than k forward snapshots exist (right-censored
    tail: unknown, never assumed 0).
    """
    params = params or market.label_params
    k = params.k
    window = snapshots[index + 1 : index + 1 + k]
    if len(window) < k:
        return None

    past = snapshots[: index + 1]
    rv_past = [s.market.rv_20d for s in past if s.market.rv_20d is not None]
    rv_p95 = _percentile(rv_past, 0.95) if len(rv_past) >= 20 else None
    ret_past = [s.market.ret_1d for s in past if s.market.ret_1d is not None]
    sigma = statistics.pstdev(ret_past) if len(ret_past) >= 20 else None
    limit_free = not market.price_limit  # (c) censored under price limits

    prev_suspended = past[-1].market.suspended
    for snap in window:
        m = snap.market
        if rv_p95 is not None and m.rv_20d is not None and m.rv_20d > rv_p95:
            return 1  # (a)
        if m.drawdown_60d is not None and m.drawdown_60d <= -params.d:
            return 1  # (b)
        if (
            limit_free
            and sigma
            and m.ret_1d is not None
            and abs(m.ret_1d) > params.j * sigma
        ):
            return 1  # (c)
        if params.limit_hit_is_event and m.limit_hit:
            return 1  # (d)
        if params.suspension_is_event and m.suspended and not prev_suspended:
            return 1  # (e) suspension START
        prev_suspended = m.suspended
    return 0


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


# -- metrics -------------------------------------------------------------------


def auc(labels: list[int], scores: list[float]) -> float | None:
    """Rank-based AUC (Mann-Whitney). None when one class is absent."""
    positives = [s for y, s in zip(labels, scores) if y == 1]
    negatives = [s for y, s in zip(labels, scores) if y == 0]
    if not positives or not negatives:
        return None
    wins = 0.0
    for p in positives:
        for n in negatives:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def brier(labels: list[int], probs: list[float]) -> float:
    return statistics.fmean((p - y) ** 2 for y, p in zip(labels, probs))


def skill_score(model_brier: float, baseline_brier: float) -> float | None:
    """1 - Brier_model / Brier_baseline; None if the baseline is perfect."""
    if baseline_brier == 0:
        return None
    return 1.0 - model_brier / baseline_brier


def persistence_forecast(labels: list[int]) -> list[float]:
    """Baseline: probability = yesterday's label (base rate for day one)."""
    if not labels:
        return []
    base_rate = statistics.fmean(labels)
    return [base_rate] + [float(y) for y in labels[:-1]]


def diebold_mariano(
    losses_a: list[float], losses_b: list[float], horizon: int = 1
) -> tuple[float, float] | None:
    """DM test on per-period loss differentials (two-sided, normal approx).

    Uses a Newey-West long-run variance with ``horizon - 1`` lags, the
    standard choice for k-step-ahead forecasts. Returns (statistic, p_value),
    or None when the differential is degenerate (identical losses).
    """
    n = len(losses_a)
    if n != len(losses_b) or n < 2:
        raise ValueError("loss series must be equal length with n >= 2")
    d = [a - b for a, b in zip(losses_a, losses_b)]
    mean_d = statistics.fmean(d)
    centred = [x - mean_d for x in d]
    gamma0 = statistics.fmean([x * x for x in centred])
    long_run = gamma0
    for lag in range(1, min(horizon, n)):
        cov = sum(centred[t] * centred[t - lag] for t in range(lag, n)) / n
        long_run += 2.0 * (1.0 - lag / horizon) * cov
    if long_run <= 0:
        return None
    stat = mean_d / math.sqrt(long_run / n)
    p_value = math.erfc(abs(stat) / math.sqrt(2.0))
    return stat, p_value


def walk_forward_splits(
    n: int, train_min: int, test_size: int
) -> list[tuple[range, range]]:
    """Chronological expanding-window splits -- never random shuffles."""
    if train_min <= 0 or test_size <= 0:
        raise ValueError("train_min and test_size must be positive")
    splits: list[tuple[range, range]] = []
    start = train_min
    while start + test_size <= n:
        splits.append((range(0, start), range(start, start + test_size)))
        start += test_size
    return splits


__all__ = [
    "forward_label",
    "auc",
    "brier",
    "skill_score",
    "persistence_forecast",
    "diebold_mariano",
    "walk_forward_splits",
]
