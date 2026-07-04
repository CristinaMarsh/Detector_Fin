"""Helpers for loading recorded market-data fixtures in adapter tests.

Fixtures are CSVs recorded in each third-party client's native output shape
(yfinance / akshare / pykrx column labels), so the adapters' column mapping is
exercised realistically without any network access.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "market_data"


def load_yfinance(name: str) -> pd.DataFrame:
    """yfinance history(): session date lives in the DatetimeIndex."""
    return pd.read_csv(FIXTURES / name, index_col="Date", parse_dates=["Date"])


def load_akshare(name: str) -> pd.DataFrame:
    """akshare hist frames: the session date is the '日期' column."""
    return pd.read_csv(FIXTURES / name)


def load_pykrx(name: str) -> pd.DataFrame:
    """pykrx OHLCV frames: the session date is the '날짜' index."""
    return pd.read_csv(FIXTURES / name, index_col="날짜", parse_dates=["날짜"])
