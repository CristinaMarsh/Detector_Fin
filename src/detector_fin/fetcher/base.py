"""Market-data source adapter protocol and shared helpers (section 1.1).

A market-data adapter turns a market + a list of instruments into a list of
:class:`~detector_fin.schemas.MarketBar` records. Concrete adapters live under
``fetcher/market_data/`` and lazily import their heavy third-party client
(yfinance / akshare / pykrx) so the core package installs without them.

Two cross-cutting guarantees enforced here rather than in each adapter:

* every bar is stamped with a single UTC ``observed_at`` fetch instant, so the
  data obeys the same point-in-time discipline as the rest of the pipeline;
* bars are filtered to valid exchange sessions via the market's trading
  calendar, so a stray non-trading row never enters storage.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Protocol, runtime_checkable

import exchange_calendars as xcals
import pandas as pd

from ..market_config import MarketConfig
from ..schemas import MarketBar
from ..universe import Instrument


def utc_now() -> datetime:
    """The current UTC instant, used as the default ``observed_at`` stamp."""
    return datetime.now(timezone.utc)


@runtime_checkable
class MarketDataAdapter(Protocol):
    """Protocol every market-data adapter implements."""

    name: str

    def fetch_bars(
        self,
        market: MarketConfig,
        instruments: list[Instrument],
        since: date,
        observed_at: datetime | None = None,
    ) -> list[MarketBar]: ...


# -- ticker mapping ----------------------------------------------------------


def to_source_code(ticker: str, market: MarketConfig) -> str:
    """Strip the market's exchange suffix to get the source-side symbol code.

    US symbols have no suffix and pass through unchanged (``NVDA`` -> ``NVDA``);
    CN/KR tickers lose their ``.SS``/``.SZ``/``.KS``/``.KQ`` suffix
    (``600519.SS`` -> ``600519``).
    """
    for suffix in market.ticker_suffixes:
        if ticker.endswith(suffix):
            return ticker[: -len(suffix)]
    return ticker


def cn_code_to_ticker(code: str) -> str:
    """Map a bare 6-digit CN code to its suffixed ticker.

    Shanghai-listed codes start with 5 (funds/ETFs), 6 (main board) or 9
    (B shares); everything else (0, 1, 3) is Shenzhen-listed.
    """
    code = code.strip()
    if code and code[0] in ("5", "6", "9"):
        return f"{code}.SS"
    return f"{code}.SZ"


# -- calendar filtering ------------------------------------------------------


def sessions_between(market: MarketConfig, start: date, end: date) -> set[date]:
    """Set of valid trading-session dates in ``[start, end]`` for the market."""
    calendar = xcals.get_calendar(market.trading_calendar)
    sessions = calendar.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
    return {ts.date() for ts in sessions}


def filter_to_sessions(bars: list[MarketBar], market: MarketConfig) -> list[MarketBar]:
    """Keep only bars whose ``date_local`` is a valid exchange session."""
    if not bars:
        return []
    lo = min(b.date_local for b in bars)
    hi = max(b.date_local for b in bars)
    valid = sessions_between(market, lo, hi)
    return [b for b in bars if b.date_local in valid]


# -- adapter base ------------------------------------------------------------


class BaseMarketDataAdapter:
    """Template adapter: fetch raw frames per instrument, transform, filter.

    Subclasses implement :meth:`_fetch_raw` (the only method that touches the
    network / third-party client) and :meth:`_transform` (pure column mapping).
    Tests drive :meth:`_transform` directly with recorded fixture frames, and
    exercise :meth:`fetch_bars` by stubbing :meth:`_fetch_raw`.
    """

    name: str = "base"

    def fetch_bars(
        self,
        market: MarketConfig,
        instruments: list[Instrument],
        since: date,
        observed_at: datetime | None = None,
    ) -> list[MarketBar]:
        stamp = observed_at or utc_now()
        bars: list[MarketBar] = []
        for inst in instruments:
            frame = self._fetch_raw(inst, market, since)
            bars.extend(self._transform(inst, frame, market, stamp))
        return filter_to_sessions(bars, market)

    def _fetch_raw(
        self, instrument: Instrument, market: MarketConfig, since: date
    ) -> pd.DataFrame:
        raise NotImplementedError

    def _transform(
        self,
        instrument: Instrument,
        frame: pd.DataFrame,
        market: MarketConfig,
        observed_at: datetime,
    ) -> list[MarketBar]:
        raise NotImplementedError


def bars_from_frame(
    instrument: Instrument,
    frame: pd.DataFrame,
    market: MarketConfig,
    source: str,
    observed_at: datetime,
    *,
    columns: dict[str, str],
    date_column: str | None,
) -> list[MarketBar]:
    """Build ``MarketBar`` records from a source frame.

    ``columns`` maps the canonical field name (open/high/low/close/volume) to
    the source frame's column label. ``date_column`` names the column holding
    the session date, or ``None`` to read it from the frame index.
    """
    bars: list[MarketBar] = []
    for idx, row in frame.iterrows():
        raw_date = idx if date_column is None else row[date_column]
        day = pd.Timestamp(raw_date).date()
        bars.append(
            MarketBar(
                ticker=instrument.ticker,
                market_id=market.market_id,
                instrument_type=instrument.instrument_type,
                date_local=day,
                open=float(row[columns["open"]]),
                high=float(row[columns["high"]]),
                low=float(row[columns["low"]]),
                close=float(row[columns["close"]]),
                volume=float(row[columns["volume"]]),
                currency=market.currency,
                source=source,
                observed_at=observed_at,
            )
        )
    return bars


__all__ = [
    "MarketDataAdapter",
    "BaseMarketDataAdapter",
    "bars_from_frame",
    "utc_now",
    "to_source_code",
    "cn_code_to_ticker",
    "sessions_between",
    "filter_to_sessions",
]
