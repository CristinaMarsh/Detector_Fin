"""CLI: fetch daily market bars for a market and append them to storage.

Usage::

    python -m detector_fin.fetch_bars --market CN --since 2026-06-01

Loads the universe, selects the market's adapter, fetches bars for every
instrument in that market, and appends them to the ``bars`` dataset of a
:class:`~detector_fin.storage.ParquetStore`.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

from .market_config import load_market_config
from .schemas import MarketBar
from .storage import ParquetStore
from .universe import universe_for_market


def build_adapter(market_id: str):
    """Return the market-data adapter instance registered for ``market_id``."""
    # Imported lazily so the CLI module loads without the optional "fetch" deps
    # until an adapter is actually constructed and used.
    from .fetcher.market_data import ADAPTERS

    mid = market_id.strip().upper()
    try:
        return ADAPTERS[mid]()
    except KeyError:
        raise SystemExit(f"no market-data adapter for market {mid!r}")


def run(
    market_id: str,
    since: date,
    *,
    store_root: Path | str,
    config_dir: Path | str | None = None,
    universe_path: Path | str | None = None,
    adapter=None,
    observed_at: datetime | None = None,
) -> list[MarketBar]:
    """Fetch bars for one market and append them to the store. Returns the bars.

    ``adapter`` may be injected (e.g. a stub) for testing; otherwise the
    registered adapter for the market is used.
    """
    market = load_market_config(market_id, config_dir)
    instruments = universe_for_market(market_id, universe_path)
    adapter = adapter or build_adapter(market.market_id)
    bars = adapter.fetch_bars(market, instruments, since, observed_at=observed_at)
    ParquetStore(store_root).append("bars", bars)
    return bars


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m detector_fin.fetch_bars",
        description="Fetch daily market bars for a market and append to storage.",
    )
    parser.add_argument("--market", required=True, help="market id, e.g. US, CN, KR")
    parser.add_argument(
        "--since",
        required=True,
        type=date.fromisoformat,
        help="fetch bars on/after this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--store", default="data", help="ParquetStore root directory (default: data)"
    )
    parser.add_argument("--config-dir", default=None, help="market config directory")
    parser.add_argument("--universe", default=None, help="universe.yaml path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    bars = run(
        args.market,
        args.since,
        store_root=args.store,
        config_dir=args.config_dir,
        universe_path=args.universe,
    )
    print(
        f"Fetched and stored {len(bars)} bars for market {args.market.upper()} "
        f"since {args.since.isoformat()}."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
