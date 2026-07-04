"""Contract tests for the dashboard display-layer payload.

``docs/dashboard.json`` is the data the static dashboard (``docs/index.html``)
renders. It is a published deliverable, so we validate its shape here rather
than trusting it by hand. These tests are pure file reads: no network calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DASHBOARD_PATH = Path(__file__).resolve().parents[1] / "docs" / "dashboard.json"

VALID_MARKETS = {"US", "CN", "KR"}


@pytest.fixture(scope="module")
def payload() -> dict:
    with DASHBOARD_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_dashboard_file_exists():
    assert DASHBOARD_PATH.is_file(), f"missing dashboard payload at {DASHBOARD_PATH}"


def test_parses_as_json(payload):
    assert isinstance(payload, dict)


def test_top_level_keys_present(payload):
    for key in ("generated_at", "pipeline_status", "kpi", "entries"):
        assert key in payload, f"missing top-level key: {key}"
    assert isinstance(payload["entries"], list)
    assert payload["entries"], "entries must not be empty"


def test_every_entry_has_required_fields(payload):
    required = (
        "ticker",
        "name",
        "market_id",
        "score",
        "sentiment_z",
        "flags",
        "claims",
        "sources",
    )
    for i, entry in enumerate(payload["entries"]):
        for field in required:
            assert field in entry, f"entry[{i}] missing field: {field}"


def test_market_ids_are_valid(payload):
    for i, entry in enumerate(payload["entries"]):
        assert entry["market_id"] in VALID_MARKETS, (
            f"entry[{i}] has invalid market_id: {entry['market_id']!r}"
        )


def test_scores_in_unit_interval(payload):
    for i, entry in enumerate(payload["entries"]):
        score = entry["score"]
        assert isinstance(score, (int, float)) and not isinstance(score, bool), (
            f"entry[{i}] score is not numeric: {score!r}"
        )
        assert 0.0 <= score <= 1.0, f"entry[{i}] score out of [0, 1]: {score}"


def test_sentiment_z_is_numeric(payload):
    for i, entry in enumerate(payload["entries"]):
        z = entry["sentiment_z"]
        assert isinstance(z, (int, float)) and not isinstance(z, bool), (
            f"entry[{i}] sentiment_z is not numeric: {z!r}"
        )


def test_list_fields_are_lists(payload):
    for i, entry in enumerate(payload["entries"]):
        for field in ("flags", "claims", "sources"):
            assert isinstance(entry[field], list), (
                f"entry[{i}] field {field} is not a list"
            )


def test_every_source_has_title_and_https_url(payload):
    for i, entry in enumerate(payload["entries"]):
        for j, source in enumerate(entry["sources"]):
            assert "title" in source and "url" in source, (
                f"entry[{i}].sources[{j}] missing title or url"
            )
            title = source["title"]
            url = source["url"]
            assert isinstance(title, str) and title.strip(), (
                f"entry[{i}].sources[{j}] has empty title"
            )
            assert isinstance(url, str) and url.startswith("https://"), (
                f"entry[{i}].sources[{j}] url is not https: {url!r}"
            )
