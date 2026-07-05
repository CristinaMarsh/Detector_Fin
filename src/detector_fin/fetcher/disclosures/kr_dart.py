"""KR disclosure adapter: DART, Korea FSS electronic disclosure system.

Queries the OpenDART ``list.json`` API and emits one RawItem per filing. The
item URL is the official DART viewer page for the receipt number, propagated
verbatim downstream.

Requirements, both skipped-not-guessed when absent:
* ``DART_API_KEY`` environment variable (free key from opendart.fss.or.kr);
  without it the adapter yields empty batches.
* ``ids.dart_corp_code`` on the instrument (8-digit code from DART's official
  corpCode.xml download).
"""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from ...market_config import MarketConfig
from ...schemas import RawItem
from ...universe import Instrument
from .base import BaseDisclosureAdapter, http_get_json

LIST_URL = (
    "https://opendart.fss.or.kr/api/list.json"
    "?crtfc_key={key}&corp_code={corp_code}&bgn_de={bgn_de}&page_count=100"
)
VIEWER_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

KST = ZoneInfo("Asia/Seoul")


class DartAdapter(BaseDisclosureAdapter):
    name = "dart"

    def _supports(self, instrument: Instrument) -> bool:
        return "dart_corp_code" in instrument.ids and bool(
            os.environ.get("DART_API_KEY")
        )

    def _fetch_raw(
        self, instrument: Instrument, market: MarketConfig, since: datetime
    ) -> dict:
        url = LIST_URL.format(
            key=os.environ["DART_API_KEY"],
            corp_code=instrument.ids["dart_corp_code"],
            bgn_de=since.astimezone(KST).strftime("%Y%m%d"),
        )
        return http_get_json(url)

    def _transform(
        self,
        instrument: Instrument,
        payload: dict,
        market: MarketConfig,
        observed_at: datetime,
    ) -> list[RawItem]:
        if payload.get("status") != "000":
            return []  # DART error statuses degrade to an empty batch
        items: list[RawItem] = []
        for entry in payload.get("list", []):
            rcept_no = entry.get("rcept_no")
            report_nm = entry.get("report_nm")
            rcept_dt = entry.get("rcept_dt")
            if not (rcept_no and report_nm and rcept_dt):
                continue
            # DART lists carry a date, not a time; midnight KST is the most
            # conservative (earliest) instant for that filing date.
            event_time = datetime.strptime(rcept_dt, "%Y%m%d").replace(tzinfo=KST)
            items.append(
                RawItem(
                    id=f"dart:{rcept_no}",
                    source=self.name,
                    market_id=market.market_id,
                    lang="ko",
                    ticker_hints=[instrument.ticker],
                    text=report_nm,
                    url=VIEWER_URL.format(rcept_no=rcept_no),
                    event_time=event_time,
                    observed_at=observed_at,
                    meta={"rcept_no": rcept_no},
                )
            )
        return items


__all__ = ["DartAdapter"]
