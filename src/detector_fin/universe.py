"""Universe registry: the instruments the pipeline tracks (section 0).

Instruments live in ``config/universe.yaml``. Each entry names a ticker, its
English name, its market, and its ``instrument_type`` (equity or ETF). ETFs
carry a distinct risk regime -- in particular CN ETFs sit under a 10% daily
price limit while cross-border (QDII) ETFs may differ -- so a per-instrument
``price_limit_override`` is allowed to state the limit band explicitly when it
deviates from the market default.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .schemas import InstrumentType, MarketId

DEFAULT_UNIVERSE_PATH = Path(__file__).resolve().parents[2] / "config" / "universe.yaml"


class Instrument(BaseModel):
    """One tracked instrument in the universe registry."""

    model_config = ConfigDict(extra="forbid")

    ticker: str
    name_en: str
    market_id: MarketId
    instrument_type: InstrumentType
    # Fractional daily price-limit band overriding the market default for this
    # instrument (e.g. a cross-border ETF differing from the local regime).
    price_limit_override: float | None = Field(default=None, gt=0.0)


class UniverseError(Exception):
    """Raised when the universe file is missing or invalid."""


def load_universe(path: Path | str | None = None) -> list[Instrument]:
    """Load and validate every instrument in the universe file."""
    path = Path(path) if path is not None else DEFAULT_UNIVERSE_PATH
    if not path.exists():
        raise UniverseError(f"universe file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    entries = raw.get("instruments", raw if isinstance(raw, list) else [])
    if not entries:
        raise UniverseError(f"universe file has no instruments: {path}")
    try:
        instruments = [Instrument.model_validate(e) for e in entries]
    except Exception as exc:
        raise UniverseError(f"invalid universe entry in {path}: {exc}") from exc
    seen: set[str] = set()
    for inst in instruments:
        if inst.ticker in seen:
            raise UniverseError(f"duplicate ticker in universe: {inst.ticker}")
        seen.add(inst.ticker)
    return instruments


def universe_for_market(
    market_id: str, path: Path | str | None = None
) -> list[Instrument]:
    """Return only the instruments belonging to ``market_id``."""
    mid = market_id.strip().upper()
    return [inst for inst in load_universe(path) if inst.market_id == mid]


__all__ = [
    "Instrument",
    "UniverseError",
    "DEFAULT_UNIVERSE_PATH",
    "load_universe",
    "universe_for_market",
]
