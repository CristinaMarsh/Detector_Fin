"""Disclosure source adapters: official filings as RawItem streams (M3a).

The generic template (per-instrument graceful degradation, ``since``
filtering, UTC ``observed_at`` stamp, skip-not-guess) lives in
:mod:`detector_fin.fetcher.item_adapters` and is shared with the sentiment
adapters. Disclosure-specific guarantees on top of it:

* Items carry filing METADATA only (form type, title) and timestamps.
* Item URLs point at the official disclosure documents and propagate verbatim
  downstream (Design Contract section 3 provenance rule).
"""

from __future__ import annotations

from ..item_adapters import (
    USER_AGENT_FALLBACK,
    BaseItemAdapter,
    http_get_json,
    utc_now,
)


class BaseDisclosureAdapter(BaseItemAdapter):
    """Disclosure flavour of the shared RawItem adapter template."""

    name: str = "base"


__all__ = ["BaseDisclosureAdapter", "http_get_json", "utc_now", "USER_AGENT_FALLBACK"]
