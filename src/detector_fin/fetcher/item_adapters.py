"""Shared template for adapters that emit RawItem streams (section 1.1).

Disclosure adapters (M3a) and sentiment adapters (M3b) share the same
contract guarantees, enforced once here:

* Fetcher does NO interpretation: fidelity, language tag, timestamps only.
* Graceful degradation: a per-instrument fetch failure yields an empty batch
  for that instrument, never a pipeline crash.
* ``since`` filtering on ``event_time`` and a single UTC ``observed_at``
  stamp per run.
* Instruments an adapter cannot serve (missing identifier, missing API key)
  are skipped, never guessed.

Network access lives exclusively in ``_fetch_raw``; tests drive
``_transform`` with recorded fixture payloads and stub ``_fetch_raw`` for
end-to-end runs.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone

from ..market_config import MarketConfig
from ..schemas import RawItem
from ..universe import Instrument

USER_AGENT_FALLBACK = "Detector_Fin/0.3 (research pipeline)"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_author(name: str) -> str:
    """Stable pseudonymous author id; raw usernames never enter storage."""
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


def http_get_json(
    url: str, headers: dict[str, str] | None = None, timeout: float = 30.0
) -> dict:
    """Small stdlib JSON GET helper so adapters need no extra dependency."""
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def http_get_text(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    encoding: str = "utf-8",
) -> str:
    """Stdlib text GET helper for HTML board pages (e.g. EUC-KR encoded)."""
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode(encoding, errors="replace")


class BaseItemAdapter:
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

    def _fetch_raw(self, instrument: Instrument, market: MarketConfig, since: datetime):
        raise NotImplementedError

    def _transform(
        self,
        instrument: Instrument,
        payload,
        market: MarketConfig,
        observed_at: datetime,
    ) -> list[RawItem]:
        raise NotImplementedError


__all__ = [
    "BaseItemAdapter",
    "hash_author",
    "http_get_json",
    "http_get_text",
    "utc_now",
    "USER_AGENT_FALLBACK",
]
