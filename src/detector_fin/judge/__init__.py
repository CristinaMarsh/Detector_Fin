"""Judge: two independent paths over the same snapshot (section 1.3).

Quant path (this milestone): deterministic, rule and statistics based,
fully unit-testable. LLM path (M10b): evidence dossiers, never a verdict.
"""

from __future__ import annotations

from .quant import METHOD_VERSION, MARKET_ONLY_VERSION, score_snapshot

__all__ = ["score_snapshot", "METHOD_VERSION", "MARKET_ONLY_VERSION"]
