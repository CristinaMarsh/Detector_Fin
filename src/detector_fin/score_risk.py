"""CLI: score stored snapshots for a market and append RiskScore records.

Usage::

    python -m detector_fin.score_risk --market CN --date 2026-06-16

Reads the ``snapshots`` dataset, orders each ticker's history by local date,
scores the snapshot for the requested date against its trailing history, and
appends the results to the ``risk_scores`` dataset. Thresholds come from
MarketConfig.label_params. ``--market-only`` produces the section-4 baseline
variant (text components excluded, distinct method_version).
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
from pathlib import Path

from .judge import score_snapshot
from .market_config import load_market_config
from .schemas import RiskScore, TickerDaySnapshot
from .storage import ParquetStore


def run(
    market_id: str,
    date_local: date,
    *,
    store_root: Path | str,
    config_dir: Path | str | None = None,
    include_text: bool = True,
) -> list[RiskScore]:
    market = load_market_config(market_id, config_dir)
    store = ParquetStore(store_root)
    snapshots = store.read("snapshots", TickerDaySnapshot, market_id=market.market_id)

    by_ticker: dict[str, list[TickerDaySnapshot]] = defaultdict(list)
    for snap in snapshots:
        by_ticker[snap.ticker].append(snap)

    scores: list[RiskScore] = []
    for ticker, series in by_ticker.items():
        series.sort(key=lambda s: s.date_local)
        today = next((s for s in series if s.date_local == date_local), None)
        if today is None:
            continue  # no snapshot for the date: nothing to score, never invented
        history = [s for s in series if s.date_local < date_local]
        scores.append(
            score_snapshot(
                today,
                history,
                drawdown_threshold=market.label_params.d,
                include_text=include_text,
            )
        )
    store.append("risk_scores", scores)
    return scores


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m detector_fin.score_risk",
        description="Score stored snapshots and append RiskScore records.",
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
    parser.add_argument(
        "--market-only",
        action="store_true",
        help="exclude text components (section 4 market-only baseline)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    scores = run(
        args.market,
        args.date,
        store_root=args.store,
        config_dir=args.config_dir,
        include_text=not args.market_only,
    )
    print(
        f"Scored and stored {len(scores)} risk scores for market "
        f"{args.market.upper()} on {args.date.isoformat()}."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
