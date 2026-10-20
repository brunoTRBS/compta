"""Tests de la file « À traiter » (libellés tirés de vrais relevés)."""

import polars as pl

from src.logic.inbox import (
    USER_RULE_PRIORITY,
    build_rule,
    category_suggestions_from_history,
    inbox_rows,
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


def test_inbox_rows_keeps_uncategorized_and_to_review_but_not_transfers():
    df = pl.DataFrame({
        "id": ["a", "b", "c", "d", "e"],
        "category": [None, "Repas", None, "Courses", ""],
        "is_transfer": [False, False, True, False, False],
        "needs_review": [False, False, False, True, False],
    })
    assert inbox_rows(df)["id"].to_list() == ["a", "d", "e"]


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
                    "priority": USER_RULE_PRIORITY, "is_active": True,
                    "direction": None, "target_business_id": None}


# ---------------------------------------------------------------------------
# Raison d'être d'une ligne, « Ça compte pour » proposé, tableau
# ---------------------------------------------------------------------------
from src.config import HOUSEHOLD_PARTICIPATION_CATEGORY  # noqa: E402
from src.logic.inbox import (  # noqa: E402
    AFFECTATIONS,
    COL_CATEGORY,
    COL_COUNTS_FOR,
    COL_FROM,
    COL_LABEL,
    COL_OFF_MONTH,
    COL_PATTERN,
    COL_RULE,
    COL_SUGGESTED,
    COL_TO,
    REASON_CLASSIFY,
    REASON_PARTICIPATION,
    REASON_TRANSFER,
    TRANSFER,
    account_label,
    inbox_reason,
    inbox_table,
    plan_inbox_changes,
    proposed_affectation,
    proposed_category,
    rule_updates,
    visible_columns,
)


def _op(id_="t1", label="E LECLERC", amount=-27.97, business_id="household", **extra):
    return {"id": id_, "label": label, "raw_label": label, "amount": amount,
            "business_id": business_id, "category": None, "needs_review": False,
            "is_exceptional": False, "account_id": "acc-commun", "date": "2026-10-08",
            "external_id": f"cm_{id_}", **extra}


CARD = _op("card", "PAIEMENT PSC 0910 BEYNOST E LECLERC CARTE 3935 HIR0", -43.06)
PARTICIPATION = _op("part", "VIR INST MME CHARLOTTE PARIS LOYER 6281", 950.0, needs_review=True)
TRANSFER_TX = _op("trf", "VIR INST MME CHARLOTTE PARIS", 800.0, business_id="personal",
                  needs_review=True, account_id="acc-perso")
PLAIN = _op("plain", "CARTE 01/10/26 DELIVEROO CB*1111", -14.95, business_id="personal",
            account_id="acc-perso")

ACCOUNTS = [
    {"id": "acc-perso", "name": "Compte perso", "institution": "Boursobank", "owner": "personal"},
    {"id": "acc-commun", "name": "Compte commun", "institution": "Crédit Mutuel", "owner": "personal"},
    {"id": "acc-phi", "name": "Compte pro coaching", "institution": "Hello Bank", "owner": "phi_rising"},
]
CATEGORIES = {
    "personal": {"expense": {"Courses", "Restaurants & bars", "Divers"}, "income": {"CAF"}},
    "household": {"expense": {"Courses", "Divers"}, "income": {HOUSEHOLD_PARTICIPATION_CATEGORY}},
    "phi_rising": {"expense": {"Marketing"}, "income": {"BNC"}},
}
PERSO, FOYER = AFFECTATIONS["personal"], AFFECTATIONS["household"]


def _row(tx, **overrides):
    """Ligne du tableau telle qu'affichée, avant toute modification."""
    base = {
        "id": tx["id"], COL_LABEL: tx["label"],
        COL_COUNTS_FOR: AFFECTATIONS[proposed_affectation(tx)],
        COL_CATEGORY: tx.get("category"), COL_FROM: None, COL_TO: None,
        COL_OFF_MONTH: None, COL_RULE: False, COL_PATTERN: "",
    }
    return {**base, **overrides}


def _plan(tx, **overrides):
    return plan_inbox_changes([tx], [_row(tx, **overrides)], ACCOUNTS, CATEGORIES)


class TestReasonAndAffectation:
    def test_reasons(self):
        assert inbox_reason(PARTICIPATION) == REASON_PARTICIPATION
        assert inbox_reason(TRANSFER_TX) == REASON_TRANSFER
        assert inbox_reason(PLAIN) == REASON_CLASSIFY
        assert inbox_reason(CARD) == REASON_CLASSIFY   # plus de cas particulier pour la carte

    def test_transfer_to_review_starts_as_transfer_between_my_accounts(self):
        assert proposed_affectation(TRANSFER_TX) == TRANSFER
        assert proposed_affectation(CARD) == "household"   # le commun compte pour le foyer
        assert proposed_affectation(PLAIN) == "personal"

    def test_wording_is_plain(self):
        assert AFFECTATIONS["household"] == "🏠 Notre foyer"
        assert AFFECTATIONS["personal"] == "👤 Moi"
        assert "Virement" in AFFECTATIONS[TRANSFER]


class TestProposedCategory:
    def test_existing_category_is_kept(self):
        assert proposed_category({**PLAIN, "category": "Divers"}, {}, CATEGORIES) == ("Divers", False)

    def test_participation_is_prefilled(self):
        assert proposed_category(PARTICIPATION, {}, CATEGORIES) == (HOUSEHOLD_PARTICIPATION_CATEGORY, True)

    def test_history_suggestion(self):
        tx = {**PLAIN, "bank_category": "Restaurants"}
        sugg = {("personal", "Restaurants"): "Restaurants & bars"}
        assert proposed_category(tx, sugg, CATEGORIES) == ("Restaurants & bars", True)

    def test_nothing_to_propose(self):
        assert proposed_category(PLAIN, {}, CATEGORIES) == (None, False)


class TestInboxTable:
    def _table(self, rows):
        return inbox_table(rows, ACCOUNTS, CATEGORIES, {})

    def test_one_line_per_operation_reviews_first_then_latest(self):
        old = _op("old", date="2026-09-01")
        new = _op("new", date="2026-10-09")
        table = self._table([old, new, PARTICIPATION])
        assert table["id"] == ["part", "new", "old"]

    def test_paid_with_shows_the_account_name(self):
        table = self._table([PLAIN, CARD])
        assert dict(zip(table["id"], table["Payé avec"], strict=True)) == {
            "plain": "Compte perso", "card": "Compte commun"}

    def test_incoming_transfer_reads_from_other_account_to_this_one(self):
        """+800 reçus sur le Bourso : De = le pro, Vers = Bourso."""
        table = self._table([TRANSFER_TX])
        assert table[COL_FROM] == [account_label(ACCOUNTS[2])]
        assert table[COL_TO] == [account_label(ACCOUNTS[0])]

    def test_outgoing_transfer_reads_from_this_account_to_the_other(self):
        out = {**TRANSFER_TX, "id": "out", "amount": -300.0}
        livret = {"id": "liv", "name": "Livret", "institution": "Boursobank", "owner": "personal",
                  "type": "savings"}
        table = inbox_table([out], [*ACCOUNTS, livret], CATEGORIES, {})
        assert table[COL_FROM] == [account_label(ACCOUNTS[0])]
        assert table[COL_TO] == [account_label(livret)]

    def test_participation_is_prefilled_with_a_sparkle(self):
        table = self._table([PARTICIPATION])
        assert table[COL_CATEGORY] == [HOUSEHOLD_PARTICIPATION_CATEGORY]
        assert table[COL_SUGGESTED] == ["✨"]

    def test_default_columns_are_few_and_details_add_more(self):
        table = self._table([PLAIN])
        simple = visible_columns(table, details=False)
        assert COL_FROM not in simple and COL_PATTERN not in simple
        assert len(simple) <= 10
        detailed = visible_columns(table, details=True)
        assert {COL_FROM, COL_TO, COL_PATTERN, COL_OFF_MONTH} <= set(detailed)

    def test_from_and_to_appear_when_a_transfer_is_proposed(self):
        shown = visible_columns(self._table([TRANSFER_TX]), details=False)
        assert COL_FROM in shown and COL_TO in shown


class TestPlanClassify:
    def test_category_chosen(self):
        plan = _plan(PLAIN, **{COL_CATEGORY: "Restaurants & bars"})
        assert plan.updates == [{"id": "plain", "category": "Restaurants & bars"}]
        assert plan.errors == []

    def test_untouched_row_changes_nothing(self):
        assert _plan(PLAIN).updates == []

    def test_rename_label(self):
        plan = _plan(PLAIN, **{COL_LABEL: "Deliveroo"})
        assert plan.updates == [{"id": "plain", "label": "Deliveroo"}]

    def test_category_unknown_for_scope_is_refused(self):
        plan = _plan(PLAIN, **{COL_CATEGORY: "Prêt immobilier"})
        assert plan.updates == []
        assert "Prêt immobilier" in plan.errors[0] and "Moi" in plan.errors[0]

    def test_off_month_toggle(self):
        plan = _plan(CARD, **{COL_OFF_MONTH: True})
        assert plan.updates[0]["is_exceptional"] is True


class TestPlanCardOnJointAccount:
    """Une dépense du commun compte pour le foyer, sauf si on change « Ça compte pour »."""

    def test_untouched_stays_in_household(self):
        assert _plan(CARD).updates == []

    def test_moved_to_me_with_category(self):
        plan = _plan(CARD, **{COL_COUNTS_FOR: PERSO, COL_CATEGORY: "Restaurants & bars"})
        assert plan.updates == [{"id": "card", "business_id": "personal",
                                 "category": "Restaurants & bars"}]

    def test_moved_to_me_clears_category_missing_there(self):
        card = {**CARD, "category": "Courses"}  # Courses existe pour moi : conservée
        assert "category" not in _plan(card, **{COL_COUNTS_FOR: PERSO}).updates[0]
        card = {**CARD, "category": "Travaux"}  # n'existe pas pour moi : effacée
        assert _plan(card, **{COL_COUNTS_FOR: PERSO}).updates[0]["category"] is None

    def test_rule_with_target_scope(self):
        plan = _plan(CARD, **{COL_COUNTS_FOR: PERSO, COL_CATEGORY: "Restaurants & bars",
                              COL_RULE: True, COL_PATTERN: "DELIVEROO"})
        rule = plan.rules[0]
        assert (rule["pattern"], rule["category"]) == ("DELIVEROO", "Restaurants & bars")
        assert rule["business_id"] == "household"        # les opérations visées
        assert rule["target_business_id"] == "personal"  # où les ranger
        assert rule["direction"] == "expense"

    def test_rule_without_scope_change_has_no_target(self):
        plan = _plan(CARD, **{COL_CATEGORY: "Courses", COL_RULE: True, COL_PATTERN: "LECLERC"})
        assert plan.rules[0]["target_business_id"] is None

    def test_no_rule_without_category_or_pattern(self):
        assert _plan(PLAIN, **{COL_RULE: True, COL_PATTERN: "X"}).rules == []
        assert _plan(PLAIN, **{COL_CATEGORY: "Divers", COL_RULE: True, COL_PATTERN: ""}).rules == []


class TestPlanParticipation:
    def test_default_creates_perso_expense(self):
        tx = {**PARTICIPATION, "category": HOUSEHOLD_PARTICIPATION_CATEGORY}
        plan = _plan(tx)
        assert len(plan.participations) == 1
        assert plan.participations[0]["amount"] == -950.0
        assert plan.updates == [{"id": "part", "needs_review": False}]

    def test_other_category_declines_it(self):
        """L'erreur bancaire du 22/09 : on la range ailleurs, aucune dépense perso."""
        tx = {**PARTICIPATION, "category": HOUSEHOLD_PARTICIPATION_CATEGORY}
        cats = {**CATEGORIES, "household": {"expense": set(), "income": {"Autres rentrées"}}}
        plan = plan_inbox_changes([tx], [_row(tx, **{COL_CATEGORY: "Autres rentrées"})], ACCOUNTS, cats)
        assert plan.participations == []
        assert plan.updates[0]["category"] == "Autres rentrées"


class TestPlanTransfer:
    def test_with_counterpart_creates_second_leg(self):
        plan = _plan(TRANSFER_TX, **{COL_FROM: account_label(ACCOUNTS[2]), COL_TO: account_label(ACCOUNTS[0])})
        assert plan.errors == []
        update = plan.updates[0]
        assert update["is_transfer"] is True and update["needs_review"] is False
        leg = plan.legs[0]
        assert leg["amount"] == -800.0 and leg["account_id"] == "acc-phi"
        assert leg["business_id"] == "phi_rising"
        assert leg["transfer_group_id"] == update["transfer_group_id"]

    def test_only_the_other_side_is_needed(self):
        plan = _plan(TRANSFER_TX, **{COL_FROM: account_label(ACCOUNTS[2])})
        assert plan.errors == [] and len(plan.legs) == 1

    def test_without_counterpart_is_an_error_and_stays_pending(self):
        plan = _plan(TRANSFER_TX)
        assert plan.updates == [] and plan.legs == []
        assert "autre compte" in plan.errors[0]

    def test_same_account_on_both_sides_is_refused(self):
        plan = _plan(TRANSFER_TX, **{COL_FROM: account_label(ACCOUNTS[0]), COL_TO: account_label(ACCOUNTS[0])})
        assert plan.legs == [] and plan.errors

    def test_two_other_accounts_is_refused(self):
        plan = _plan(TRANSFER_TX, **{COL_FROM: account_label(ACCOUNTS[2]), COL_TO: account_label(ACCOUNTS[1])})
        assert plan.legs == [] and "un seul" in plan.errors[0]

    def test_declined_transfer_becomes_a_normal_operation(self):
        plan = _plan(TRANSFER_TX, **{COL_COUNTS_FOR: PERSO, COL_CATEGORY: "CAF"})
        assert plan.updates == [{"id": "trf", "category": "CAF", "needs_review": False}]
        assert plan.legs == []

    def test_return_of_money_from_joint_account_to_pro(self):
        """L'erreur bancaire de 695 € : un virement du commun vers le compte pro."""
        out = _op("695", "VIR SEPA CHARLOTTE PARIS", -695.0)
        plan = plan_inbox_changes(
            [out],
            [_row(out, **{COL_COUNTS_FOR: AFFECTATIONS[TRANSFER], COL_TO: account_label(ACCOUNTS[2])})],
            ACCOUNTS, CATEGORIES,
        )
        assert plan.updates[0]["is_transfer"] is True
        assert plan.legs[0]["amount"] == 695.0 and plan.legs[0]["business_id"] == "phi_rising"

    def test_transfer_to_joint_account_marks_one_side_without_creating_a_leg(self):
        pro_tx = {"id": "t1", "label": "Virement vers COMPTE COMMUN", "business_id": "phi_rising",
                  "account_id": "acc-phi", "amount": -650.0, "date": "2026-10-03",
                  "needs_review": True, "category": None}
        plan = plan_inbox_changes(
            [pro_tx],
            [_row(pro_tx, **{COL_TO: account_label(ACCOUNTS[1])})],
            ACCOUNTS, {},
        )
        assert plan.legs == [] and plan.errors == []
        assert plan.updates[0]["is_transfer"] is True
        assert plan.updates[0]["needs_review"] is False
        assert plan.updates[0]["transfer_group_id"]


class TestRuleUpdates:
    RULES = [
        {"pattern": "DELIVEROO", "business_id": "household", "category": "Restaurants & bars",
         "target_business_id": "personal", "direction": "expense", "priority": 200},
        {"pattern": "LECLERC", "business_id": "household", "category": "Courses",
         "target_business_id": None, "direction": "expense", "priority": 150},
    ]

    def _df(self, *rows):
        return pl.DataFrame(list(rows), schema_overrides={"category": pl.Utf8}, infer_schema_length=None)

    def test_rule_moves_card_purchase_to_me(self):
        card = _op("c1", "PAIEMENT CB 0810 LYON DELIVEROO CARTE 3935 HIR0", -20.0)
        updates = rule_updates(self._df(card), self.RULES)
        assert updates == [{"id": "c1", "category": "Restaurants & bars", "business_id": "personal"}]

    def test_household_rule_only_sets_the_category(self):
        updates = rule_updates(self._df(CARD), self.RULES)
        assert updates == [{"id": "card", "category": "Courses"}]

    def test_nothing_matches(self):
        other = _op("o", "BOULANGERIE", -3.0, business_id="household")
        assert rule_updates(self._df(other), self.RULES) == []
