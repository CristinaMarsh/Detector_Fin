"""Tests for the fetch_bars CLI, driven with a stubbed adapter (no network)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from detector_fin import fetch_bars
from detector_fin.schemas import MarketBar
from detector_fin.storage import ParquetStore

OBSERVED = datetime(2026, 6, 8, 0, 30, tzinfo=timezone.utc)


class StubAdapter:
    """Returns fixed bars for the market's first instrument; records its call."""

    name = "stub"

    def __init__(self):
        self.calls = []

    def fetch_bars(self, market, instruments, since, observed_at=None):
        self.calls.append((market.market_id, [i.ticker for i in instruments], since))
        return [
            MarketBar(
                ticker="510300.SS",
                market_id="CN",
                instrument_type="etf",
                date_local=date(2026, 6, 1),
                open=3.90,
                high=3.93,
                low=3.895,
                close=3.92,
                volume=1200000,
                currency="CNY",
                source="stub",
                observed_at=observed_at or OBSERVED,
            )
        ]


def test_run_appends_bars_to_store(tmp_path):
    stub = StubAdapter()
    bars = fetch_bars.run(
        "CN",
        date(2026, 6, 1),
        store_root=tmp_path,
        adapter=stub,
        observed_at=OBSERVED,
    )
    assert len(bars) == 1

    # The stub saw the CN universe (loaded from config), not an empty list.
    assert stub.calls[0][0] == "CN"
    assert "600519.SS" in stub.calls[0][1]

    # Bars landed in the "bars" dataset, partitioned by market/date.
    store = ParquetStore(tmp_path)
    stored = store.read("bars", MarketBar, market_id="CN")
    assert len(stored) == 1
    assert stored[0].ticker == "510300.SS"
    assert stored[0].instrument_type == "etf"
    assert (tmp_path / "bars" / "market_id=CN" / "date=2026-06-01").is_dir()


def test_run_uppercases_market_id(tmp_path):
    stub = StubAdapter()
    fetch_bars.run(
        "cn", date(2026, 6, 1), store_root=tmp_path, adapter=stub, observed_at=OBSERVED
    )
    assert stub.calls[0][0] == "CN"


def test_build_adapter_registry():
    from detector_fin.fetcher.market_data import (
        AkshareAdapter,
        PykrxAdapter,
        YFinanceAdapter,
    )

    assert isinstance(fetch_bars.build_adapter("US"), YFinanceAdapter)
    assert isinstance(fetch_bars.build_adapter("CN"), AkshareAdapter)
    assert isinstance(fetch_bars.build_adapter("KR"), PykrxAdapter)


def test_build_adapter_unknown_market_exits():
    with pytest.raises(SystemExit):
        fetch_bars.build_adapter("JP")


def test_main_with_stub(tmp_path, monkeypatch, capsys):
    stub = StubAdapter()
    monkeypatch.setattr(fetch_bars, "build_adapter", lambda market_id: stub)
    rc = fetch_bars.main(
        ["--market", "CN", "--since", "2026-06-01", "--store", str(tmp_path)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 bars" in out and "CN" in out
    stored = ParquetStore(tmp_path).read("bars", MarketBar, market_id="CN")
    assert len(stored) == 1
