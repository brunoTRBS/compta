"""Tests du budget du foyer (opérations tirées d'un vrai relevé du compte commun)."""

from datetime import date

import polars as pl

from src.logic.household import classify_joint_transactions, propose_exceptional
from src.logic.household_budget import (
    OTHER_PAYER,
    contributions,
    payer_of,
    regular_operations,
    retro_classify,
    spending_by_payer,
    summarize,
)


def _df(*rows):
    return pl.DataFrame(
        [
            {"id": f"t{i}", "date": date(2026, 10, 8), "label": label, "raw_label": label,
             "amount": amount, "category": category, "business_id": "household",
             "is_exceptional": exceptional, "is_transfer": False,
             "account_id": "acc-commun"}
            for i, (label, amount, category, exceptional) in enumerate(rows)
        ],
        schema_overrides={"category": pl.Utf8},
    )


MONTH = _df(
    ("VIR INST MME CHARLOTTE PARIS LOYER", 950.0, "Participation Charlotte", False),
    ("DATALYO SALAIRE 09/2026 DATALYO", 2614.12, "Salaire Bruno", False),
    ("PAIEMENT CB 0610 BEYNOST E LECLERC CARTE 1295 HIR0", -27.97, "Courses", False),
    ("PAIEMENT PSC 0910 BEYNOST E LECLERC CARTE 3935 HIR0", -43.06, "Courses", False),
    ("ECH PRET CAP+IN 07329 222229 03", -828.98, "Prêt immobilier", False),
    ("PAIEMENT CB 0810 LYON ROMERA JEAN LOUP CARTE 1295 HIR0", -75.0, "Achats perso Bruno", False),
    ("VIR INST TARBES BRUNO CH3W", -800.0, "Épargne Bruno", False),
    ("VIR INST M OU MME TABERNERO RESTIT CAUTION", 1230.91, None, True),
)


def test_regular_excludes_exceptional():
    assert regular_operations(MONTH).height == 7


def test_summarize_separates_bruno_personal_and_savings():
    s = summarize(regular_operations(MONTH))
    assert s["income"] == 3564.12
    assert s["common_expenses"] == 900.01
    assert s["non_common"] == 875.0
    assert s["difference"] == round(3564.12 - 900.01 - 875.0, 2)


def test_contributions_pct():
    contrib = contributions(regular_operations(MONTH)).to_dicts()
    assert contrib[0]["category"] == "Salaire Bruno"
    assert round(sum(c["pct"] for c in contrib)) == 100


def test_payer_of():
    assert payer_of({"raw_label": "PAIEMENT CB 0610 E LECLERC CARTE 1295 HIR0"}) == "Bruno"
    assert payer_of({"raw_label": "PAIEMENT PSC 0910 E LECLERC CARTE 3935 HIR0"}) == "Charlotte"
    assert payer_of({"raw_label": "PRLV SEPA MATMUT ROUEN"}) == OTHER_PAYER


def test_spending_by_payer_common_only():
    payers = {r["payer"]: r["total"] for r in spending_by_payer(regular_operations(MONTH)).to_dicts()}
    assert payers == {"Bruno": 27.97, "Charlotte": 43.06, OTHER_PAYER: 828.98}


class TestProposeExceptional:
    def test_big_amount(self):
        assert propose_exceptional({"business_id": "household", "amount": 29000.0, "category": "Virements Bruno"})

    def test_salary_never(self):
        assert not propose_exceptional({"business_id": "household", "amount": 2614.12, "category": "Salaire Bruno"})

    def test_small_amount(self):
        assert not propose_exceptional({"business_id": "household", "amount": -828.98, "category": None})

    def test_not_household(self):
        assert not propose_exceptional({"business_id": "personal", "amount": -5000.0, "category": None})


def test_classify_joint_cancels_rejected_transfers():
    rows = classify_joint_transactions([
        {"date": "2026-09-23", "amount": -698.0, "label": "VIR INST CHARLOTTE PARIS CH3W1",
         "raw_label": "VIR INST CHARLOTTE PARIS CH3W1", "account_id": "c"},
        {"date": "2026-09-23", "amount": 698.0, "label": "REJ VIR INST CHARLOTTE PARIS CH3W1",
         "raw_label": "REJ VIR INST CHARLOTTE PARIS CH3W1", "account_id": "c"},
    ])
    assert all(r["is_transfer"] for r in rows)
    assert rows[0]["transfer_group_id"] == rows[1]["transfer_group_id"]
    assert not any(r["needs_review"] for r in rows)


def test_retro_classify():
    df = _df(
        ("DATALYO SALAIRE 09/2026 DATALYO", 2614.12, None, False),
        ("VIR M TARBES BRUNO REFERENCE NON TRANSMISE", 29000.0, None, False),
        ("PAIEMENT CB LYON INCONNU CARTE 1295 HIR0", -12.0, None, False),
    )
    rules = [
        {"pattern": "DATALYO", "business_id": "household", "category": "Salaire Bruno",
         "direction": "income"},
        {"pattern": "TARBES BRUNO", "business_id": "household", "category": "Virements Bruno",
         "direction": "income"},
    ]
    updates = {u["id"]: u for u in retro_classify(df, rules)}
    assert updates["t0"] == {"id": "t0", "category": "Salaire Bruno"}
    assert updates["t1"] == {"id": "t1", "category": "Virements Bruno", "is_exceptional": True}
    assert "t2" not in updates


class TestOperationChanges:
    ORIGINAL = {"label": "VIR SEPA CHARLOTTE PARIS CH3W26274M118430", "category": None,
                "is_exceptional": False}

    def test_bank_error_becomes_exceptional_divers_with_clear_label(self):
        from src.logic.household_budget import operation_changes

        edited = {"Libellé": "Erreur bancaire - fonds pro renvoyés", "Catégorie": "Divers",
                  "Exceptionnel": True}
        assert operation_changes(self.ORIGINAL, edited) == {
            "label": "Erreur bancaire - fonds pro renvoyés",
            "category": "Divers",
            "is_exceptional": True,
        }

    def test_nothing_changed(self):
        from src.logic.household_budget import operation_changes

        edited = {"Libellé": self.ORIGINAL["label"], "Catégorie": "", "Exceptionnel": False}
        assert operation_changes(self.ORIGINAL, edited) == {}

    def test_clearing_a_category(self):
        from src.logic.household_budget import operation_changes

        original = {**self.ORIGINAL, "category": "Courses"}
        edited = {"Libellé": original["label"], "Catégorie": "", "Exceptionnel": False}
        assert operation_changes(original, edited) == {"category": None}
