"""CN sentiment adapter: East Money guba (股吧) forum post lists.

Fetches the public article-list API per stock code and emits one RawItem per
post title. Post URLs use the canonical guba permalink pattern. Timestamps in
the payload are Beijing local time and are normalised to UTC.

Per Design Contract section 1.1, scraper adapters must respect robots.txt and
rate limits: production runs should keep ``request_delay_seconds`` positive so
consecutive per-instrument requests are spaced out, cache aggressively, and
degrade gracefully to empty batches (enforced by the shared template).
The upstream list API is an internal endpoint whose shape was recorded into
the test fixture; if East Money changes it, re-record the fixture and adjust
``_transform`` -- the rest of the pipeline is unaffected.
"""

from __future__ import annotations

import time
from datetime import datetime
from zoneinfo import ZoneInfo

from ...market_config import MarketConfig
from ...schemas import RawItem
from ...universe import Instrument
from ..base import to_source_code
from ..item_adapters import BaseItemAdapter, hash_author, http_get_json

LIST_URL = (
    "https://gbapi.eastmoney.com/webarticlelist/api/Article/Articlelist"
    "?code={code}&type=0&sorttype=1&ps=100&p=1"
)
POST_URL = "https://guba.eastmoney.com/news,{code},{post_id}.html"

CST = ZoneInfo("Asia/Shanghai")


class EastmoneyGubaAdapter(BaseItemAdapter):
    name = "eastmoney_guba"

    # Seconds slept before each network request; keeps consecutive
    # per-instrument fetches polite. Zero only in tests (stubbed fetch).
    request_delay_seconds: float = 2.0

    def _fetch_raw(
        self, instrument: Instrument, market: MarketConfig, since: datetime
    ) -> dict:
        if self.request_delay_seconds > 0:
            time.sleep(self.request_delay_seconds)
        code = to_source_code(instrument.ticker, market)
        return http_get_json(LIST_URL.format(code=code))

    def _transform(
        self,
        instrument: Instrument,
        payload: dict,
        market: MarketConfig,
        observed_at: datetime,
    ) -> list[RawItem]:
        code = to_source_code(instrument.ticker, market)
        posts = (payload.get("re") if isinstance(payload, dict) else None) or []
        items: list[RawItem] = []
        for post in posts:
            post_id = post.get("post_id")
            title = post.get("post_title")
            publish_time = post.get("post_publish_time")
            if not (post_id and title and publish_time):
                continue  # fidelity only: skip malformed rows, never repair
            event_time = datetime.strptime(publish_time, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=CST
            )
            nickname = post.get("user_nickname") or ""
            items.append(
                RawItem(
                    id=f"eastmoney_guba:{post_id}",
                    source=self.name,
                    market_id=market.market_id,
                    lang="zh",
                    ticker_hints=[instrument.ticker],
                    text=title,
                    url=POST_URL.format(code=code, post_id=post_id),
                    author_hash=hash_author(nickname) if nickname else None,
                    event_time=event_time,
                    observed_at=observed_at,
                    meta={"post_id": str(post_id)},
                )
            )
        return items


__all__ = ["EastmoneyGubaAdapter"]
