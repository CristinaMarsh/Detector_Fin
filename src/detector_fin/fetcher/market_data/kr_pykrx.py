"""KR market-data adapter backed by pykrx (equities and ETFs).

Equities use ``pykrx.stock.get_market_ohlcv_by_date`` and ETFs use
``pykrx.stock.get_etf_ohlcv_by_date``. pykrx works with bare 6-digit codes, so
the ``.KS`` / ``.KQ`` suffix is stripped for the request and preserved on the
emitted bar.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from ...market_config import MarketConfig
from ...schemas import MarketBar
from ...universe import Instrument
from ..base import BaseMarketDataAdapter, bars_from_frame, to_source_code

# pykrx returns Korean column labels; the session date is the frame index.
_COLUMNS = {
    "open": "시가",
    "high": "고가",
    "low": "저가",
    "close": "종가",
    "volume": "거래량",
}


def _yyyymmdd(day: date) -> str:
    return day.strftime("%Y%m%d")


class PykrxAdapter(BaseMarketDataAdapter):
    name = "pykrx"

    def _fetch_raw(
        self, instrument: Instrument, market: MarketConfig, since: date
    ) -> pd.DataFrame:
        from pykrx import stock  # lazy: optional "fetch" dependency

        code = to_source_code(instrument.ticker, market)
        start = _yyyymmdd(since)
        end = _yyyymmdd(date.today())
        if instrument.instrument_type == "etf":
            return stock.get_etf_ohlcv_by_date(start, end, code)
        return stock.get_market_ohlcv_by_date(start, end, code)

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
            date_column=None,  # date lives in the index
        )


__all__ = ["PykrxAdapter"]
