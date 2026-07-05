"""CLI: build TickerDaySnapshots for a market and local trading date.

Usage::

    python -m detector_fin.build_snapshots --market CN --date 2026-06-16

Reads the ``raw_items`` and ``bars`` datasets, resolves items to universe
tickers, builds one snapshot per instrument, and appends them to the
``snapshots`` dataset. The temporal cutoff (observed_at strictly before the
market's decision instant) is enforced inside the builder.

Sentiment/burst rolling histories are assembled by the M5 evaluation harness;
snapshots built by this CLI carry ``sentiment_z=None`` / ``burst_score=None``
until then, which is the honest value for missing history.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .aggregator import LexiconScorer, build_snapshot, resolve_items
from .market_config import load_market_config
from .schemas import MarketBar, RawItem, TickerDaySnapshot
from .storage import ParquetStore
from .universe import universe_for_market


def run(
    market_id: str,
    date_local: date,
    *,
    store_root: Path | str,
    config_dir: Path | str | None = None,
    universe_path: Path | str | None = None,
    scorer=None,
    translator=None,
) -> list[TickerDaySnapshot]:
    market = load_market_config(market_id, config_dir)
    instruments = universe_for_market(market_id, universe_path)
    store = ParquetStore(store_root)
    scorer = scorer or LexiconScorer()

    items = store.read("raw_items", RawItem, market_id=market.market_id)
    bars = store.read("bars", MarketBar, market_id=market.market_id)
    resolved = resolve_items(items, instruments)
    bars_by_ticker: dict[str, list[MarketBar]] = {}
    for bar in bars:
        bars_by_ticker.setdefault(bar.ticker, []).append(bar)

    snapshots = [
        build_snapshot(
            ticker=inst.ticker,
            date_local=date_local,
            items=resolved.get(inst.ticker, []),
            bars=bars_by_ticker.get(inst.ticker, []),
            market=market,
            instrument=inst,
            scorer=scorer,
            translator=translator,
        )
        for inst in instruments
    ]
    store.append("snapshots", snapshots)
    return snapshots


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m detector_fin.build_snapshots",
        description="Build per-ticker snapshots for a market and local date.",
    )
    parser.add_argument("--market", required=True, help="market id, e.g. US, CN, KR")
    parser.add_argument(
        "--date",
        required=True,
        type=date.fromisoformat,
        help="local trading date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--store", default="data", help="ParquetStore root directory (default: data)"
    )
    parser.add_argument("--config-dir", default=None, help="market config directory")
    parser.add_argument("--universe", default=None, help="universe.yaml path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    snapshots = run(
        args.market,
        args.date,
        store_root=args.store,
        config_dir=args.config_dir,
        universe_path=args.universe,
    )
    print(
        f"Built and stored {len(snapshots)} snapshots for market "
        f"{args.market.upper()} on {args.date.isoformat()}."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
