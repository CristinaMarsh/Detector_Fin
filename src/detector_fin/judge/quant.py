"""Deterministic quant risk score over TickerDaySnapshots (section 1.3).

Inputs are snapshots ONLY -- today's plus a trailing history of the same
ticker's snapshots for percentile/vol context. Every component is a value in
[0, 1] with a fixed weight; the final score is the weight-normalised mean of
the components that are computable, so missing history degrades coverage,
never fabricates a number. The component breakdown is persisted in
``RiskScore.components`` for reconcilability with the LLM path.

``include_text=False`` produces the section-4 market-only baseline: identical
computation with the text-derived components (sentiment, burst) excluded, and
a distinct method_version so stored scores are never confused.
"""

from __future__ import annotations

import statistics

from ..schemas import RiskScore, TickerDaySnapshot

METHOD_VERSION = "quant-0.1"
MARKET_ONLY_VERSION = "quant-0.1-market-only"

# 99% one-sided normal quantile for parametric VaR from daily log-vol.
Z_99 = 2.326

# Fixed component weights (renormalised over computable components).
WEIGHTS: dict[str, float] = {
    "rv_percentile": 0.20,
    "var_99": 0.10,
    "hist_es": 0.10,
    "drawdown": 0.15,
    "dist_to_limit": 0.10,
    "limit_hit": 0.10,
    "suspended": 0.10,
    "sentiment": 0.10,
    "burst": 0.05,
}
TEXT_COMPONENTS = {"sentiment", "burst"}

MIN_RV_HISTORY = 10
MIN_RET_HISTORY = 40
ES_TAIL_FRACTION = 0.05


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _percentile_rank(value: float, history: list[float]) -> float:
    below = sum(1 for h in history if h <= value)
    return below / len(history)


def _components(
    snapshot: TickerDaySnapshot,
    history: list[TickerDaySnapshot],
    drawdown_threshold: float,
    include_text: bool,
) -> dict[str, float]:
    m = snapshot.market
    comps: dict[str, float] = {}

    rv_history = [s.market.rv_20d for s in history if s.market.rv_20d is not None]
    if m.rv_20d is not None and len(rv_history) >= MIN_RV_HISTORY:
        comps["rv_percentile"] = _percentile_rank(m.rv_20d, rv_history)

    if m.rv_20d is not None:
        # Parametric daily 99% VaR, normalised by the drawdown threshold.
        comps["var_99"] = _clip01(Z_99 * m.rv_20d / drawdown_threshold)

    returns = [s.market.ret_1d for s in history if s.market.ret_1d is not None]
    if len(returns) >= MIN_RET_HISTORY:
        tail_n = max(1, int(len(returns) * ES_TAIL_FRACTION))
        worst = sorted(returns)[:tail_n]
        expected_shortfall = -statistics.fmean(worst)
        if expected_shortfall > 0:
            comps["hist_es"] = _clip01(expected_shortfall / drawdown_threshold)

    if m.drawdown_60d is not None and m.drawdown_60d < 0:
        comps["drawdown"] = _clip01(-m.drawdown_60d / drawdown_threshold)

    if m.dist_to_upper_limit is not None and m.dist_to_lower_limit is not None:
        band = (m.dist_to_upper_limit + m.dist_to_lower_limit) / 2.0
        if band > 0:
            nearest = min(m.dist_to_upper_limit, m.dist_to_lower_limit)
            comps["dist_to_limit"] = _clip01(1.0 - nearest / band)

    comps["limit_hit"] = 1.0 if m.limit_hit else 0.0
    comps["suspended"] = 1.0 if m.suspended else 0.0

    if include_text:
        if snapshot.sentiment_z is not None:
            # Risk rises with strongly negative sentiment; positive is neutral.
            comps["sentiment"] = _clip01(-snapshot.sentiment_z / 3.0)
        if snapshot.burst_score is not None:
            # 1x trailing volume is neutral; 5x saturates the component.
            comps["burst"] = _clip01((snapshot.burst_score - 1.0) / 4.0)

    return comps


def score_snapshot(
    snapshot: TickerDaySnapshot,
    history: list[TickerDaySnapshot],
    *,
    drawdown_threshold: float = 0.10,
    include_text: bool = True,
) -> RiskScore:
    """Score one snapshot given the ticker's trailing snapshot history.

    ``drawdown_threshold`` is MarketConfig.label_params.d, keeping all
    thresholds config-driven per section 1.3.
    """
    comps = _components(snapshot, history, drawdown_threshold, include_text)
    weighted = {k: v for k, v in comps.items() if k in WEIGHTS}
    total_weight = sum(WEIGHTS[k] for k in weighted)
    score = (
        sum(WEIGHTS[k] * v for k, v in weighted.items()) / total_weight
        if total_weight > 0
        else 0.0
    )
    return RiskScore(
        ticker=snapshot.ticker,
        market_id=snapshot.market_id,
        instrument_type=snapshot.instrument_type,
        date_local=snapshot.date_local,
        score=_clip01(score),
        components=comps,
        method_version=METHOD_VERSION if include_text else MARKET_ONLY_VERSION,
    )


__all__ = [
    "score_snapshot",
    "METHOD_VERSION",
    "MARKET_ONLY_VERSION",
    "WEIGHTS",
    "TEXT_COMPONENTS",
]
