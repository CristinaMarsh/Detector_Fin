"""CN disclosure adapter: cninfo (巨潮资讯), the CSRC-designated platform.

Queries the public announcement history endpoint and emits one RawItem per
announcement. Announcement PDFs live under ``static.cninfo.com.cn``; the item
URL is that official document URL, propagated verbatim downstream.

cninfo is keyed by the bare 6-digit stock code (no extra universe identifier
needed); the exchange column is derived from the ticker suffix.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from ...market_config import MarketConfig
from ...schemas import RawItem
from ...universe import Instrument
from ..base import to_source_code
from .base import BaseDisclosureAdapter

QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
DOCUMENT_BASE = "https://static.cninfo.com.cn/"


def _column_for(ticker: str) -> str:
    # Shanghai listings query the "sse" column, Shenzhen the "szse" column.
    return "sse" if ticker.endswith(".SS") else "szse"


class CninfoAdapter(BaseDisclosureAdapter):
    name = "cninfo"

    def _fetch_raw(
        self, instrument: Instrument, market: MarketConfig, since: datetime
    ) -> dict:
        code = to_source_code(instrument.ticker, market)
        se_date = f"{since.date().isoformat()}~{datetime.now(timezone.utc).date().isoformat()}"
        form = urllib.parse.urlencode(
            {
                "stock": code,
                "column": _column_for(instrument.ticker),
                "category": "",
                "seDate": se_date,
                "pageNum": 1,
                "pageSize": 100,
                "tabName": "fulltext",
            }
        ).encode("ascii")
        request = urllib.request.Request(
            QUERY_URL,
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(request, timeout=30.0) as response:
            return json.loads(response.read().decode("utf-8"))

    def _transform(
        self,
        instrument: Instrument,
        payload: dict,
        market: MarketConfig,
        observed_at: datetime,
    ) -> list[RawItem]:
        announcements = payload.get("announcements") or []
        items: list[RawItem] = []
        for entry in announcements:
            announcement_id = entry.get("announcementId")
            title = entry.get("announcementTitle")
            adjunct_url = entry.get("adjunctUrl")
            time_ms = entry.get("announcementTime")
            if not (announcement_id and title and adjunct_url and time_ms):
                continue  # fidelity only: skip malformed rows, never repair them
            event_time = datetime.fromtimestamp(time_ms / 1000.0, tz=timezone.utc)
            items.append(
                RawItem(
                    id=f"cninfo:{announcement_id}",
                    source=self.name,
                    market_id=market.market_id,
                    lang="zh",
                    ticker_hints=[instrument.ticker],
                    text=title,
                    url=DOCUMENT_BASE + adjunct_url,
                    event_time=event_time,
                    observed_at=observed_at,
                    meta={"announcement_id": str(announcement_id)},
                )
            )
        return items


__all__ = ["CninfoAdapter"]
