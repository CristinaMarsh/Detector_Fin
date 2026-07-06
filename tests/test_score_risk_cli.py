"""End-to-end test for the score_risk CLI over a synthetic store."""

from __future__ import annotations

from datetime import date, timedelta

from detector_fin import score_risk
from detector_fin.judge import MARKET_ONLY_VERSION, METHOD_VERSION
from detector_fin.schemas import MarketStats, RiskScore, TickerDaySnapshot
from detector_fin.storage import ParquetStore

DAY = date(2026, 6, 16)


def _seed(store: ParquetStore) -> None:
    base = DAY - timedelta(days=30)
    series = [
        TickerDaySnapshot(
            ticker="600519.SS",
            entity_id="kweichow-moutai",
            market_id="CN",
            date_local=base + timedelta(days=i),
            market=MarketStats(close=100.0, rv_20d=0.01, ret_1d=0.001),
        )
        for i in range(30)
    ]
    today = TickerDaySnapshot(
        ticker="600519.SS",
        entity_id="kweichow-moutai",
        market_id="CN",
        date_local=DAY,
        sentiment_z=-2.5,
        market=MarketStats(close=110.0, rv_20d=0.03, ret_1d=0.10, limit_hit=True),
    )
    store.append("snapshots", [*series, today])


def test_run_scores_only_dated_snapshots(tmp_path):
    store = ParquetStore(tmp_path)
    _seed(store)
    scores = score_risk.run("CN", DAY, store_root=tmp_path)
    assert len(scores) == 1  # only the ticker with a snapshot for the date
    score = scores[0]
    assert score.method_version == METHOD_VERSION
    assert score.components["limit_hit"] == 1.0
    assert score.components["rv_percentile"] == 1.0
    assert 0.0 < score.score <= 1.0

    stored = store.read("risk_scores", RiskScore, market_id="CN")
    assert len(stored) == 1 and stored[0].ticker == "600519.SS"


def test_market_only_flag(tmp_path):
    store = ParquetStore(tmp_path)
    _seed(store)
    rc = score_risk.main(
        [
            "--market",
            "CN",
            "--date",
            DAY.isoformat(),
            "--store",
            str(tmp_path),
            "--market-only",
        ]
    )
    assert rc == 0
    stored = store.read("risk_scores", RiskScore, market_id="CN")
    assert stored[0].method_version == MARKET_ONLY_VERSION
    assert "sentiment" not in stored[0].components
