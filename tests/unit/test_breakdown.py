"""Tests de la répartition des dépenses par groupe, avec variation."""

from datetime import date

import polars as pl

from src.logic.breakdown import (
    GROUP_COLORS,
    OTHER_GROUP,
    by_group,
    category_group_map,
    color_of,
    display_group,
    format_delta,
    household_overview,
    spending_table,
)

CATEGORIES = [
    {"name": "Courses", "direction": "expense", "group_name": "Alimentation", "business_id": "personal"},
    {"name": "Restaurants & bars", "direction": "expense", "group_name": "Alimentation", "business_id": "personal"},
    {"name": "Loyer", "direction": "expense", "group_name": "Logement", "business_id": "personal"},
    {"name": "Prêt immobilier", "direction": "expense", "group_name": "Logement", "business_id": "household"},
    {"name": "Achats perso Bruno", "direction": "expense", "group_name": "Hors dépenses communes", "business_id": "household"},
    {"name": "CAF", "direction": "income", "group_name": "Revenus", "business_id": "personal"},
]
GROUPS = category_group_map(CATEGORIES)


def _df(*rows):
    return pl.DataFrame(
        [{"date": date(2026, m, 5), "amount": a, "category": c, "is_exceptional": False}
         for m, a, c in rows],
        schema_overrides={"category": pl.Utf8},
    )


def test_group_map_only_for_the_direction():
    assert GROUPS["Courses"] == "Alimentation"
    assert "CAF" not in GROUPS


def test_display_group_falls_back_to_other():
    assert display_group("Courses", GROUPS) == "Alimentation"
    assert display_group("Achats perso Bruno", GROUPS) == OTHER_GROUP   # groupe non coloré
    assert display_group("inconnue", GROUPS) == OTHER_GROUP


def test_colors_are_fixed_per_group_and_other_is_gray():
    assert color_of("Logement") == GROUP_COLORS["Logement"][0]
    assert color_of("Logement", dark=True) == GROUP_COLORS["Logement"][1]
    assert color_of("Autres") != color_of("Logement")
    assert len({c[0] for c in GROUP_COLORS.values()}) == len(GROUP_COLORS)


class TestSpendingTable:
    def test_totals_percent_and_variation(self):
        now = _df((10, -60.0, "Courses"), (10, -40.0, "Restaurants & bars"), (10, 500.0, "CAF"))
        before = _df((9, -50.0, "Courses"))
        table = spending_table(now, before, GROUPS).to_dicts()
        courses = next(r for r in table if r["category"] == "Courses")
        assert courses["total"] == 60.0 and courses["pct"] == 60.0
        assert courses["previous"] == 50.0 and courses["delta"] == 10.0 and courses["delta_pct"] == 20.0
        resto = next(r for r in table if r["category"] == "Restaurants & bars")
        assert resto["previous"] == 0.0 and resto["delta_pct"] is None   # nouveau ce mois-ci

    def test_income_is_ignored_and_uncategorized_is_kept(self):
        table = spending_table(_df((10, -10.0, None), (10, 300.0, "CAF")), None, GROUPS)
        assert table["category"].to_list() == ["non classé"]

    def test_empty(self):
        assert spending_table(_df(), None, GROUPS).is_empty()

    def test_sorted_by_amount(self):
        table = spending_table(_df((10, -5.0, "Courses"), (10, -50.0, "Loyer")), None, GROUPS)
        assert table["category"].to_list() == ["Loyer", "Courses"]


def test_by_group_sums_categories_of_the_same_group():
    now = _df((10, -60.0, "Courses"), (10, -40.0, "Restaurants & bars"), (10, -100.0, "Loyer"))
    before = _df((9, -80.0, "Courses"), (9, -20.0, "Restaurants & bars"))
    groups = by_group(spending_table(now, before, GROUPS)).to_dicts()
    alim = next(g for g in groups if g["group"] == "Alimentation")
    assert alim["total"] == 100.0 and alim["pct"] == 50.0
    assert alim["previous"] == 100.0 and alim["delta"] == 0.0
    assert next(g for g in groups if g["group"] == "Logement")["delta_pct"] is None


class TestFormatDelta:
    def test_up_down_flat_new(self):
        assert format_delta(120.0, 12.0) == "▲ +120 € (+12 %)"
        assert format_delta(-40.0, -8.0) == "▼ −40 € (−8 %)"
        assert format_delta(0.2, 1.0) == "—"
        assert format_delta(None, None) == "—"
        assert format_delta(300.0, None) == "▲ +300 € (nouveau)"


class TestHouseholdOverview:
    def _foyer(self, *rows):
        return pl.DataFrame(
            [{"date": date(2026, 10, 8), "amount": a, "category": c, "is_exceptional": e}
             for a, c, e in rows],
            schema_overrides={"category": pl.Utf8},
        )

    def test_participation_counted_once_when_foyer_has_the_month(self):
        perso = pl.DataFrame({"date": [date(2026, 10, 1)] * 2, "amount": [-950.0, -30.0],
                              "category": ["Loyer", "Courses"]})
        foyer = self._foyer((-828.98, "Prêt immobilier", False), (-43.0, "Courses", False))
        total = spending_table(household_overview(perso, foyer), None, GROUPS)
        by_cat = {r["category"]: r["total"] for r in total.to_dicts()}
        assert "Loyer" not in by_cat                     # remplacé par les vraies dépenses du foyer
        assert by_cat["Prêt immobilier"] == 828.98
        assert by_cat["Courses"] == 73.0                 # perso + foyer additionnés

    def test_participation_kept_for_months_without_foyer_data(self):
        """Avant l'import du compte commun, le loyer perso est la seule trace du logement."""
        perso = pl.DataFrame({"date": [date(2026, 5, 1)], "amount": [-950.0], "category": ["Loyer"]})
        foyer = self._foyer((-43.0, "Courses", False))   # octobre seulement
        assert "Loyer" in household_overview(perso, foyer)["category"].to_list()

    def test_bruno_personal_purchases_exceptional_and_income_are_excluded(self):
        perso = pl.DataFrame({"date": [date(2026, 10, 1)], "amount": [-10.0], "category": ["Courses"]})
        foyer = self._foyer(
            (-75.0, "Achats perso Bruno", False),
            (-26000.0, "Divers", True),
            (2614.12, "Salaire Bruno", False),
        )
        assert household_overview(perso, foyer)["category"].to_list() == ["Courses"]

    def test_empty_inputs(self):
        empty = pl.DataFrame(schema={"date": pl.Date, "amount": pl.Float64, "category": pl.Utf8,
                                     "is_exceptional": pl.Boolean})
        assert household_overview(empty, empty).is_empty()
