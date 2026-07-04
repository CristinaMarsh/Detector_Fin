"""Site configuration for the publication layer (section 6.2)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

DEFAULT_SITE_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "site.yaml"


class SiteConfig(BaseModel):
    """Static-site configuration loaded from ``config/site.yaml``."""

    model_config = ConfigDict(extra="forbid")

    site_title: str
    locale: str = "zh-Hant"
    base_url: str
    disclaimer_key: str


class SiteConfigError(Exception):
    """Raised when the site config is missing or invalid."""


def load_site_config(path: Path | str | None = None) -> SiteConfig:
    path = Path(path) if path is not None else DEFAULT_SITE_CONFIG_PATH
    if not path.exists():
        raise SiteConfigError(f"site config not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    try:
        return SiteConfig.model_validate(raw)
    except Exception as exc:
        raise SiteConfigError(f"invalid site config {path}: {exc}") from exc


__all__ = [
    "SiteConfig",
    "SiteConfigError",
    "DEFAULT_SITE_CONFIG_PATH",
    "load_site_config",
]
