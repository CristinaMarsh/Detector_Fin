"""Article schema and fixture loader for the publication layer (section 6.1).

An :class:`Article` is the unit of editorial content. In M10a articles are
authored as YAML fixtures under ``data/sample_articles/``; in M10b they will be
produced by the LLM writing layer. ``model_version`` and ``prompt_hash`` are
empty strings for fixture-authored articles and become mandatory (non-empty)
once an article is LLM-written.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..schemas import MarketId

DEFAULT_ARTICLES_DIR = Path(__file__).resolve().parents[3] / "data" / "sample_articles"

ArticleKind = Literal["morning_call", "brief", "weekly"]


class ArticleSource(BaseModel):
    """A cited source. ``url`` propagates verbatim (section 3 provenance)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    url: str


class Article(BaseModel):
    """One editorial article."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: ArticleKind
    market_id: MarketId
    ticker: str | None = None
    date_local: date
    lang: str = "zh-Hant"
    headline: str
    dek: str
    body_paragraphs: list[str] = Field(default_factory=list)
    sources: list[ArticleSource] = Field(default_factory=list)
    # Empty for fixture-authored articles; mandatory once LLM-written (M10b).
    model_version: str = ""
    prompt_hash: str = ""

    @model_validator(mode="after")
    def _provenance_generator_pair(self) -> "Article":
        # If one generation field is set, both must be: an LLM-written article
        # carries both its model version and prompt hash, never one alone.
        if bool(self.model_version) != bool(self.prompt_hash):
            raise ValueError(
                "model_version and prompt_hash must be set together "
                "(both empty for fixtures, both non-empty once LLM-written)"
            )
        return self


class ArticleError(Exception):
    """Raised when an article fixture is missing or invalid."""


def load_articles(articles_dir: Path | str | None = None) -> list[Article]:
    """Load every ``*.yaml`` article fixture, sorted by date then id.

    Sorting is deterministic so the generated site is idempotent.
    """
    articles_dir = (
        Path(articles_dir) if articles_dir is not None else DEFAULT_ARTICLES_DIR
    )
    if not articles_dir.exists():
        raise ArticleError(f"articles directory not found: {articles_dir}")
    articles: list[Article] = []
    seen: set[str] = set()
    for path in sorted(articles_dir.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        try:
            article = Article.model_validate(raw)
        except Exception as exc:
            raise ArticleError(f"invalid article fixture {path}: {exc}") from exc
        if article.id in seen:
            raise ArticleError(f"duplicate article id: {article.id}")
        seen.add(article.id)
        articles.append(article)
    if not articles:
        raise ArticleError(f"no article fixtures found in {articles_dir}")
    # Newest first, id as tiebreaker -- stable and deterministic.
    articles.sort(key=lambda a: (a.date_local, a.id), reverse=True)
    return articles


__all__ = [
    "Article",
    "ArticleSource",
    "ArticleKind",
    "ArticleError",
    "DEFAULT_ARTICLES_DIR",
    "load_articles",
]
