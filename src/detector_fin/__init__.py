"""Detector_Fin: daily multi-market equity risk assessment.

Public surface for milestone M1: authoritative schemas, the market abstraction
(``MarketConfig`` + loader), and the append-only parquet storage layer.
"""

from __future__ import annotations

from .market_config import (
    DEFAULT_CONFIG_DIR,
    LabelParams,
    MarketConfig,
    MarketConfigError,
    load_all_market_configs,
    load_market_config,
)
from .schemas import (
    EvidenceDossier,
    Fragment,
    MarketStats,
    RawItem,
    RiskScore,
    StorageRecord,
    TickerDaySnapshot,
)
from .storage import ParquetStore

__version__ = "0.2.0"

__all__ = [
    "__version__",
    # schemas
    "StorageRecord",
    "RawItem",
    "Fragment",
    "MarketStats",
    "TickerDaySnapshot",
    "RiskScore",
    "EvidenceDossier",
    # market config
    "MarketConfig",
    "LabelParams",
    "MarketConfigError",
    "DEFAULT_CONFIG_DIR",
    "load_market_config",
    "load_all_market_configs",
    # storage
    "ParquetStore",
]
