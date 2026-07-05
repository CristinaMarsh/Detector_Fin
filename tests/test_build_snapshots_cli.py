"""End-to-end test for the build_snapshots CLI over a synthetic store."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from detector_fin import build_snapshots
from detector_fin.schemas import MarketBar, RawItem, TickerDaySnapshot
from detector_fin.storage import ParquetStore

DAY = date(2026, 6, 16)
OBSERVED = datetime(2026, 6, 16, 0, 0, tzinfo=timezone.utc)  # before CN cutoff


def _seed(store: ParquetStore) -> None:
    store.append(
        "raw_items",
        [
            RawItem(
                id="guba:1",
                source="eastmoney_guba",
                market_id="CN",
                lang="zh",
                ticker_hints=["600519.SS"],
                text="贵州茅台业绩超预期 利好",
                url="https://guba.eastmoney.com/news,600519,1.html",
                event_time=OBSERVED - timedelta(hours=1),
                observed_at=OBSERVED,
            )
        ],
    )
    store.append(
        "bars",
        [
            MarketBar(
                ticker="600519.SS",
                market_id="CN",
                instrument_type="equity",
                date_local=DAY - timedelta(days=1),
                open=100,
                high=100,
                low=100,
                close=100.0,
                volume=1,
                currency="CNY",
                source="test",
                observed_at=OBSERVED,
            ),
            MarketBar(
                ticker="600519.SS",
                market_id="CN",
                instrument_type="equity",
                date_local=DAY,
                open=101,
                high=105,
                low=101,
                close=104.0,
                volume=1,
                currency="CNY",
                source="test",
                observed_at=OBSERVED,
            ),
        ],
    )


def test_run_builds_one_snapshot_per_cn_instrument(tmp_path):
    store = ParquetStore(tmp_path)
    _seed(store)
    snapshots = build_snapshots.run("CN", DAY, store_root=tmp_path)

    # One snapshot per CN universe instrument (5 in the pilot universe).
    assert len(snapshots) == 5
    by_ticker = {s.ticker: s for s in snapshots}

    moutai = by_ticker["600519.SS"]
    assert moutai.n_items_by_source == {"eastmoney_guba": 1}
    assert moutai.market.close == 104.0
    assert moutai.top_fragments[0].source_url == (
        "https://guba.eastmoney.com/news,600519,1.html"
    )
    # Instruments with no bars for the day are explicit suspension gaps.
    assert by_ticker["300750.SZ"].market.suspended is True

    stored = store.read("snapshots", TickerDaySnapshot, market_id="CN")
    assert len(stored) == 5


def test_main_prints_summary(tmp_path, capsys):
    store = ParquetStore(tmp_path)
    _seed(store)
    rc = build_snapshots.main(
        ["--market", "CN", "--date", "2026-06-16", "--store", str(tmp_path)]
    )
    assert rc == 0
    assert "5 snapshots" in capsys.readouterr().out
