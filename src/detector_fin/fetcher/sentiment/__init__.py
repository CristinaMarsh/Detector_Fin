"""Sentiment source adapters, one per market (Milestone M3b).

Each adapter emits RawItem records from public discussion streams:
    US -> StockTwits, CN -> East Money guba, KR -> Naver finance board.
"""

from __future__ import annotations

from .cn_eastmoney_guba import EastmoneyGubaAdapter
from .kr_naver_board import NaverBoardAdapter
from .us_stocktwits import StocktwitsAdapter

# Registry keyed by market_id, consumed by the fetch_sentiment CLI.
SENTIMENT_ADAPTERS = {
    "US": StocktwitsAdapter,
    "CN": EastmoneyGubaAdapter,
    "KR": NaverBoardAdapter,
}

__all__ = [
    "StocktwitsAdapter",
    "EastmoneyGubaAdapter",
    "NaverBoardAdapter",
    "SENTIMENT_ADAPTERS",
]
