"""Market abstraction: ``MarketConfig`` model and YAML loader (section 0).

Every market the pipeline runs is described by a ``MarketConfig`` loaded from
``config/markets/<market_id>.yaml``. Markets are isolated at runtime but share
this code and these schemas. All thresholds the Judge uses come from
``label_params`` so the same code runs every market.

Cross-currency conversion is explicitly out of scope here: returns and labels
are computed in local currency, and cross-market comparison happens only at the
evaluation layer via z-scored quantities.
"""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .schemas import MarketId

# Repo-root default: <repo>/config/markets. Resolved relative to this file so it
# works regardless of the process working directory.
DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "markets"


class LabelParams(BaseModel):
    """Per-market thresholds for the section-4 evaluation labels.

    Defaults match the contract (k=5, d=0.10, j=3). Any field may be overridden
    per market in YAML. ``rv_percentile`` is the trailing percentile for label
    component (a); ``suspension_is_event`` toggles component (e), which only
    applies to markets that halt (CN).
    """

    model_config = ConfigDict(extra="forbid")

    k: int = Field(default=5, gt=0)  # forward horizon in trading days
    d: float = Field(default=0.10, gt=0.0)  # drawdown threshold
    j: float = Field(default=3.0, gt=0.0)  # return-jump sigma multiple (US)
    rv_percentile: float = Field(default=0.95, gt=0.0, lt=1.0)  # label (a)
    limit_hit_is_event: bool = True  # label (d) -- CN, KR
    suspension_is_event: bool = True  # label (e) -- CN


class MarketConfig(BaseModel):
    """Full runtime description of one market."""

    model_config = ConfigDict(extra="forbid")

    market_id: MarketId
    timezone: str
    trading_calendar: str  # exchange_calendars id: XNYS, XSHG, XKRX
    decision_time_local: time  # pre-open, local tz
    currency: str
    # None for US; {"main":0.10,"star_chinext":0.20,"st":0.05} for CN;
    # {"all":0.30} for KR.
    price_limit: dict[str, float] | None = None
    ticker_suffixes: list[str] = Field(default_factory=list)
    sentiment_sources: list[str] = Field(default_factory=list)
    label_params: LabelParams = Field(default_factory=LabelParams)

    @field_validator("decision_time_local", mode="before")
    @classmethod
    def _parse_time(cls, v: object) -> object:
        # Accept "08:30" / "08:30:00" strings as well as datetime.time.
        if isinstance(v, str):
            return time.fromisoformat(v)
        return v

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {v!r}") from exc
        return v

    @model_validator(mode="after")
    def _validate_calendar(self) -> "MarketConfig":
        # Validate the calendar id lazily; exchange_calendars is heavy to import
        # and not always needed just to read a config.
        try:
            import exchange_calendars as xcals
        except ImportError:
            return self
        if self.trading_calendar not in xcals.get_calendar_names():
            raise ValueError(
                f"unknown trading_calendar {self.trading_calendar!r} for "
                f"market {self.market_id}"
            )
        return self

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def decision_datetime_local(self, on: date) -> datetime:
        """Local-timezone decision instant for a given calendar date."""
        return datetime.combine(on, self.decision_time_local, tzinfo=self.tzinfo)

    def decision_datetime_utc(self, on: date) -> datetime:
        """UTC decision instant. Features may only use data with
        ``observed_at`` strictly before this instant (section 3)."""
        from datetime import timezone as _tz

        return self.decision_datetime_local(on).astimezone(_tz.utc)


class MarketConfigError(Exception):
    """Raised when a market config file is missing or invalid."""


def _config_path(market_id: str, config_dir: Path) -> Path:
    return config_dir / f"{market_id.lower()}.yaml"


def load_market_config(
    market_id: str, config_dir: Path | str | None = None
) -> MarketConfig:
    """Load and validate a single market's config by id (case-insensitive)."""
    config_dir = Path(config_dir) if config_dir is not None else DEFAULT_CONFIG_DIR
    path = _config_path(market_id, config_dir)
    if not path.exists():
        raise MarketConfigError(f"no config for market {market_id!r} at {path}")
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    try:
        return MarketConfig.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError et al.
        raise MarketConfigError(f"invalid config at {path}: {exc}") from exc


def load_all_market_configs(
    config_dir: Path | str | None = None,
) -> dict[str, MarketConfig]:
    """Load every ``*.yaml`` under ``config_dir``, keyed by ``market_id``."""
    config_dir = Path(config_dir) if config_dir is not None else DEFAULT_CONFIG_DIR
    if not config_dir.exists():
        raise MarketConfigError(f"config dir does not exist: {config_dir}")
    configs: dict[str, MarketConfig] = {}
    for path in sorted(config_dir.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        try:
            cfg = MarketConfig.model_validate(raw)
        except Exception as exc:
            raise MarketConfigError(f"invalid config at {path}: {exc}") from exc
        if cfg.market_id in configs:
            raise MarketConfigError(f"duplicate market_id {cfg.market_id} in {path}")
        configs[cfg.market_id] = cfg
    return configs


__all__ = [
    "LabelParams",
    "MarketConfig",
    "MarketConfigError",
    "DEFAULT_CONFIG_DIR",
    "load_market_config",
    "load_all_market_configs",
]
