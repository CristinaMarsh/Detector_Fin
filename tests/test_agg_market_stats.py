"""Tests for MarketStats computation from bar history."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from detector_fin.aggregator.market_stats import compute_market_stats, price_limit_band
from detector_fin.market_config import load_market_config
from detector_fin.schemas import MarketBar
from detector_fin.universe import Instrument

CN = load_market_config("CN")
US = load_market_config("US")
KR = load_market_config("KR")

MOUTAI = Instrument(
    ticker="600519.SS",
    name_en="Kweichow Moutai",
    market_id="CN",
    instrument_type="equity",
)
CHINEXT = Instrument(
    ticker="300750.SZ", name_en="CATL", market_id="CN", instrument_type="equity"
)
NVDA = Instrument(
    ticker="NVDA", name_en="NVIDIA", market_id="US", instrument_type="equity"
)
KODEX = Instrument(
    ticker="069500.KS", name_en="KODEX 200", market_id="KR", instrument_type="etf"
)


def _bars(
    ticker: str, market_id: str, closes: list[float], end: date
) -> list[MarketBar]:
    start = end - timedelta(days=len(closes) - 1)
    return [
        MarketBar(
            ticker=ticker,
            market_id=market_id,
            instrument_type="equity",
            date_local=start + timedelta(days=i),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=1000,
            currency="CNY",
            source="test",
            observed_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
        )
        for i, c in enumerate(closes)
    ]


def test_price_limit_bands_per_board():
    assert price_limit_band(CN, MOUTAI) == 0.10  # main board
    assert price_limit_band(CN, CHINEXT) == 0.20  # ChiNext 300xxx
    assert price_limit_band(US, NVDA) is None
    assert price_limit_band(KR, KODEX) == 0.30


def test_limit_hit_and_distances_cn():
    end = date(2026, 6, 16)
    stats = compute_market_stats(
        _bars("600519.SS", "CN", [100.0, 110.0], end), end, CN, MOUTAI
    )
    assert stats.limit_hit is True  # +10% == main-board band
    assert abs(stats.dist_to_upper_limit - 0.0) < 1e-9
    assert abs(stats.dist_to_lower_limit - 0.2) < 1e-9
    assert abs(stats.ret_1d - 0.10) < 1e-9


def test_us_has_no_limit_fields():
    end = date(2026, 6, 16)
    stats = compute_market_stats(
        _bars("NVDA", "US", [100.0, 130.0], end), end, US, NVDA
    )
    assert stats.limit_hit is False
    assert stats.dist_to_upper_limit is None and stats.dist_to_lower_limit is None
    assert abs(stats.ret_1d - 0.30) < 1e-9


def test_missing_session_bar_is_explicit_suspension_gap():
    end = date(2026, 6, 16)
    bars = _bars("600519.SS", "CN", [100.0, 101.0], end - timedelta(days=1))
    stats = compute_market_stats(bars, end, CN, MOUTAI)
    assert stats.suspended is True
    assert stats.close is None and stats.ret_1d is None  # never forward-filled


def test_rv_and_drawdown_windows():
    end = date(2026, 6, 30)
    closes = [100.0 + i for i in range(25)]  # steadily rising
    stats = compute_market_stats(_bars("NVDA", "US", closes, end), end, US, NVDA)
    assert stats.rv_20d is not None and stats.rv_20d > 0
    assert abs(stats.drawdown_60d) < 1e-9  # at the peak -> zero drawdown

    falling = [100.0] * 10 + [80.0]
    stats2 = compute_market_stats(_bars("NVDA", "US", falling, end), end, US, NVDA)
    assert abs(stats2.drawdown_60d - (-0.2)) < 1e-9


def test_future_bars_ignored():
    end = date(2026, 6, 16)
    bars = _bars("NVDA", "US", [100.0, 110.0, 999.0], end + timedelta(days=1))
    stats = compute_market_stats(bars, end, US, NVDA)
    assert stats.close == 110.0  # the bar dated after `end` never leaks in
