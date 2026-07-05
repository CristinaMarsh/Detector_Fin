"""US disclosure adapter: SEC EDGAR submissions API.

Fetches recent filing metadata per company from
``https://data.sec.gov/submissions/CIK##########.json`` and emits one RawItem
per filing of interest. The SEC fair-access policy requires a descriptive
User-Agent with contact information; supply it via the
``SEC_EDGAR_USER_AGENT`` environment variable (see .env.example).

Instruments must carry ``ids.edgar_cik`` (zero-padded 10-digit CIK); those
without it are skipped.
"""

from __future__ import annotations

import os
from datetime import datetime

from ...market_config import MarketConfig
from ...schemas import RawItem
from ...universe import Instrument
from .base import USER_AGENT_FALLBACK, BaseDisclosureAdapter, http_get_json

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
FILING_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{document}"
)

# Filing forms surfaced to the pipeline. Metadata only; no document bodies.
FORMS_OF_INTEREST = {"10-K", "10-Q", "8-K", "20-F", "6-K"}


class SecEdgarAdapter(BaseDisclosureAdapter):
    name = "sec_edgar"

    def _supports(self, instrument: Instrument) -> bool:
        return "edgar_cik" in instrument.ids

    def _fetch_raw(
        self, instrument: Instrument, market: MarketConfig, since: datetime
    ) -> dict:
        cik = instrument.ids["edgar_cik"]
        headers = {
            "User-Agent": os.environ.get("SEC_EDGAR_USER_AGENT", USER_AGENT_FALLBACK)
        }
        return http_get_json(SUBMISSIONS_URL.format(cik=cik), headers=headers)

    def _transform(
        self,
        instrument: Instrument,
        payload: dict,
        market: MarketConfig,
        observed_at: datetime,
    ) -> list[RawItem]:
        recent = payload.get("filings", {}).get("recent", {})
        if not recent:
            return []
        cik = instrument.ids["edgar_cik"]
        cik_int = int(cik)
        items: list[RawItem] = []
        rows = zip(
            recent.get("accessionNumber", []),
            recent.get("form", []),
            recent.get("acceptanceDateTime", []),
            recent.get("primaryDocument", []),
            recent.get("primaryDocDescription", []),
            recent.get("filingDate", []),
        )
        for accession, form, accepted_at, document, description, filing_date in rows:
            if form not in FORMS_OF_INTEREST:
                continue
            event_time = datetime.fromisoformat(accepted_at)
            url = FILING_URL.format(
                cik_int=cik_int,
                accession_nodash=accession.replace("-", ""),
                document=document,
            )
            items.append(
                RawItem(
                    id=f"sec_edgar:{accession}",
                    source=self.name,
                    market_id=market.market_id,
                    lang="en",
                    ticker_hints=[instrument.ticker],
                    text=f"{form}: {description or form} (filed {filing_date})",
                    url=url,
                    event_time=event_time,
                    observed_at=observed_at,
                    meta={"form": form, "accession": accession, "cik": cik},
                )
            )
        return items


__all__ = ["SecEdgarAdapter", "FORMS_OF_INTEREST"]
