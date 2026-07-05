"""CLI: look up DART corp_codes for KR universe instruments.

Usage::

    python -m detector_fin.tools.dart_corp_codes

Downloads DART's official corpCode.xml bundle (a ZIP containing CORPCODE.xml),
matches its entries against the KR instruments in ``config/universe.yaml`` by
6-digit stock code, and prints the ``ids: { dart_corp_code: ... }`` lines to
paste into the universe file for any instrument still missing a code.

The tool prints rather than rewrites: ``universe.yaml`` carries curated
comments and hand-edited layout, and codes must stay reviewable in a diff
(Design Contract v0.3.1: identifiers come from the official corpCode.xml,
never guessed). Requires ``DART_API_KEY`` in the environment.
"""

from __future__ import annotations

import io
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from ..universe import Instrument, universe_for_market

CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={key}"


def download_corp_code_zip(api_key: str, timeout: float = 60.0) -> bytes:
    """Download the official corpCode ZIP bundle from OpenDART."""
    url = CORP_CODE_URL.format(key=api_key)
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def parse_corp_codes(zip_bytes: bytes) -> dict[str, str]:
    """Map 6-digit stock codes to 8-digit corp_codes from the ZIP bundle.

    Unlisted companies (empty/blank stock_code) are skipped.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as bundle:
        xml_bytes = bundle.read("CORPCODE.xml")
    mapping: dict[str, str] = {}
    for element in ET.fromstring(xml_bytes).iter("list"):
        stock_code = (element.findtext("stock_code") or "").strip()
        corp_code = (element.findtext("corp_code") or "").strip()
        if stock_code and corp_code:
            mapping[stock_code] = corp_code
    return mapping


def missing_kr_codes(
    universe_path: Path | str | None = None,
) -> list[Instrument]:
    """KR instruments that still lack ``ids.dart_corp_code``."""
    return [
        inst
        for inst in universe_for_market("KR", universe_path)
        if "dart_corp_code" not in inst.ids
    ]


def resolve(
    mapping: dict[str, str], instruments: list[Instrument]
) -> list[tuple[str, str | None]]:
    """Pair each instrument ticker with its corp_code, or None if absent."""
    results: list[tuple[str, str | None]] = []
    for inst in instruments:
        stock_code = inst.ticker.split(".", 1)[0]
        results.append((inst.ticker, mapping.get(stock_code)))
    return results


def main(argv: list[str] | None = None) -> int:
    api_key = os.environ.get("DART_API_KEY")
    if not api_key:
        print("DART_API_KEY is not set; see .env.example.", file=sys.stderr)
        return 1
    instruments = missing_kr_codes()
    if not instruments:
        print("All KR instruments already carry a dart_corp_code.")
        return 0
    mapping = parse_corp_codes(download_corp_code_zip(api_key))
    print("Paste into the matching entries of config/universe.yaml:")
    for ticker, corp_code in resolve(mapping, instruments):
        if corp_code is None:
            print(f"  {ticker}: NOT FOUND in official corpCode.xml")
        else:
            print(f'  {ticker}: ids: {{ dart_corp_code: "{corp_code}" }}')
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
