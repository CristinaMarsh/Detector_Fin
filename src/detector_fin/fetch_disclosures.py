"""CLI: fetch official disclosures for a market and append them to storage.

Usage::

    python -m detector_fin.fetch_disclosures --market US --since 2026-06-01

Loads the universe, selects the market's disclosure adapter, fetches filing
metadata for every instrument in that market, and appends the RawItem records
to the ``raw_items`` dataset of a :class:`~detector_fin.storage.ParquetStore`.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path

from .market_config import load_market_config
from .schemas import RawItem
from .storage import ParquetStore
from .universe import universe_for_market


def build_adapter(market_id: str):
    """Return the disclosure adapter instance registered for ``market_id``."""
    from .fetcher.disclosures import DISCLOSURE_ADAPTERS

    mid = market_id.strip().upper()
    try:
        return DISCLOSURE_ADAPTERS[mid]()
    except KeyError:
        raise SystemExit(f"no disclosure adapter for market {mid!r}")


def run(
    market_id: str,
    since: date,
    *,
    store_root: Path | str,
    config_dir: Path | str | None = None,
    universe_path: Path | str | None = None,
    adapter=None,
    observed_at: datetime | None = None,
) -> list[RawItem]:
    """Fetch disclosures for one market and append them to the store."""
    market = load_market_config(market_id, config_dir)
    instruments = universe_for_market(market_id, universe_path)
    adapter = adapter or build_adapter(market.market_id)
    since_utc = datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc)
    items = adapter.fetch_items(market, instruments, since_utc, observed_at=observed_at)
    ParquetStore(store_root).append("raw_items", items)
    return items


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m detector_fin.fetch_disclosures",
        description="Fetch official disclosures for a market and append to storage.",
    )
    parser.add_argument("--market", required=True, help="market id, e.g. US, CN, KR")
    parser.add_argument(
        "--since",
        required=True,
        type=date.fromisoformat,
        help="fetch filings on/after this date (YYYY-MM-DD, UTC)",
    )
    parser.add_argument(
        "--store", default="data", help="ParquetStore root directory (default: data)"
    )
    parser.add_argument("--config-dir", default=None, help="market config directory")
    parser.add_argument("--universe", default=None, help="universe.yaml path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    items = run(
        args.market,
        args.since,
        store_root=args.store,
        config_dir=args.config_dir,
        universe_path=args.universe,
    )
    print(
        f"Fetched and stored {len(items)} disclosure items for market "
        f"{args.market.upper()} since {args.since.isoformat()}."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
