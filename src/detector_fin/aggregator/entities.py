"""Entity resolution: mention -> local ticker (section 1.2).

Resolution is conservative and precision-first:

1. ``ticker_hints`` set by the fetcher adapters are trusted directly.
2. The item text is scanned for exact universe signals: cashtags (``$NVDA``),
   bare US symbols, 6-digit CN/KR codes, suffixed tickers, and English names.

Cross-listings: an ADR and its local line are DISTINCT tickers that share an
``entity_id``. Until the universe carries explicit entity links, the entity id
is derived deterministically from ``name_en`` so both lines of a future
cross-listing can be pointed at the same slug.
"""

from __future__ import annotations

import re
from collections import defaultdict

from ..schemas import RawItem
from ..universe import Instrument


def entity_id_for(instrument: Instrument) -> str:
    """Deterministic entity id: slugified English name."""
    slug = re.sub(r"[^a-z0-9]+", "-", instrument.name_en.lower()).strip("-")
    return slug or instrument.ticker.lower()


def _signals(instrument: Instrument) -> list[re.Pattern[str]]:
    code = instrument.ticker.split(".", 1)[0]
    patterns = [
        re.escape(instrument.ticker),  # suffixed ticker, e.g. 600519.SS
        rf"\${re.escape(code)}\b",  # cashtag, e.g. $NVDA
        re.escape(instrument.name_en),  # English name
    ]
    if code.isdigit():
        patterns.append(rf"(?<!\d){code}(?!\d)")  # bare CN/KR 6-digit code
    else:
        patterns.append(rf"\b{re.escape(code)}\b")  # bare US symbol
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def resolve_items(
    items: list[RawItem], instruments: list[Instrument]
) -> dict[str, list[RawItem]]:
    """Map each instrument ticker to the items that mention it.

    An item may resolve to several instruments; items resolving to none are
    dropped (never guessed onto a ticker).
    """
    compiled = {inst.ticker: _signals(inst) for inst in instruments}
    known = set(compiled)
    resolved: dict[str, list[RawItem]] = defaultdict(list)
    for item in items:
        matched = {hint for hint in item.ticker_hints if hint in known}
        for ticker, patterns in compiled.items():
            if ticker in matched:
                continue
            if any(p.search(item.text) for p in patterns):
                matched.add(ticker)
        for ticker in matched:
            resolved[ticker].append(item)
    return dict(resolved)


__all__ = ["resolve_items", "entity_id_for"]
