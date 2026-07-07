"""Tests unitaires pour le parseur CSV Boursobank."""

import pytest

from src.logic.statement_parser import (
    _parse_amount,
    build_external_id,
    map_statement_transaction,
    parse_boursobank_csv,
)

_HEADER = (
    "dateOp;dateVal;label;suggestedLabel;category;categoryParent;"
    "amount;comment;accountNum;accountLabel;accountbalance\n"
)


def _make_csv(*rows: str) -> bytes:
    return (_HEADER + "\n".join(rows)).encode("utf-8")


def test_parse_single_transaction():
    csv_bytes = _make_csv(
        '2026-04-30;2026-04-30;"VIREMENT RECU COACHING";Coaching;Revenus;Revenus;'
        "500,00;;00040342194;BoursoBank;4170.39"
    )
    result = parse_boursobank_csv(csv_bytes)
    assert len(result) == 1
    assert result[0]["date"] == "2026-04-30"
    assert result[0]["amount"] == 500.0
    assert result[0]["label"] == "VIREMENT RECU COACHING"


def test_parse_negative_amount():
    csv_bytes = _make_csv(
        '2026-05-02;2026-05-02;"PRLVT URSSAF";URSSAF;Taxes;Charges;'
        "-212,00;;00040342194;BoursoBank;3958.39"
    )
    result = parse_boursobank_csv(csv_bytes)
    assert len(result) == 1
    assert result[0]["amount"] == -212.0


def test_parse_multiple_transactions():
    csv_bytes = _make_csv(
        '2026-04-30;2026-04-30;"TX A";;Cat;Parent;100,00;;000;BoursoBank;1000.00',
        '2026-04-29;2026-04-29;"TX B";;Cat;Parent;-50,00;;000;BoursoBank;900.00',
    )
    result = parse_boursobank_csv(csv_bytes)
    assert len(result) == 2


def test_parse_amount_french_decimal():
    assert _parse_amount("-0,86") == -0.86
    assert _parse_amount("1 234,56") == 1234.56
    assert _parse_amount("500,00") == 500.0


def test_parse_amount_invalid_returns_none():
    assert _parse_amount("invalid") is None
    assert _parse_amount("") is None


def test_date_already_iso():
    csv_bytes = _make_csv(
        '2026-04-30;2026-04-30;"TEST";;Cat;Parent;10,00;;000;BoursoBank;100.00'
    )
    result = parse_boursobank_csv(csv_bytes)
    assert result[0]["date"] == "2026-04-30"


def test_external_id_is_stable():
    id1 = build_external_id("2026-04-30", -0.86, "CARTE 26/04/26 Swile CB*7608")
    id2 = build_external_id("2026-04-30", -0.86, "CARTE 26/04/26 Swile CB*7608")
    assert id1 == id2


def test_external_id_format():
    ext_id = build_external_id("2026-04-30", -0.86, "SWILE")
    assert ext_id.startswith("bourso_")
    assert len(ext_id) == len("bourso_") + 16


def test_external_id_differs_on_amount_change():
    id1 = build_external_id("2026-04-30", -0.86, "SWILE")
    id2 = build_external_id("2026-04-30", -0.87, "SWILE")
    assert id1 != id2


def test_empty_csv_returns_empty_list():
    result = parse_boursobank_csv(_HEADER.encode("utf-8"))
    assert result == []


def test_row_with_empty_amount_is_ignored():
    csv_bytes = _make_csv(
        '2026-04-30;2026-04-30;"TEST";;Cat;Parent;;;000;BoursoBank;100.00'
    )
    result = parse_boursobank_csv(csv_bytes)
    assert result == []


def test_row_with_invalid_amount_is_ignored():
    csv_bytes = _make_csv(
        '2026-04-30;2026-04-30;"TEST";;Cat;Parent;N/A;;000;BoursoBank;100.00'
    )
    result = parse_boursobank_csv(csv_bytes)
    assert result == []


def test_map_statement_transaction():
    raw = {"date": "2026-04-30", "amount": -0.86, "label": "SWILE"}
    tx = map_statement_transaction(raw, "personal")
    assert tx["source"] == "bank"
    assert tx["business_id"] == "personal"
    assert tx["category"] is None
    assert tx["external_id"].startswith("bourso_")
    assert tx["date"] == "2026-04-30"
    assert tx["amount"] == -0.86
    assert tx["notes"] is None


def test_map_statement_transaction_business_id():
    raw = {"date": "2026-05-01", "amount": 500.0, "label": "COACHING"}
    tx = map_statement_transaction(raw, "phi_rising")
    assert tx["business_id"] == "phi_rising"
