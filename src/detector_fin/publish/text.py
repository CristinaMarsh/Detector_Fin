"""Text helpers for the publication layer.

Simplified-to-Traditional conversion via OpenCC is an optional build-time
normalisation (section 6.2). OpenCC lives in the optional ``publish`` extra, so
this module degrades to identity when it is not installed -- fixture content is
authored in Traditional, so output is correct either way. URLs are never
converted.
"""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _converter():
    """Return an OpenCC s2t converter, or ``None`` if OpenCC is unavailable."""
    try:
        from opencc import OpenCC
    except Exception:
        return None
    for config in ("s2t", "s2t.json", "s2twp"):
        try:
            return OpenCC(config)
        except Exception:
            continue
    return None


def to_traditional(text: str) -> str:
    """Convert Simplified Chinese to Traditional, or return text unchanged.

    Idempotent on Traditional input. Only display strings are passed here;
    URLs and code identifiers are not.
    """
    converter = _converter()
    if converter is None or not text:
        return text
    try:
        return converter.convert(text)
    except Exception:
        return text


def opencc_available() -> bool:
    return _converter() is not None


__all__ = ["to_traditional", "opencc_available"]
