"""Disclosure adapters, one per market (Milestone M3a).

Each adapter emits RawItem records for official filings:
    US -> SEC EDGAR, CN -> cninfo, KR -> DART.
"""

from __future__ import annotations

from .cn_cninfo import CninfoAdapter
from .kr_dart import DartAdapter
from .us_sec_edgar import SecEdgarAdapter

# Registry keyed by market_id, consumed by the fetch_disclosures CLI.
DISCLOSURE_ADAPTERS = {
    "US": SecEdgarAdapter,
    "CN": CninfoAdapter,
    "KR": DartAdapter,
}

__all__ = ["SecEdgarAdapter", "CninfoAdapter", "DartAdapter", "DISCLOSURE_ADAPTERS"]
