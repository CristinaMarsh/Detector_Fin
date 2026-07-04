"""CN market-data adapter backed by akshare (equities and ETFs).

Equities use ``akshare.stock_zh_a_hist`` and ETFs use
``akshare.fund_etf_hist_em`` (both East Money sources). akshare works with bare
6-digit codes, so the ``.SS`` / ``.SZ`` suffix is stripped for the request and
preserved on the emitted bar.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from ...market_config import MarketConfig
from ...schemas import MarketBar
from ...universe import Instrument
from ..base import BaseMarketDataAdapter, bars_from_frame, to_source_code

# akshare returns Chinese column labels for both endpoints.
_COLUMNS = {
    "open": "开盘",
    "high": "最高",
    "low": "最低",
    "close": "收盘",
    "volume": "成交量",
}
_DATE_COLUMN = "日期"


def _yyyymmdd(day: date) -> str:
    return day.strftime("%Y%m%d")


class AkshareAdapter(BaseMarketDataAdapter):
    name = "akshare"

    def _fetch_raw(
        self, instrument: Instrument, market: MarketConfig, since: date
    ) -> pd.DataFrame:
        import akshare as ak  # lazy: optional "fetch" dependency

        code = to_source_code(instrument.ticker, market)
        start = _yyyymmdd(since)
        end = _yyyymmdd(date.today())
        if instrument.instrument_type == "etf":
            return ak.fund_etf_hist_em(
                symbol=code, period="daily", start_date=start, end_date=end, adjust=""
            )
        return ak.stock_zh_a_hist(
            symbol=code, period="daily", start_date=start, end_date=end, adjust=""
        )

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
            date_column=_DATE_COLUMN,
        )


__all__ = ["AkshareAdapter"]
