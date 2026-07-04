"""Tests for the append-only, partitioned parquet storage layer (M1)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from detector_fin.schemas import MarketStats, RawItem, RiskScore, TickerDaySnapshot
from detector_fin.storage import ParquetStore


def _raw(id_: str, market_id: str = "US", day: int = 2) -> RawItem:
    return RawItem(
        id=id_,
        source="stocktwits",
        market_id=market_id,
        lang="en",
        ticker_hints=["AAPL"],
        text="text " + id_,
        event_time=datetime(2026, 1, day, 13, 0, tzinfo=timezone.utc),
        observed_at=datetime(2026, 1, day, 13, 5, tzinfo=timezone.utc),
    )


def test_append_and_read_roundtrip(tmp_path):
    store = ParquetStore(tmp_path)
    items = [_raw("a"), _raw("b")]
    paths = store.append("raw_items", items)
    assert len(paths) == 1  # same (market, date) partition -> one part file
    assert all(p.exists() for p in paths)

    back = store.read("raw_items", RawItem, market_id="US", day=date(2026, 1, 2))
    assert {i.id for i in back} == {"a", "b"}
    assert back[0] == next(i for i in items if i.id == back[0].id)


def test_append_is_append_only(tmp_path):
    store = ParquetStore(tmp_path)
    store.append("raw_items", [_raw("a")])
    store.append("raw_items", [_raw("b")])  # same partition, second append

    part = tmp_path / "raw_items" / "market_id=US" / "date=2026-01-02"
    files = list(part.glob("*.parquet"))
    assert len(files) == 2  # two separate part files, nothing overwritten

    back = store.read("raw_items", RawItem, market_id="US", day=date(2026, 1, 2))
    assert {i.id for i in back} == {"a", "b"}


def test_partition_layout_on_disk(tmp_path):
    store = ParquetStore(tmp_path)
    store.append("raw_items", [_raw("a", market_id="US", day=2)])
    store.append("raw_items", [_raw("c", market_id="CN", day=3)])

    assert (tmp_path / "raw_items" / "market_id=US" / "date=2026-01-02").is_dir()
    assert (tmp_path / "raw_items" / "market_id=CN" / "date=2026-01-03").is_dir()


def test_market_and_date_filtering(tmp_path):
    store = ParquetStore(tmp_path)
    store.append("raw_items", [_raw("us1", "US", 2), _raw("us2", "US", 3)])
    store.append("raw_items", [_raw("cn1", "CN", 2)])

    only_us = store.read("raw_items", RawItem, market_id="US")
    assert {i.id for i in only_us} == {"us1", "us2"}

    only_cn = store.read("raw_items", RawItem, market_id="CN")
    assert {i.id for i in only_cn} == {"cn1"}

    us_day2 = store.read("raw_items", RawItem, market_id="US", day=date(2026, 1, 2))
    assert {i.id for i in us_day2} == {"us1"}

    everything = store.read("raw_items", RawItem)
    assert {i.id for i in everything} == {"us1", "us2", "cn1"}


def test_multiple_partitions_in_one_append(tmp_path):
    store = ParquetStore(tmp_path)
    paths = store.append(
        "raw_items",
        [_raw("us1", "US", 2), _raw("cn1", "CN", 2), _raw("us2", "US", 3)],
    )
    assert len(paths) == 3  # three distinct (market, date) partitions


def test_empty_append_is_noop(tmp_path):
    store = ParquetStore(tmp_path)
    assert store.append("raw_items", []) == []
    assert store.read("raw_items", RawItem) == []


def test_read_missing_dataset_returns_empty(tmp_path):
    store = ParquetStore(tmp_path)
    assert store.read("does_not_exist", RawItem) == []


def test_nested_snapshot_roundtrip(tmp_path):
    store = ParquetStore(tmp_path)
    snap = TickerDaySnapshot(
        ticker="600519.SS",
        entity_id="kweichow-moutai",
        market_id="CN",
        date_local=date(2026, 1, 5),
        n_items_by_source={"eastmoney_guba": 12, "xueqiu": 3},
        sentiment_z=1.8,
        sentiment_model_version="zh-finbert-1.0",
        event_counts={"rumor": 2},
        market=MarketStats(
            close=1700.0,
            ret_1d=0.099,
            limit_hit=True,
            dist_to_upper_limit=0.0,
        ),
    )
    store.append("snapshots", [snap])
    back = store.read("snapshots", TickerDaySnapshot, market_id="CN")
    assert len(back) == 1
    assert back[0] == snap
    assert back[0].market.limit_hit is True
    assert back[0].n_items_by_source["eastmoney_guba"] == 12


def test_introspection_helpers(tmp_path):
    store = ParquetStore(tmp_path)
    store.append(
        "risk",
        [
            RiskScore(
                ticker="AAPL",
                market_id="US",
                date_local=date(2026, 1, 2),
                score=0.3,
                method_version="q-0.1",
            ),
            RiskScore(
                ticker="600519.SS",
                market_id="CN",
                date_local=date(2026, 1, 5),
                score=0.7,
                method_version="q-0.1",
            ),
        ],
    )
    assert store.markets("risk") == ["CN", "US"]
    assert store.dates("risk", "US") == [date(2026, 1, 2)]
    assert store.dates("risk", "CN") == [date(2026, 1, 5)]
