"""KR sentiment adapter: Naver Finance discussion board (종목토론실).

Fetches the public board list page per stock code (HTML, EUC-KR encoded) and
emits one RawItem per post row. Only the list page is read -- titles, dates
and post ids -- never post bodies. Timestamps are KST and normalised to UTC.

Per Design Contract section 1.1, scraper adapters must respect robots.txt and
rate limits: keep ``request_delay_seconds`` positive in production, cache
aggressively, and degrade gracefully (enforced by the shared template). The
row regex mirrors the board's stable list markup as recorded in the test
fixture; if Naver changes the markup, re-record the fixture and adjust the
pattern -- the rest of the pipeline is unaffected.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from ...market_config import MarketConfig
from ...schemas import RawItem
from ...universe import Instrument
from ..base import to_source_code
from ..item_adapters import BaseItemAdapter, http_get_text

BOARD_URL = "https://finance.naver.com/item/board.naver?code={code}"
POST_URL = "https://finance.naver.com/item/board_read.naver?code={code}&nid={nid}"

KST = ZoneInfo("Asia/Seoul")

# One board row: date cell, then the title anchor carrying the post id (nid).
ROW_PATTERN = re.compile(
    r"<td[^>]*>\s*(?P<date>\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2})\s*</td>.*?"
    r"board_read\.naver\?code=\d+&(?:amp;)?nid=(?P<nid>\d+)[^>]*>(?P<title>[^<]+)<",
    re.DOTALL,
)


class NaverBoardAdapter(BaseItemAdapter):
    name = "naver_finance_board"

    # Seconds slept before each network request; zero only in tests.
    request_delay_seconds: float = 2.0

    def _fetch_raw(
        self, instrument: Instrument, market: MarketConfig, since: datetime
    ) -> str:
        if self.request_delay_seconds > 0:
            time.sleep(self.request_delay_seconds)
        code = to_source_code(instrument.ticker, market)
        return http_get_text(BOARD_URL.format(code=code), encoding="euc-kr")

    def _transform(
        self,
        instrument: Instrument,
        payload: str,
        market: MarketConfig,
        observed_at: datetime,
    ) -> list[RawItem]:
        code = to_source_code(instrument.ticker, market)
        items: list[RawItem] = []
        for match in ROW_PATTERN.finditer(payload or ""):
            nid = match.group("nid")
            title = match.group("title").strip()
            if not title:
                continue
            event_time = datetime.strptime(
                match.group("date"), "%Y.%m.%d %H:%M"
            ).replace(tzinfo=KST)
            items.append(
                RawItem(
                    id=f"naver_finance_board:{code}:{nid}",
                    source=self.name,
                    market_id=market.market_id,
                    lang="ko",
                    ticker_hints=[instrument.ticker],
                    text=title,
                    url=POST_URL.format(code=code, nid=nid),
                    event_time=event_time,
                    observed_at=observed_at,
                    meta={"nid": nid},
                )
            )
        return items


__all__ = ["NaverBoardAdapter"]
