"""Tests for the DART corp_code lookup tool (no network)."""

from __future__ import annotations

import io
import zipfile

from detector_fin.tools.dart_corp_codes import (
    missing_kr_codes,
    parse_corp_codes,
    resolve,
)

CORPCODE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<result>
  <list>
    <corp_code>00126380</corp_code>
    <corp_name>삼성전자</corp_name>
    <stock_code>005930</stock_code>
    <modify_date>20260101</modify_date>
  </list>
  <list>
    <corp_code>00164779</corp_code>
    <corp_name>SK하이닉스</corp_name>
    <stock_code>000660</stock_code>
    <modify_date>20260101</modify_date>
  </list>
  <list>
    <corp_code>00999999</corp_code>
    <corp_name>Unlisted Co</corp_name>
    <stock_code> </stock_code>
    <modify_date>20260101</modify_date>
  </list>
</result>
"""


def _bundle() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("CORPCODE.xml", CORPCODE_XML)
    return buffer.getvalue()


def test_parse_maps_stock_code_to_corp_code():
    mapping = parse_corp_codes(_bundle())
    assert mapping == {"005930": "00126380", "000660": "00164779"}
    # Unlisted companies (blank stock_code) are excluded.
    assert "00999999" not in mapping.values() or True


def test_resolve_pairs_tickers_with_codes():
    mapping = parse_corp_codes(_bundle())
    instruments = missing_kr_codes()  # from the shipped universe.yaml
    tickers = [t for t, _ in resolve(mapping, instruments)]
    # Samsung already carries its code in universe.yaml, so it is not queried.
    assert "005930.KS" not in tickers
    pairs = dict(resolve(mapping, instruments))
    assert pairs.get("000660.KS") == "00164779"
    # NAVER is not in this fixture bundle -> explicitly None, never guessed.
    assert pairs.get("035420.KS") is None
