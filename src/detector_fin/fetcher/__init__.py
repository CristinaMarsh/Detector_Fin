"""Fetcher package: pluggable source adapters (Design Contract section 1.1)."""

from __future__ import annotations

from .base import (
    BaseMarketDataAdapter,
    MarketDataAdapter,
    cn_code_to_ticker,
    filter_to_sessions,
    sessions_between,
    to_source_code,
    utc_now,
)

__all__ = [
    "MarketDataAdapter",
    "BaseMarketDataAdapter",
    "utc_now",
    "sessions_between",
    "filter_to_sessions",
    "to_source_code",
    "cn_code_to_ticker",
]
