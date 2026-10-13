"""Tests de la file « À traiter » (libellés tirés de vrais relevés)."""

import polars as pl

from src.logic.inbox import (
    USER_RULE_PRIORITY,
    build_rule,
    category_suggestions_from_history,
    pending_transactions,
    suggest_category,
    suggest_pattern,
)


def _tx(raw, label=None, **extra):
    return {"label": label or raw, "raw_label": raw, **extra}


class TestSuggestPattern:
    def test_bourso_uses_cleaned_label(self):
        assert suggest_pattern(_tx("CARTE 09/10/26 EasyPark SARL CB*8589", "EasyPark")) == "EasyPark"

    def test_bourso_without_cleaned_label(self):
        assert suggest_pattern(_tx("CARTE 01/10/26 DELIVEROO CB*8589")) == "DELIVEROO"

    def test_credit_mutuel_card(self):
        raw = "PAIEMENT CB 0610 BEYNOST E LECLERC CARTE 1295 HIR012628004430068"
        assert suggest_pattern(_tx(raw)) == "BEYNOST E LECLERC"

    def test_credit_mutuel_contactless(self):
        raw = "PAIEMENT PSC 0910 69 CALUIRE ET REGIE BPNL CARTE 3935 HIR012628505256830"
        assert suggest_pattern(_tx(raw)) == "69 CALUIRE ET REGIE BPNL"

    def test_direct_debit(self):
        raw = "PRLV SEPA MATMUT ROUEN 2026100500009840010002361"
        assert suggest_pattern(_tx(raw)) == "MATMUT ROUEN"

    def test_too_short_falls_back_to_raw(self):
        assert suggest_pattern(_tx("VIR 12345678")) == "VIR 12345678"

    def test_manual_entry_without_raw(self):
        assert suggest_pattern({"label": "Boulangerie", "raw_label": None}) == "BOULANGERIE"


def test_pending_excludes_categorized_transfers_and_household():
    df = pl.DataFrame({
        "id": ["a", "b", "c", "d"],
        "category": [None, "Repas", None, None],
        "is_transfer": [False, False, True, False],
        "is_household": [False, False, False, True],
    })
    assert pending_transactions(df)["id"].to_list() == ["a"]


def test_category_suggestions_most_frequent():
    history = pl.DataFrame({
        "business_id": ["personal"] * 4,
        "bank_category": ["Restaurants", "Restaurants", "Restaurants", None],
        "category": ["Restau / Soirées", "Restau / Soirées", "Repas", "Repas"],
    })
    assert category_suggestions_from_history(history) == {
        ("personal", "Restaurants"): "Restau / Soirées"
    }


def test_suggest_category_only_if_allowed():
    sugg = {("personal", "Parking"): "Transport"}
    tx = {"business_id": "personal", "bank_category": "Parking"}
    assert suggest_category(tx, sugg, ["Transport", "Repas"]) == "Transport"
    assert suggest_category(tx, sugg, ["Repas"]) is None
    assert suggest_category({"business_id": "personal", "bank_category": None}, sugg, ["Transport"]) is None


def test_build_rule():
    rule = build_rule("  EasyPark ", "Transport", "personal")
    assert rule == {"pattern": "EasyPark", "category": "Transport", "business_id": "personal",
                    "priority": USER_RULE_PRIORITY, "is_active": True}
