"""Contract tests for the publication site generator (Design Contract section 6).

The generator is rendered into a temporary copy of ``docs/`` (so the moved
``panel.html`` and locale files are present) and the output is checked against
the section 6.3 rendering guardrails. No network calls.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from detector_fin.publish.article import load_articles
from detector_fin.publish.generator import build_site, load_locale
from detector_fin.publish.site_config import load_site_config

REPO_DOCS = Path(__file__).resolve().parents[1] / "docs"

# Internal schema tokens that must never leak into rendered HTML (section 6.3).
FORBIDDEN_TOKENS = [
    "observed_at",
    "prompt_hash",
    "model_version",
    "text_original",
    "sentiment_z",
    "instrument_type",
]

# Links that are not internal page references and need not resolve to a file.
_EXTERNAL_PREFIXES = ("http://", "https://", "#", "mailto:")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Render the site into a temp copy of docs/. Returns (out_dir, pages)."""
    out_dir = tmp_path_factory.mktemp("site") / "docs"
    shutil.copytree(REPO_DOCS, out_dir)
    pages = build_site(out_dir, locale_dir=out_dir / "i18n")
    return out_dir, pages


def test_generator_is_idempotent(built):
    out_dir, pages = built
    before = {p: p.read_bytes() for p in pages}
    build_site(out_dir, locale_dir=out_dir / "i18n")
    after = {p: p.read_bytes() for p in pages}
    assert before == after


def test_no_internal_tokens_in_rendered_html(built):
    _, pages = built
    for page in pages:
        html = page.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            assert token not in html, f"token {token!r} leaked into {page.name}"


def test_every_article_page_has_exact_https_source_link(built):
    out_dir, _ = built
    articles = load_articles()
    for article in articles:
        page = out_dir / "articles" / f"{article.id}.html"
        assert page.exists(), f"missing article page for {article.id}"
        html = page.read_text(encoding="utf-8")
        https = [s for s in article.sources if s.url.startswith("https://")]
        assert https, f"article {article.id} has no https source in fixture"
        # At least one source url appears verbatim as an href.
        assert any(f'href="{s.url}"' in html for s in https), (
            f"no verbatim https source href in {page.name}"
        )


def test_disclaimer_on_every_page(built):
    out_dir, pages = built
    site = load_site_config()
    locale = load_locale(site.locale, out_dir / "i18n")
    disclaimer = locale[site.disclaimer_key]
    for page in pages:
        html = page.read_text(encoding="utf-8")
        assert disclaimer in html, f"disclaimer missing from {page.name}"


def test_sample_articles_are_fixture_authored():
    # Fixtures carry empty generation fields; both become mandatory in M10b.
    for article in load_articles():
        assert article.model_version == ""
        assert article.prompt_hash == ""


def test_article_generation_fields_must_pair():
    from detector_fin.publish.article import Article

    base = dict(
        id="x",
        kind="brief",
        market_id="US",
        date_local="2026-07-03",
        headline="h",
        dek="d",
    )
    # One generation field without the other is rejected.
    with pytest.raises(Exception):
        Article(**base, model_version="llm-1", prompt_hash="")
    with pytest.raises(Exception):
        Article(**base, model_version="", prompt_hash="abc")
    # Both set together is fine (an LLM-written article).
    ok = Article(**base, model_version="llm-1", prompt_hash="abc")
    assert ok.model_version == "llm-1"


def test_front_page_internal_links_resolve(built):
    out_dir, _ = built
    index = out_dir / "index.html"
    hrefs = re.findall(r'href="([^"]+)"', index.read_text(encoding="utf-8"))
    internal = [h for h in hrefs if not h.startswith(_EXTERNAL_PREFIXES)]
    assert internal, "front page has no internal links"
    for href in internal:
        target = (out_dir / href).resolve()
        assert target.exists(), f"broken internal link on front page: {href}"
