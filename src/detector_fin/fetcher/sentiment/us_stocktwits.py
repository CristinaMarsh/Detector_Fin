"""US sentiment adapter: StockTwits public symbol streams.

Fetches the public message stream per symbol and emits one RawItem per
message. Usernames are hashed before storage (``author_hash``); message text
is untrusted input and is sanitized downstream at the aggregator boundary,
never here (fetcher does no interpretation).
"""

from __future__ import annotations

from datetime import datetime, timezone

from ...market_config import MarketConfig
from ...schemas import RawItem
from ...universe import Instrument
from ..base import to_source_code
from ..item_adapters import BaseItemAdapter, hash_author, http_get_json

STREAM_URL = "https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
MESSAGE_URL = "https://stocktwits.com/message/{message_id}"


class StocktwitsAdapter(BaseItemAdapter):
    name = "stocktwits"

    def _fetch_raw(
        self, instrument: Instrument, market: MarketConfig, since: datetime
    ) -> dict:
        symbol = to_source_code(instrument.ticker, market)
        return http_get_json(STREAM_URL.format(symbol=symbol))

    def _transform(
        self,
        instrument: Instrument,
        payload: dict,
        market: MarketConfig,
        observed_at: datetime,
    ) -> list[RawItem]:
        items: list[RawItem] = []
        for message in payload.get("messages", []):
            message_id = message.get("id")
            body = message.get("body")
            created_at = message.get("created_at")
            if not (message_id and body and created_at):
                continue  # fidelity only: skip malformed rows, never repair
            event_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=timezone.utc)
            username = (message.get("user") or {}).get("username") or ""
            items.append(
                RawItem(
                    id=f"stocktwits:{message_id}",
                    source=self.name,
                    market_id=market.market_id,
                    lang="en",
                    ticker_hints=[instrument.ticker],
                    text=body,
                    url=MESSAGE_URL.format(message_id=message_id),
                    author_hash=hash_author(username) if username else None,
                    event_time=event_time,
                    observed_at=observed_at,
                    meta={"message_id": str(message_id)},
                )
            )
        return items


__all__ = ["StocktwitsAdapter"]
