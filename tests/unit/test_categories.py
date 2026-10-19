"""Tests des catégories partagées (liste commune, renommage, fusion)."""

from src.logic.categories import (
    NO_GROUP,
    SUGGESTED_RENAMES,
    diff_matrix,
    matrix_rows,
    plan_category_rows,
    validate_rename,
)


def _cat(id_, scope, name, direction="expense", group=None):
    return {"id": id_, "business_id": scope, "name": name, "direction": direction, "group_name": group}


CURRENT = [
    _cat("1", "personal", "Courses", group="Alimentation"),
    _cat("2", "household", "Courses", group="Alimentation"),
    _cat("3", "personal", "Médical"),
    _cat("4", "personal", "Salaire", direction="income"),
]


class TestValidateRename:
    def test_ok(self):
        assert validate_rename("Médical", "Santé") is None

    def test_empty(self):
        assert validate_rename("Médical", "  ") is not None

    def test_same(self):
        assert validate_rename("Médical", "Médical") is not None

    def test_protected_cannot_be_renamed_or_merged_away(self):
        for name in ("Épargne", "BNC", "BIC", "ND", "Évenement Privé", "Stripe"):
            assert validate_rename(name, "Autre") is not None

    def test_can_merge_into_protected(self):
        """« Epargne » (sans accent) peut être fusionnée dans « Épargne »."""
        assert validate_rename("Epargne", "Épargne") is None

    def test_suggested_renames_are_all_allowed(self):
        assert all(validate_rename(old, new) is None for old, new in SUGGESTED_RENAMES)


class TestPlanCategoryRows:
    def test_rename_when_new_does_not_exist(self):
        rows = [{"id": "a", "business_id": "personal", "direction": "expense"}]
        assert plan_category_rows(rows, set()) == (["a"], [])

    def test_merge_when_new_already_exists_for_same_scope_and_direction(self):
        rows = [
            {"id": "a", "business_id": "personal", "direction": "expense"},
            {"id": "b", "business_id": "household", "direction": "expense"},
        ]
        assert plan_category_rows(rows, {("personal", "expense")}) == (["b"], ["a"])

    def test_direction_matters(self):
        rows = [{"id": "a", "business_id": "personal", "direction": "income"}]
        assert plan_category_rows(rows, {("personal", "expense")}) == (["a"], [])


class TestMatrix:
    def test_rows_group_by_name_with_scope_flags(self):
        rows = matrix_rows(CURRENT, "expense")
        courses = next(r for r in rows if r["name"] == "Courses")
        assert courses["personal"] and courses["household"]
        assert not courses["phi_rising"]
        assert courses["group"] == "Alimentation"

    def test_ungrouped_category_and_order(self):
        rows = matrix_rows(CURRENT, "expense")
        assert [r["name"] for r in rows] == ["Courses", "Médical"]
        assert rows[1]["group"] == NO_GROUP

    def test_direction_filter(self):
        assert [r["name"] for r in matrix_rows(CURRENT, "income")] == ["Salaire"]

    def test_no_change_gives_empty_diff(self):
        assert diff_matrix(CURRENT, matrix_rows(CURRENT, "expense"), "expense") == ([], [], {})

    def test_toggle_scope_on_and_off(self):
        edited = matrix_rows(CURRENT, "expense")
        courses = next(r for r in edited if r["name"] == "Courses")
        courses["household"] = False       # retirer du foyer
        courses["phi_rising"] = True       # ajouter au pro
        to_create, to_delete, groups = diff_matrix(CURRENT, edited, "expense")
        assert to_delete == ["2"]
        assert to_create == [{"business_id": "phi_rising", "name": "Courses",
                              "direction": "expense", "group_name": "Alimentation"}]
        assert groups == {}

    def test_group_change(self):
        edited = matrix_rows(CURRENT, "expense")
        next(r for r in edited if r["name"] == "Médical")["group"] = "Santé"
        _, _, groups = diff_matrix(CURRENT, edited, "expense")
        assert groups == {"Médical": "Santé"}
