"""Static site generator for the publication layer (section 6.2, 6.3).

Renders fixture-authored articles into a self-contained editorial site under an
output directory (``docs/`` in production). Rendering is deterministic and
idempotent: the same inputs always produce the same bytes, so the generated
site can be committed and re-generated without spurious diffs.
"""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .article import Article, load_articles
from .site_config import SiteConfig, load_site_config
from .text import to_traditional

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "docs"
DEFAULT_LOCALE_DIR = DEFAULT_OUTPUT_DIR / "i18n"

# Desk order is fixed so the site is deterministic.
DESKS = [
    {"id": "US", "slug": "us"},
    {"id": "CN", "slug": "cn"},
    {"id": "KR", "slug": "kr"},
]


class SiteGenerator:
    """Renders a :class:`SiteConfig` + locale + articles into static HTML."""

    def __init__(
        self,
        site_config: SiteConfig,
        locale: dict,
        articles: list[Article],
        output_dir: Path | str,
    ):
        self.site = site_config
        self.locale = locale
        self.articles = articles
        self.output_dir = Path(output_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["t2t"] = to_traditional
        self.disclaimer = locale[site_config.disclaimer_key]

    # -- grouping helpers ----------------------------------------------------

    def _desks(self) -> list[dict]:
        return [
            {"id": d["id"], "slug": d["slug"], "name": self.locale[f"desk_{d['id']}"]}
            for d in DESKS
        ]

    def _by_kind(self, kind: str, market_id: str | None = None) -> list[Article]:
        return [
            a
            for a in self.articles
            if a.kind == kind and (market_id is None or a.market_id == market_id)
        ]

    def _base_context(self, root: str) -> dict:
        return {
            "site": self.site,
            "t": self.locale,
            "disclaimer": self.disclaimer,
            "desks": self._desks(),
            "root": root,
        }

    # -- rendering -----------------------------------------------------------

    def render(self) -> list[Path]:
        """Render the whole site. Returns the generated file paths (sorted)."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "articles").mkdir(parents=True, exist_ok=True)

        written: list[Path] = []
        written.append(self._render_front())
        for desk in self._desks():
            written.append(self._render_desk(desk))
        written.append(self._render_about())
        for article in self.articles:
            written.append(self._render_article(article))
        return sorted(written)

    def _write(self, rel_path: str, html: str) -> Path:
        path = self.output_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return path

    def _render_front(self) -> Path:
        ctx = self._base_context(root="")
        ctx.update(
            {
                "morning_calls": self._by_kind("morning_call"),
                "desk_briefs": [
                    {"desk": d, "briefs": self._by_kind("brief", d["id"])}
                    for d in self._desks()
                ],
                "trending": [a for a in self.articles if a.kind == "brief"],
            }
        )
        return self._write(
            "index.html", self.env.get_template("front.html").render(ctx)
        )

    def _render_desk(self, desk: dict) -> Path:
        ctx = self._base_context(root="")
        ctx.update(
            {
                "desk": desk,
                "morning_calls": self._by_kind("morning_call", desk["id"]),
                "briefs": self._by_kind("brief", desk["id"]),
            }
        )
        return self._write(
            f"desk-{desk['slug']}.html", self.env.get_template("desk.html").render(ctx)
        )

    def _render_about(self) -> Path:
        ctx = self._base_context(root="")
        return self._write(
            "about.html", self.env.get_template("about.html").render(ctx)
        )

    def _render_article(self, article: Article) -> Path:
        ctx = self._base_context(root="../")
        desk_name = self.locale[f"desk_{article.market_id}"]
        kind_label = self.locale[f"kind_{article.kind}"]
        ctx.update({"a": article, "desk_name": desk_name, "kind_label": kind_label})
        return self._write(
            f"articles/{article.id}.html",
            self.env.get_template("article.html").render(ctx),
        )


def load_locale(locale: str, locale_dir: Path | str | None = None) -> dict:
    """Load a publication locale file (``docs/i18n/<locale>.json``)."""
    locale_dir = Path(locale_dir) if locale_dir is not None else DEFAULT_LOCALE_DIR
    path = locale_dir / f"{locale}.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_site(
    output_dir: Path | str | None = None,
    *,
    site_config_path: Path | str | None = None,
    articles_dir: Path | str | None = None,
    locale_dir: Path | str | None = None,
) -> list[Path]:
    """Load config, locale and article fixtures, render the site. Idempotent."""
    site = load_site_config(site_config_path)
    locale = load_locale(site.locale, locale_dir)
    articles = load_articles(articles_dir)
    out = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    return SiteGenerator(site, locale, articles, out).render()


__all__ = [
    "SiteGenerator",
    "load_locale",
    "build_site",
    "TEMPLATES_DIR",
    "DEFAULT_OUTPUT_DIR",
    "DESKS",
]
