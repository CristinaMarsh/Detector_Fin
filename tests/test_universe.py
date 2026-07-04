"""Tests for the universe registry loader (section 0)."""

from __future__ import annotations

import pytest

from detector_fin.universe import (
    Instrument,
    UniverseError,
    load_universe,
    universe_for_market,
)


def test_load_shipped_universe():
    insts = load_universe()
    tickers = {i.ticker for i in insts}
    assert {"NVDA", "SPY", "600519.SS", "510300.SS", "069500.KS"} <= tickers
    # instrument_type is populated for every entry.
    assert all(i.instrument_type in {"equity", "etf"} for i in insts)


def test_market_filter():
    cn = universe_for_market("cn")  # case-insensitive
    assert {i.market_id for i in cn} == {"CN"}
    assert any(i.instrument_type == "etf" for i in cn)


def test_cn_etf_carries_price_limit_override():
    cn = {i.ticker: i for i in universe_for_market("CN")}
    assert cn["510300.SS"].price_limit_override == 0.10
    assert cn["588000.SS"].price_limit_override == 0.10
    # A single stock has no override; it inherits the market default.
    assert cn["600519.SS"].price_limit_override is None


def test_instrument_type_required():
    with pytest.raises(Exception):
        Instrument(ticker="X", name_en="X", market_id="US")


def test_invalid_instrument_type_rejected():
    with pytest.raises(Exception):
        Instrument(ticker="X", name_en="X", market_id="US", instrument_type="bond")


def test_missing_file_raises(tmp_path):
    with pytest.raises(UniverseError):
        load_universe(tmp_path / "nope.yaml")


def test_duplicate_ticker_rejected(tmp_path):
    path = tmp_path / "u.yaml"
    path.write_text(
        "instruments:\n"
        "  - {ticker: AAA, name_en: A, market_id: US, instrument_type: equity}\n"
        "  - {ticker: AAA, name_en: A2, market_id: US, instrument_type: etf}\n"
    )
    with pytest.raises(UniverseError):
        load_universe(path)
