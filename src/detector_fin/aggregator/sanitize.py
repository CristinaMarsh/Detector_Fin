"""Sanitisation boundary for text fragments (section 1.2).

Raw fetched text is untrusted input (prompt-injection risk). Any fragment
that survives into a snapshot passes through :func:`sanitize_text`, which
strips URLs, markup, control characters, and instruction-like injection
markers, then truncates to the fragment cap. This is defence in depth: the
primary protection remains that the LLM path only ever sees controlled
schemas, never raw scraped text.
"""

from __future__ import annotations

import re

from ..schemas import MAX_FRAGMENT_CHARS

_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_TAG = re.compile(r"<[^>]{0,200}>")
_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# Zero-width and control characters often used to smuggle content.
_CONTROL = re.compile("[\\x00-\\x1f\\x7f\\u200b-\\u200f\\u2028\\u2029\\ufeff]")
# Instruction-like injection markers; removed wherever they appear.
_INJECTION = re.compile(
    r"(?:ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?"
    r"|disregard\s+(?:all\s+)?(?:previous|prior)\s+\w+"
    r"|(?:^|\s)(?:system|assistant|user)\s*:"
    r"|<\|[^|]{0,40}\|>)",
    re.IGNORECASE,
)
_WHITESPACE = re.compile(r"\s+")


def sanitize_text(text: str, max_chars: int = MAX_FRAGMENT_CHARS) -> str:
    """Return ``text`` with URLs, markup, control chars and injection markers
    removed, whitespace collapsed, and length capped."""
    cleaned = _MARKDOWN_LINK.sub(r"\1", text)
    cleaned = _URL.sub(" ", cleaned)
    cleaned = _TAG.sub(" ", cleaned)
    cleaned = _CONTROL.sub("", cleaned)
    cleaned = _INJECTION.sub(" ", cleaned)
    cleaned = _WHITESPACE.sub(" ", cleaned).strip()
    return cleaned[:max_chars]


__all__ = ["sanitize_text"]
