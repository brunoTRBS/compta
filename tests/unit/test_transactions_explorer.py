"""Tests de la page Transactions : filtres, recherche, modifications, suppression."""

from datetime import date

import polars as pl

from src.logic.categories import resolve_category
from src.logic.transactions_explorer import (
    NO_CATEGORY,
    filter_transactions,
    normalize,
    period_bounds,
    plan_bulk,
    plan_delete,
    plan_edits,
    totals,
)


def _row(id_, label, amount, business="personal", category=None, day=5, month=10, **kw):
    return {"id": id_, "date": date(2026, month, day), "label": label, "raw_label": kw.pop("raw", label),
            "amount": amount, "business_id": business, "category": category, "account_id": kw.pop("account", "a1"),
            "needs_review": False, "is_exceptional": False, "is_transfer": False,
            "transfer_group_id": None, "external_id": f"e{id_}", **kw}


ROWS = [
    _row("1", "Café de la gare", -3.5, category="Restaurants & bars"),
    _row("2", "E LECLERC", -43.0, "household", "Courses", account="a2", raw="PAIEMENT CB LECLERC CARTE 3935"),
    _row("3", "Salaire", 1800.0, "household", "Salaire Bruno", account="a2"),
    _row("4", "Boulangerie", -2.0, month=9),
    _row("5", "Virement vers livret", -100.0, is_transfer=True, transfer_group_id="g1"),
    _row("6", "Apport", -26000.0, "household", is_exceptional=True, account="a2"),
]
DF = pl.DataFrame(ROWS, schema_overrides={"category": pl.Utf8})
CATEGORIES = {
    "personal": {"expense": {"Courses", "Restaurants & bars"}, "income": {"CAF"}},
    "household": {"expense": {"Courses", "Divers"}, "income": {"Salaire Bruno"}},
}


def _ids(df):
    return df["id"].to_list()


class TestPeriod:
    TODAY = date(2026, 10, 19)

    def test_bounds(self):
        assert period_bounds("Ce mois-ci", self.TODAY) == (date(2026, 10, 1), self.TODAY)
        assert period_bounds("Mois dernier", self.TODAY) == (date(2026, 9, 1), date(2026, 9, 30))
        assert period_bounds("3 derniers mois", self.TODAY) == (date(2026, 8, 1), self.TODAY)
        assert period_bounds("Cette année", self.TODAY) == (date(2026, 1, 1), self.TODAY)
        assert period_bounds("Tout", self.TODAY) == (None, None)
        assert period_bounds("Choisir…", self.TODAY, (date(2026, 3, 1), date(2026, 3, 31))) == (
            date(2026, 3, 1), date(2026, 3, 31))

    def test_three_months_across_new_year(self):
        assert period_bounds("3 derniers mois", date(2026, 1, 20)) == (date(2025, 11, 1), date(2026, 1, 20))

    def test_last_month_in_january(self):
        assert period_bounds("Mois dernier", date(2026, 1, 20)) == (date(2025, 12, 1), date(2025, 12, 31))


class TestFilters:
    def test_transfers_hidden_by_default(self):
        assert "5" not in _ids(filter_transactions(DF))
        assert "5" in _ids(filter_transactions(DF, include_transfers=True))

    def test_period_and_business(self):
        out = filter_transactions(DF, date_from=date(2026, 10, 1), businesses=["household"])
        assert sorted(_ids(out)) == ["2", "3", "6"]
        assert _ids(filter_transactions(DF, date_to=date(2026, 9, 30))) == ["4"]

    def test_search_is_case_and_accent_insensitive_and_looks_in_raw_label(self):
        assert _ids(filter_transactions(DF, text="cafe")) == ["1"]
        assert _ids(filter_transactions(DF, text="CAFÉ")) == ["1"]
        assert _ids(filter_transactions(DF, text="carte 3935")) == ["2"]

    def test_categories_including_unclassified(self):
        assert _ids(filter_transactions(DF, categories=["Courses"])) == ["2"]
        assert sorted(_ids(filter_transactions(DF, categories=[NO_CATEGORY]))) == ["4", "6"]

    def test_direction_and_min_amount(self):
        assert _ids(filter_transactions(DF, direction="income")) == ["3"]
        assert sorted(_ids(filter_transactions(DF, direction="expense", min_amount=40))) == ["2", "6"]

    def test_only_exceptional_and_review(self):
        assert _ids(filter_transactions(DF, only_exceptional=True)) == ["6"]
        assert _ids(filter_transactions(DF, only_review=True)) == []

    def test_accounts(self):
        assert sorted(_ids(filter_transactions(DF, account_ids=["a2"]))) == ["2", "3", "6"]

    def test_empty_frame(self):
        assert filter_transactions(pl.DataFrame()).is_empty()

    def test_sorted_newest_first(self):
        assert filter_transactions(DF)["date"].to_list() == sorted(filter_transactions(DF)["date"].to_list(), reverse=True)


def test_normalize():
    assert normalize("Café Éléphant") == "cafe elephant"
    assert normalize(None) == ""


def test_totals():
    assert totals(filter_transactions(DF, businesses=["household"])) == {
        "income": 1800.0, "expenses": 26043.0, "count": 3}
    assert totals(pl.DataFrame())["count"] == 0


class TestResolveCategory:
    def test_chosen_valid(self):
        assert resolve_category(None, "Courses", {"Courses"}) == ("Courses", False)

    def test_chosen_invalid_is_rejected_and_current_kept_if_valid(self):
        assert resolve_category("Divers", "Travaux", {"Divers"}) == ("Divers", True)

    def test_no_choice_clears_a_category_that_is_no_longer_valid(self):
        assert resolve_category("Travaux", None, {"Divers"}) == (None, False)


class TestPlanEdits:
    def _tx(self, **kw):
        return {"id": "1", "label": "Café", "business_id": "personal", "category": "Restaurants & bars",
                "amount": -3.5, "is_exceptional": False, **kw}

    def test_no_change(self):
        tx = self._tx()
        edited = [{"id": "1", "Libellé": "Café", "Budget": "personal", "Catégorie": "Restaurants & bars",
                   "Exceptionnel": False}]
        assert plan_edits([tx], edited, CATEGORIES).updates == []

    def test_rename_recategorize_exceptional(self):
        tx = self._tx()
        edited = [{"id": "1", "Libellé": "Café gare", "Budget": "personal", "Catégorie": "Courses",
                   "Exceptionnel": True}]
        assert plan_edits([tx], edited, CATEGORIES).updates == [
            {"id": "1", "label": "Café gare", "category": "Courses", "is_exceptional": True}]

    def test_move_to_another_budget_clears_category_missing_there(self):
        tx = self._tx()  # Restaurants & bars n'existe pas au foyer
        edited = [{"id": "1", "Libellé": "Café", "Budget": "household", "Catégorie": "Restaurants & bars",
                   "Exceptionnel": False}]
        plan = plan_edits([tx], edited, CATEGORIES)
        assert plan.updates == [{"id": "1", "business_id": "household", "category": None}]
        assert "Restaurants & bars" in plan.errors[0]

    def test_move_keeps_category_valid_in_both(self):
        tx = self._tx(category="Courses")
        edited = [{"id": "1", "Libellé": "Café", "Budget": "household", "Catégorie": "Courses",
                   "Exceptionnel": False}]
        assert plan_edits([tx], edited, CATEGORIES).updates == [{"id": "1", "business_id": "household"}]


class TestPlanBulk:
    SELECTED = [
        {"id": "1", "label": "Café", "business_id": "personal", "category": None, "amount": -3.5, "is_exceptional": False},
        {"id": "2", "label": "Leclerc", "business_id": "household", "category": None, "amount": -43.0, "is_exceptional": False},
    ]

    def test_category_applied_where_valid_only(self):
        plan = plan_bulk(self.SELECTED, CATEGORIES, category="Courses")
        assert plan.updates == [{"id": "1", "category": "Courses"}, {"id": "2", "category": "Courses"}]
        plan = plan_bulk(self.SELECTED, CATEGORIES, category="Restaurants & bars")
        assert plan.updates == [{"id": "1", "category": "Restaurants & bars"}]
        assert len(plan.errors) == 1

    def test_move_everything_to_a_budget(self):
        plan = plan_bulk(self.SELECTED, CATEGORIES, business_id="household")
        assert plan.updates == [{"id": "1", "business_id": "household"}]

    def test_exceptional_for_all(self):
        plan = plan_bulk(self.SELECTED, CATEGORIES, exceptional=True)
        assert [u["is_exceptional"] for u in plan.updates] == [True, True]


def test_plan_delete_groups_transfers_and_counts_imported():
    rows = [
        {"id": "1", "transfer_group_id": None, "external_id": "bourso_x"},
        {"id": "2", "transfer_group_id": None, "external_id": None},
        {"id": "3", "transfer_group_id": "g1", "external_id": None},
        {"id": "4", "transfer_group_id": "g1", "external_id": None},
    ]
    assert plan_delete(rows) == (["1", "2"], ["g1"], 1)
