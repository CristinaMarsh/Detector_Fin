"""Detector_Fin: daily multi-market equity risk assessment.

Public surface: authoritative schemas, the market abstraction
(``MarketConfig`` + loader), the universe registry, the market-data fetcher,
and the append-only parquet storage layer.
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
    InstrumentType,
    MarketBar,
    MarketStats,
    RawItem,
    RiskScore,
    StorageRecord,
    TickerDaySnapshot,
)
from .storage import ParquetStore
from .universe import (
    DEFAULT_UNIVERSE_PATH,
    Instrument,
    UniverseError,
    load_universe,
    universe_for_market,
)

__version__ = "0.2.2"

__all__ = [
    "__version__",
    # schemas
    "StorageRecord",
    "RawItem",
    "MarketBar",
    "Fragment",
    "MarketStats",
    "TickerDaySnapshot",
    "RiskScore",
    "EvidenceDossier",
    "InstrumentType",
    # market config
    "MarketConfig",
    "LabelParams",
    "MarketConfigError",
    "DEFAULT_CONFIG_DIR",
    "load_market_config",
    "load_all_market_configs",
    # universe
    "Instrument",
    "UniverseError",
    "DEFAULT_UNIVERSE_PATH",
    "load_universe",
    "universe_for_market",
    # storage
    "ParquetStore",
]
