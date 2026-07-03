"""Tests for the market abstraction: MarketConfig + loader (section 0)."""

from __future__ import annotations

from datetime import date, time, timezone

import pytest

from detector_fin.market_config import (
    MarketConfig,
    MarketConfigError,
    load_all_market_configs,
    load_market_config,
)


def test_load_all_shipped_markets():
    cfgs = load_all_market_configs()
    assert set(cfgs) == {"US", "CN", "KR"}


def test_us_config_shape():
    us = load_market_config("US")
    assert us.currency == "USD"
    assert us.timezone == "America/New_York"
    assert us.trading_calendar == "XNYS"
    assert us.price_limit is None
    assert us.ticker_suffixes == []
    assert us.decision_time_local == time(8, 30)
    assert us.label_params.k == 5
    assert us.label_params.limit_hit_is_event is False


def test_cn_config_price_limits():
    cn = load_market_config("cn")  # case-insensitive lookup
    assert cn.price_limit == {"main": 0.10, "star_chinext": 0.20, "st": 0.05}
    assert cn.ticker_suffixes == [".SS", ".SZ"]
    assert cn.label_params.suspension_is_event is True
    assert "eastmoney_guba" in cn.sentiment_sources


def test_kr_config():
    kr = load_market_config("KR")
    assert kr.price_limit == {"all": 0.30}
    assert kr.decision_time_local == time(8, 0)
    assert kr.trading_calendar == "XKRX"


def test_decision_datetime_utc_us():
    us = load_market_config("US")
    # 2026-01-02 08:30 America/New_York is UTC-5 in January -> 13:30 UTC.
    dt = us.decision_datetime_utc(date(2026, 1, 2))
    assert dt.tzinfo == timezone.utc
    assert (dt.hour, dt.minute) == (13, 30)


def test_decision_datetime_utc_cn():
    cn = load_market_config("CN")
    # 08:30 Asia/Shanghai (UTC+8) -> 00:30 UTC same day.
    dt = cn.decision_datetime_utc(date(2026, 1, 5))
    assert (dt.hour, dt.minute) == (0, 30)


def test_missing_market_raises():
    with pytest.raises(MarketConfigError):
        load_market_config("JP")


def test_invalid_timezone_rejected():
    with pytest.raises(Exception):
        MarketConfig(
            market_id="XX",
            timezone="Mars/Olympus",
            trading_calendar="XNYS",
            decision_time_local="08:30",
            currency="USD",
        )


def test_invalid_calendar_rejected():
    with pytest.raises(Exception):
        MarketConfig(
            market_id="XX",
            timezone="America/New_York",
            trading_calendar="XNOPE",
            decision_time_local="08:30",
            currency="USD",
        )


def test_label_params_override(tmp_path):
    cfg_dir = tmp_path / "markets"
    cfg_dir.mkdir()
    (cfg_dir / "xx.yaml").write_text(
        """
market_id: XX
timezone: America/New_York
trading_calendar: XNYS
decision_time_local: "09:00"
currency: USD
label_params:
  k: 10
  d: 0.15
""".strip()
    )
    cfg = load_market_config("XX", config_dir=cfg_dir)
    assert cfg.label_params.k == 10
    assert cfg.label_params.d == 0.15
    # untouched fields keep defaults
    assert cfg.label_params.j == 3.0
    assert cfg.label_params.rv_percentile == 0.95


def test_time_string_parsing():
    cfg = MarketConfig(
        market_id="XX",
        timezone="America/New_York",
        trading_calendar="XNYS",
        decision_time_local="09:15:00",
        currency="USD",
    )
    assert cfg.decision_time_local == time(9, 15, 0)
