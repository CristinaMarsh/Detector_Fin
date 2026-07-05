"""Pluggable fragment translation (section 1.2).

Fragments are stored in the original language plus an English rendering for
the human reviewer. Real machine translation arrives with the M10b LLM layer;
until then :class:`IdentityTranslator` copies the original text through and
says so in its version string, so stored snapshots are honest about which
translator produced ``text_en``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..schemas import Lang


@runtime_checkable
class Translator(Protocol):
    version: str

    def to_english(self, text: str, lang: Lang) -> str: ...


class IdentityTranslator:
    """Pass-through placeholder: text_en == text_original for non-English."""

    version = "identity-0.1"

    def to_english(self, text: str, lang: Lang) -> str:
        return text


__all__ = ["Translator", "IdentityTranslator"]
