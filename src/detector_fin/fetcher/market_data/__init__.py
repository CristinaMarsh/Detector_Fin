"""Market-data adapters, one per market (Milestone M2).

Each adapter covers both equities and ETFs for its market:
    US -> yfinance, CN -> akshare, KR -> pykrx.
"""

from __future__ import annotations

from .cn_akshare import AkshareAdapter
from .kr_pykrx import PykrxAdapter
from .us_yfinance import YFinanceAdapter

# Registry keyed by market_id, consumed by the fetch_bars CLI.
ADAPTERS = {
    "US": YFinanceAdapter,
    "CN": AkshareAdapter,
    "KR": PykrxAdapter,
}

__all__ = ["YFinanceAdapter", "AkshareAdapter", "PykrxAdapter", "ADAPTERS"]
