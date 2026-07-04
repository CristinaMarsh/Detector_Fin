"""Publication layer: static editorial site generator (Design Contract section 6).

M10a renders fixture-authored articles into a static site under ``docs/``. The
LLM writing layer (M10b) will author :class:`Article` objects from snapshots;
this package is designed for that but does not implement it.
"""

from __future__ import annotations

from .article import Article, ArticleSource, load_articles
from .generator import SiteGenerator, build_site
from .site_config import SiteConfig, load_site_config

__all__ = [
    "Article",
    "ArticleSource",
    "load_articles",
    "SiteConfig",
    "load_site_config",
    "SiteGenerator",
    "build_site",
]
