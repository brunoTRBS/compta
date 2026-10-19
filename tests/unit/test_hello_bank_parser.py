"""Tests du parseur de relevé Hello Bank (compte pro)."""

import pytest

from src.logic.statement_parser import (
    BANK_HELLO_BANK,
    UnknownStatementFormat,
    detect_bank,
    map_statement_transaction,
    parse_statement,
)

_HEADER = '"Compte de ch&egrave;ques";"Compte de ch&amp;egrave;ques";****9077;16/10/2026;;1 823,44'
_LINES = [
    "25/09/2025;VIREMENT;VIR SEPA RECU;VIR SEPA RECU /FRM STRIPE /EID ST-UXYGY6BLMWSD /RNF;25/09/2025;183,13",
    "26/09/2025;PAIEMENT CB;FACTURE CARTE;FACTURE CARTE DU 260925 TRAIN HEROIC, L CARTE   4396XXXXXXXX9042"
    "                USA    17,99USD;29/09/2025;-15,45",
    "01/10/2025;PAIEMENT CB;FACTURE CARTE;FACTURE CARTE DU 011025 IRSSAFRHONEALP  VENISSIEUX      "
    "CARTE   4396XXXXXXXX9042;02/10/2025;-560,00",
    "29/09/2025;PRELEVEMENT;PRLV SEPA;PRLV SEPA BASIC FIT FRANCE ECH/290925 ID EMETTEUR/FR10ZZZ642164 "
    "MDT/842009115;29/09/2025;-34,99",
    "02/10/2025;VIREMENT INSTANTANE EMIS;VIR SEPA INST EMIS;VIR SEPA INST EMIS /MOTIF LOYER COWORKING OCTOBRE "
    "/BEN MAXENCE PUPPO - LE MENTORAT SAS /REFDO 6006 /REF NOTPROVIDED;02/10/2025;-240,00",
    "02/10/2025;COMMISSIONS;COMMISSIONS;COMMISSIONS HELLO BUSINESS FACTURE NUMERO 20251001;10/10/2025;-11,50",
    "05/10/2026;VIREMENT;VIR SEPA RECU;VIR SEPA RECU /FRM X /EID Y /RNF Z;05/10/2026;1 024,15",
    "22/10/2025;PAIEMENT CB;FACTURE CARTE;FACTURE CARTE DU 221025 LPA             LYON            "
    "CARTE   4396XXXXXXXX9042;23/10/2025;-1,00",
    "22/10/2025;PAIEMENT CB;FACTURE CARTE;FACTURE CARTE DU 221025 LPA             LYON            "
    "CARTE   4396XXXXXXXX9042;23/10/2025;-1,00",
]


def _csv() -> bytes:
    return "\n".join([_HEADER, *_LINES]).encode("cp1252")


def test_detected_without_column_header():
    assert detect_bank(_csv()) == BANK_HELLO_BANK


def test_parse_reads_account_dates_and_amounts():
    bank, rows = parse_statement(_csv(), "E2929077.csv")
    assert bank == BANK_HELLO_BANK
    assert len(rows) == 9
    assert {r["account_number"] for r in rows} == {"****9077"}
    assert rows[0]["date"] == "2025-09-25"
    assert rows[0]["amount"] == 183.13
    assert rows[1]["amount"] == -15.45  # carte en dollars : le montant débité en euros
    assert rows[6]["amount"] == 1024.15  # séparateur de milliers


def test_readable_labels_keep_raw_label():
    _, rows = parse_statement(_csv())
    labels = [r["suggested_label"] for r in rows]
    assert labels[0] == "Virement de STRIPE"
    assert labels[1] == "TRAIN HEROIC, L"
    assert labels[2] == "IRSSAFRHONEALP VENISSIEUX"
    assert labels[3] == "Prélèvement BASIC FIT FRANCE"
    assert labels[4] == "Virement vers MAXENCE PUPPO - LE MENTORAT SAS (LOYER COWORKING OCTOBRE)"
    assert labels[5] == "Commission Hello Business"
    assert "CARTE" in rows[1]["label"]  # libellé brut conservé


def test_closing_balance_on_last_operation_only():
    _, rows = parse_statement(_csv())
    assert [r["balance"] for r in rows[:-1]] == [None] * (len(rows) - 1)
    assert rows[-1]["balance"] == 1823.44


def test_identical_lines_get_distinct_external_ids():
    _, rows = parse_statement(_csv())
    ids = [r["external_id"] for r in rows]
    assert len(set(ids)) == len(ids)
    assert ids[0].startswith("hello_")


def test_mapped_transaction_uses_clean_label():
    _, rows = parse_statement(_csv())
    mapped = map_statement_transaction(rows[2], "phi_rising", "acc-1")
    assert mapped["label"] == "IRSSAFRHONEALP VENISSIEUX"
    assert mapped["raw_label"].startswith("FACTURE CARTE DU 011025")
    assert mapped["business_id"] == "phi_rising"


def test_unknown_file_still_rejected():
    with pytest.raises(UnknownStatementFormat):
        parse_statement(b"a;b;c\n1;2;3")
