"""US market-data adapter backed by yfinance (equities and ETFs).

US symbols are bare (no exchange suffix) and ETFs are fetched exactly like
equities, so a single code path serves both instrument types.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from ...market_config import MarketConfig
from ...schemas import MarketBar
from ...universe import Instrument
from ..base import BaseMarketDataAdapter, bars_from_frame, to_source_code

# yfinance history() column labels.
_COLUMNS = {
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "volume": "Volume",
}


class YFinanceAdapter(BaseMarketDataAdapter):
    name = "yfinance"

    def _fetch_raw(
        self, instrument: Instrument, market: MarketConfig, since: date
    ) -> pd.DataFrame:
        import yfinance as yf  # lazy: optional "fetch" dependency

        symbol = to_source_code(instrument.ticker, market)
        frame = yf.Ticker(symbol).history(start=since.isoformat(), auto_adjust=False)
        return frame

    def _transform(
        self,
        instrument: Instrument,
        frame: pd.DataFrame,
        market: MarketConfig,
        observed_at: datetime,
    ) -> list[MarketBar]:
        if frame is None or frame.empty:
            return []
        return bars_from_frame(
            instrument,
            frame,
            market,
            self.name,
            observed_at,
            columns=_COLUMNS,
            date_column=None,  # date lives in the DatetimeIndex
        )


__all__ = ["YFinanceAdapter"]
