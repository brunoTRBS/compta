from datetime import date

import polars as pl
import pytest

from src.logic.recurring import default_materialize_date, due_templates


@pytest.fixture
def sample_templates():
    return pl.DataFrame({
        "id": ["rec-loyer", "rec-salaire", "rec-netflix", "rec-inactif"],
        "label": ["Loyer", "Salaire", "Netflix", "Ancien abonnement"],
        "amount": pl.Series([-800.0, 2000.0, -15.0, -9.0], dtype=pl.Float64),
        "day_of_month": pl.Series([5, 1, 10, 15], dtype=pl.Int32),
        "is_active": [True, True, True, False],
        "last_materialized_year": pl.Series([2026, 2026, None, None], dtype=pl.Int32),
        "last_materialized_month": pl.Series([6, 7, None, None], dtype=pl.Int32),
    })


class TestDueTemplates:
    def test_already_materialized_this_month_excluded(self, sample_templates):
        result = due_templates(sample_templates, year=2026, month=7)
        assert "Salaire" not in result["label"].to_list()

    def test_materialized_last_month_is_due_again(self, sample_templates):
        result = due_templates(sample_templates, year=2026, month=7)
        assert "Loyer" in result["label"].to_list()

    def test_never_materialized_is_due(self, sample_templates):
        result = due_templates(sample_templates, year=2026, month=7)
        assert "Netflix" in result["label"].to_list()

    def test_inactive_template_excluded(self, sample_templates):
        result = due_templates(sample_templates, year=2026, month=7)
        assert "Ancien abonnement" not in result["label"].to_list()

    def test_empty_dataframe_returns_empty(self):
        empty = pl.DataFrame(schema={"is_active": pl.Boolean})
        result = due_templates(empty, year=2026, month=7)
        assert result.is_empty()

    def test_exact_count(self, sample_templates):
        result = due_templates(sample_templates, year=2026, month=7)
        assert result.shape[0] == 2  # Loyer + Netflix


class TestDefaultMaterializeDate:
    def test_normal_day(self):
        assert default_materialize_date(5, 2026, 7) == date(2026, 7, 5)

    def test_clamps_to_last_day_of_shorter_month(self):
        # Avril n'a que 30 jours
        assert default_materialize_date(31, 2026, 4) == date(2026, 4, 30)

    def test_february_non_leap_year(self):
        assert default_materialize_date(30, 2026, 2) == date(2026, 2, 28)

    def test_february_leap_year(self):
        assert default_materialize_date(30, 2028, 2) == date(2028, 2, 29)

    def test_first_day(self):
        assert default_materialize_date(1, 2026, 7) == date(2026, 7, 1)
