"""Tests unitaires pour le parseur CSV Boursobank."""


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


# ---------------------------------------------------------------------------
# Nouveau format BoursoBank (en-têtes français, deux colonnes "Solde")
# ---------------------------------------------------------------------------
from src.logic.statement_parser import (  # noqa: E402
    BANK_BOURSOBANK,
    BANK_CREDIT_MUTUEL,
    UnknownStatementFormat,
    account_number_from_filename,
    detect_bank,
    parse_credit_mutuel_csv,
    parse_statement,
)

_BOURSO_FR_HEADER = (
    '"Date Opération";"Date Valeur";Libellé;"Libellé Suggéré";Catégorie;'
    '"Catégorie Parente";Solde;Commentaire;"Numéro Compte";"Libellé Compte";Solde;Pointage\n'
)


def _bourso_fr(*rows: str) -> bytes:
    return (_BOURSO_FR_HEADER + "\n".join(rows)).encode("utf-8")


def test_bourso_fr_reads_amount_not_balance():
    """La 1re colonne "Solde" est le montant, la 2e le solde du compte."""
    result = parse_boursobank_csv(_bourso_fr(
        '2026-10-12;2026-10-12;"CARTE 10/10/26 VILLA MARLIOZ 4 CB*1111";"La Villa Marlioz";'
        '"Non catégorisé";"Non catégorisé";-164,75;;00011112222;BoursoBank;0.96;Non'
    ))
    assert len(result) == 1
    assert result[0]["amount"] == -164.75
    assert result[0]["balance"] == 0.96
    assert result[0]["account_number"] == "00011112222"


def test_bourso_fr_keeps_suggested_label_and_category():
    result = parse_boursobank_csv(_bourso_fr(
        '2026-10-12;2026-10-12;"CARTE 09/10/26 EasyPark SARL CB*1111";EasyPark;Parking;'
        '"Auto & Moto";-3,00;;00011112222;BoursoBank;0.96;Non'
    ))
    assert result[0]["label"] == "CARTE 09/10/26 EasyPark SARL CB*1111"
    assert result[0]["suggested_label"] == "EasyPark"
    assert result[0]["bank_category"] == "Parking"


def test_bourso_uncategorized_becomes_none():
    result = parse_boursobank_csv(_bourso_fr(
        '2026-10-12;2026-10-12;"CARTE X";"X";"Non catégorisé";"Non catégorisé";'
        "-1,00;;00011112222;BoursoBank;0.96;Non"
    ))
    assert result[0]["bank_category"] is None


def test_detect_bank_both_bourso_headers():
    assert detect_bank(_bourso_fr()) == BANK_BOURSOBANK
    assert detect_bank(_HEADER) == BANK_BOURSOBANK


# ---------------------------------------------------------------------------
# Crédit Mutuel
# ---------------------------------------------------------------------------
_CM_HEADER = "Date;Date de valeur;Débit;Crédit;Libellé;Solde\n"


def _cm(*rows: str) -> bytes:
    # Le Crédit Mutuel exporte en Windows-1252, pas en UTF-8
    return (_CM_HEADER + "\n".join(rows)).encode("cp1252")


def test_credit_mutuel_debit_and_credit():
    result = parse_credit_mutuel_csv(_cm(
        "28/09/2026;28/09/2026;-21,80;;PAIEMENT CB 2709 VALENCE NIVON CARTE 1111 HIR01;4153,06",
        "08/10/2026;08/10/2026;;950,00;VIR INST MME X LOYER 628;4881,35",
    ), account_number="00099998888")
    assert [r["date"] for r in result] == ["2026-09-28", "2026-10-08"]
    assert [r["amount"] for r in result] == [-21.80, 950.0]
    assert result[0]["label"] == "PAIEMENT CB 2709 VALENCE NIVON CARTE 1111 HIR01"
    assert result[0]["balance"] == 4153.06
    assert result[0]["account_number"] == "00099998888"


def test_credit_mutuel_detected_from_cp1252():
    assert detect_bank(_cm()) == BANK_CREDIT_MUTUEL


def test_account_number_from_filename():
    assert account_number_from_filename("00099998888.csv") == "00099998888"
    assert account_number_from_filename("releve commun.csv") is None
    assert account_number_from_filename(None) is None


# ---------------------------------------------------------------------------
# parse_statement : détection + identifiants
# ---------------------------------------------------------------------------
def test_parse_statement_credit_mutuel_uses_filename_and_cm_prefix():
    bank, rows = parse_statement(
        _cm("05/10/2026;05/10/2026;-73,19;;PRLV SEPA MATMUT;5201,90"), "00099998888.csv"
    )
    assert bank == BANK_CREDIT_MUTUEL
    assert rows[0]["account_number"] == "00099998888"
    assert rows[0]["external_id"].startswith("cm_")


def test_parse_statement_identical_operations_get_distinct_ids():
    """2 achats identiques le même jour = 2 opérations, pas un doublon."""
    line = '2026-10-05;2026-10-05;"CARTE 02/10/26 CAFE CB*1111";Cafe;Cafe;Loisirs;-2,50;;000;BoursoBank;10.00;Non'
    _, rows = parse_statement(_bourso_fr(line, line))
    assert rows[0]["external_id"] != rows[1]["external_id"]


def test_parse_statement_first_occurrence_keeps_legacy_id():
    """Les lignes déjà importées avant ce changement doivent être reconnues."""
    _, rows = parse_statement(_make_csv(
        '2026-04-30;2026-04-30;"SWILE";;Cat;Parent;-0,86;;000;BoursoBank;100.00'
    ))
    assert rows[0]["external_id"] == build_external_id("2026-04-30", -0.86, "SWILE")


def test_parse_statement_unknown_format_raises():
    import pytest

    with pytest.raises(UnknownStatementFormat):
        parse_statement(b"foo;bar\n1;2")


def test_map_statement_uses_suggested_label_and_keeps_raw():
    raw = {
        "date": "2026-10-12", "amount": -3.0, "label": "CARTE 09/10/26 EasyPark SARL CB*1111",
        "suggested_label": "EasyPark", "bank_category": "Parking", "external_id": "bourso_x",
    }
    tx = map_statement_transaction(raw, "personal", "acc-1")
    assert tx["label"] == "EasyPark"
    assert tx["raw_label"] == "CARTE 09/10/26 EasyPark SARL CB*1111"
    assert tx["bank_category"] == "Parking"
    assert tx["account_id"] == "acc-1"
    assert tx["external_id"] == "bourso_x"
