"""MarketStats from MarketBar history + MarketConfig (sections 0 and 1.2).

Rules enforced here:

* Halts/suspensions produce explicit gaps: a session date with no bar yields
  ``suspended=True`` with ``None`` prices -- never a forward-filled price.
* Limit-hit detection and distance-to-limit use the market's price-limit band
  (per-instrument override first, then the board band for CN, the uniform
  band for KR; None for the US).
* All returns are computed in local currency from the bars as stored.
"""

from __future__ import annotations

import math
import statistics
from datetime import date

from ..market_config import MarketConfig
from ..schemas import MarketBar, MarketStats
from ..universe import Instrument

RV_WINDOW = 20
DRAWDOWN_WINDOW = 60
# Tolerance for float comparison against the limit band (e.g. 9.98% counts
# as a hit of a 10% band; exchange rounding makes exact equality unreliable).
LIMIT_EPSILON = 0.002


def price_limit_band(market: MarketConfig, instrument: Instrument) -> float | None:
    """Fractional daily band for the instrument, or None (US)."""
    if instrument.price_limit_override is not None:
        return instrument.price_limit_override
    if not market.price_limit:
        return None
    if market.market_id == "CN":
        code = instrument.ticker.split(".", 1)[0]
        if code.startswith(("688", "300")):
            return market.price_limit.get("star_chinext", market.price_limit["main"])
        return market.price_limit["main"]
    if "all" in market.price_limit:
        return market.price_limit["all"]
    # Single-band configs regardless of key name.
    return next(iter(market.price_limit.values()))


def compute_market_stats(
    bars: list[MarketBar],
    on: date,
    market: MarketConfig,
    instrument: Instrument,
) -> MarketStats:
    """Stats for ``on`` from the instrument's bar history (ascending or not).

    ``bars`` may contain history beyond ``on``; anything after ``on`` is
    ignored (point-in-time discipline is the caller's responsibility for
    fetch timing; this guard keeps label leakage out regardless).
    """
    history = sorted(
        (b for b in bars if b.date_local <= on), key=lambda b: b.date_local
    )
    today = next((b for b in history if b.date_local == on), None)
    if today is None:
        # Explicit gap record: suspended session, never forward-filled.
        return MarketStats(suspended=True)

    closes = [b.close for b in history]
    stats = MarketStats(close=today.close)

    prev = history[-2] if len(history) >= 2 else None
    band = price_limit_band(market, instrument)
    if prev is not None and prev.close > 0:
        ret_1d = today.close / prev.close - 1.0
        stats.ret_1d = ret_1d
        if band is not None:
            upper = prev.close * (1.0 + band)
            lower = prev.close * (1.0 - band)
            stats.limit_hit = abs(ret_1d) >= band - LIMIT_EPSILON
            stats.dist_to_upper_limit = (upper - today.close) / prev.close
            stats.dist_to_lower_limit = (today.close - lower) / prev.close

    if len(closes) >= RV_WINDOW + 1:
        window = closes[-(RV_WINDOW + 1) :]
        log_returns = [
            math.log(b / a) for a, b in zip(window, window[1:]) if a > 0 and b > 0
        ]
        if len(log_returns) >= 2:
            stats.rv_20d = statistics.pstdev(log_returns)

    tail = closes[-DRAWDOWN_WINDOW:]
    peak = max(tail)
    if peak > 0:
        stats.drawdown_60d = today.close / peak - 1.0

    return stats


__all__ = ["compute_market_stats", "price_limit_band", "RV_WINDOW", "DRAWDOWN_WINDOW"]
