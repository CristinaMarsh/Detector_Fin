"""Language-aware near-duplicate removal (section 1.2).

Uses character n-gram Jaccard similarity, which works uniformly across
English, Chinese and Korean text without tokenisers: CJK characters carry
enough information per character that 3-grams discriminate well, and the
comparison is only ever applied within one language (items are grouped by
``lang`` first). Deterministic and dependency-free -- a minhash-family
approximation is unnecessary at pilot-universe volumes; the interface stays
the same if one is swapped in later.
"""

from __future__ import annotations

import re
from collections import defaultdict

from ..schemas import RawItem

_NON_WORD = re.compile(r"[\W_]+", re.UNICODE)

DEFAULT_THRESHOLD = 0.8
NGRAM = 3


def _shingles(text: str, n: int = NGRAM) -> frozenset[str]:
    normalised = _NON_WORD.sub("", text.lower())
    if len(normalised) < n:
        return frozenset({normalised} if normalised else set())
    return frozenset(normalised[i : i + n] for i in range(len(normalised) - n + 1))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def dedup_items(
    items: list[RawItem], threshold: float = DEFAULT_THRESHOLD
) -> list[RawItem]:
    """Drop near-duplicates, keeping the earliest ``event_time`` per cluster.

    Comparison happens within one language only. Input order is preserved for
    the survivors.
    """
    by_lang: dict[str, list[RawItem]] = defaultdict(list)
    for item in items:
        by_lang[item.lang].append(item)

    dropped: set[str] = set()
    for lang_items in by_lang.values():
        # Earliest first so the earliest observation survives its cluster.
        ordered = sorted(lang_items, key=lambda i: (i.event_time, i.id))
        kept: list[tuple[frozenset[str], RawItem]] = []
        for item in ordered:
            shingles = _shingles(item.text)
            if any(_jaccard(shingles, seen) >= threshold for seen, _ in kept):
                dropped.add(item.id)
            else:
                kept.append((shingles, item))
    return [item for item in items if item.id not in dropped]


__all__ = ["dedup_items", "DEFAULT_THRESHOLD"]
