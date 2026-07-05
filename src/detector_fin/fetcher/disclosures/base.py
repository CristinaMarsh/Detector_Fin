"""Disclosure source adapters: official filings as RawItem streams (M3a).

A disclosure adapter turns a market + instruments into
:class:`~detector_fin.schemas.RawItem` records describing official filings
(annual/quarterly reports, material-event notices). Contract guarantees
enforced here:

* Fetcher does NO interpretation: items carry filing metadata (form type,
  title) and timestamps only.
* Item URLs point at the official disclosure documents and propagate verbatim
  downstream (Design Contract section 3 provenance rule).
* Graceful degradation: a per-instrument fetch failure yields an empty batch
  for that instrument, never a pipeline crash (section 1.1).
* Instruments lacking a required source identifier (EDGAR CIK, DART
  corp_code) are skipped, never guessed.

Network access lives exclusively in ``_fetch_raw``; tests drive ``_transform``
with recorded fixture payloads and stub ``_fetch_raw`` for end-to-end runs.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

from ...market_config import MarketConfig
from ...schemas import RawItem
from ...universe import Instrument

USER_AGENT_FALLBACK = "Detector_Fin/0.3 (research pipeline)"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def http_get_json(
    url: str, headers: dict[str, str] | None = None, timeout: float = 30.0
) -> dict:
    """Small stdlib JSON GET helper so adapters need no extra dependency."""
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class BaseDisclosureAdapter:
    """Template adapter: fetch raw payload per instrument, transform, filter."""

    name: str = "base"

    def fetch_items(
        self,
        market: MarketConfig,
        instruments: list[Instrument],
        since: datetime,
        observed_at: datetime | None = None,
    ) -> list[RawItem]:
        if since.tzinfo is None:
            raise ValueError("since must be timezone-aware (UTC)")
        stamp = observed_at or utc_now()
        items: list[RawItem] = []
        for instrument in instruments:
            if not self._supports(instrument):
                continue
            try:
                payload = self._fetch_raw(instrument, market, since)
            except Exception:
                # Degrade gracefully to an empty batch for this instrument.
                continue
            items.extend(
                item
                for item in self._transform(instrument, payload, market, stamp)
                if item.event_time >= since
            )
        return items

    def _supports(self, instrument: Instrument) -> bool:
        """Whether this adapter has what it needs for the instrument."""
        return True

    def _fetch_raw(
        self, instrument: Instrument, market: MarketConfig, since: datetime
    ) -> dict:
        raise NotImplementedError

    def _transform(
        self,
        instrument: Instrument,
        payload: dict,
        market: MarketConfig,
        observed_at: datetime,
    ) -> list[RawItem]:
        raise NotImplementedError


__all__ = ["BaseDisclosureAdapter", "http_get_json", "utc_now", "USER_AGENT_FALLBACK"]
