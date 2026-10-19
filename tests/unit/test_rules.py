"""Tests de la gestion des règles de catégorisation."""

from src.logic.rules import diff_rules, rule_stats, sort_rules, which_rule

RULES = [
    {"id": "r1", "pattern": "LECLERC", "business_id": "household", "category": "Courses",
     "direction": "expense", "target_business_id": None, "priority": 150, "is_active": True},
    {"id": "r2", "pattern": "DELIVEROO", "business_id": "household", "category": "Restaurants & bars",
     "direction": "expense", "target_business_id": "personal", "priority": 200, "is_active": True},
    {"id": "r3", "pattern": "LECLERC", "business_id": None, "category": "Courses",
     "direction": None, "target_business_id": None, "priority": 50, "is_active": True},
    {"id": "r4", "pattern": "EDF", "business_id": "personal", "category": "Énergie & eau",
     "direction": "expense", "target_business_id": None, "priority": 90, "is_active": False},
]


def _tx(label, business_id="household", amount=-20.0):
    return {"label": label, "raw_label": label, "business_id": business_id, "amount": amount}


def test_sort_rules_active_first_then_priority():
    assert [r["id"] for r in sort_rules(RULES)] == ["r2", "r1", "r3", "r4"]


class TestStats:
    def test_matches_and_wins(self):
        txs = [_tx("E LECLERC"), _tx("E LECLERC"), _tx("DELIVEROO PARIS"), _tx("E LECLERC", "personal")]
        stats = rule_stats(RULES, txs)
        assert stats["r1"] == {"matches": 2, "wins": 2}
        assert stats["r2"] == {"matches": 1, "wins": 1}
        assert stats["r3"] == {"matches": 1, "wins": 1}   # seule règle valable hors foyer

    def test_shadowed_rule_has_matches_but_no_wins(self):
        high = {**RULES[0], "id": "hi", "priority": 300}
        stats = rule_stats([high, RULES[0]], [_tx("E LECLERC")])
        assert stats["hi"]["wins"] == 1
        assert stats["r1"] == {"matches": 1, "wins": 0}

    def test_inactive_rule_never_wins(self):
        stats = rule_stats(RULES, [_tx("FACTURE EDF", "personal")])
        assert stats["r4"] == {"matches": 1, "wins": 0}


class TestTestLabel:
    def test_winner(self):
        rule = which_rule(RULES, "CB LYON DELIVEROO CARTE 3935", "household", -20.0)
        assert rule["id"] == "r2" and rule["target_business_id"] == "personal"

    def test_no_match(self):
        assert which_rule(RULES, "BOULANGERIE", "household", -3.0) is None

    def test_direction_matters(self):
        assert which_rule(RULES, "E LECLERC REMBOURSEMENT", "household", 12.0) is None


def _edited(rule, **overrides):
    row = {"id": rule["id"], "Motif": rule["pattern"], "Budget visé": "Foyer" if rule["business_id"] == "household" else "Tous (hors foyer)",
           "Sens": "Dépenses", "Catégorie": rule["category"], "Ranger dans": "Reste dans son budget",
           "Priorité": rule["priority"], "Actif": rule["is_active"], "Supprimer": False}
    return {**row, **overrides}


class TestDiff:
    def test_no_change(self):
        assert diff_rules([RULES[0]], [_edited(RULES[0])]) == ({}, [], [])

    def test_changes_only_what_changed(self):
        updates, deletes, errors = diff_rules(
            [RULES[0]], [_edited(RULES[0], Motif="E LECLERC", **{"Ranger dans": "Perso"}, Priorité=160)])
        assert updates == {"r1": {"pattern": "E LECLERC", "target_business_id": "personal", "priority": 160}}
        assert deletes == [] and errors == []

    def test_deactivate_and_delete(self):
        updates, deletes, _ = diff_rules(RULES[:2], [_edited(RULES[0], Actif=False),
                                                     _edited(RULES[1], Supprimer=True)])
        assert updates == {"r1": {"is_active": False}}
        assert deletes == ["r2"]

    def test_empty_pattern_or_category_is_an_error(self):
        updates, _, errors = diff_rules([RULES[0]], [_edited(RULES[0], Motif="  ")])
        assert updates == {} and "obligatoires" in errors[0]
        _, _, errors = diff_rules([RULES[0]], [_edited(RULES[0], Catégorie="")])
        assert errors

    def test_both_directions(self):
        updates, _, _ = diff_rules([RULES[0]], [_edited(RULES[0], Sens="Les deux")])
        assert updates == {"r1": {"direction": None}}
