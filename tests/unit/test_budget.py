import polars as pl
import pytest
from datetime import date

from src.logic.budget import (
    breakdown_by_category,
    compute_budget_summary,
    compute_cumulative_balance,
    compute_savings_rate,
)


@pytest.fixture
def personal_transactions():
    return pl.DataFrame({
        "id": ["t-p1", "t-p2", "t-p3", "t-p4", "t-p5"],
        "date": pl.Series(
            [date(2024, 1, 5), date(2024, 1, 10), date(2024, 1, 20), date(2024, 2, 3), date(2024, 2, 15)],
            dtype=pl.Date,
        ),
        "amount": pl.Series([2500.0, -900.0, -300.0, -150.0, -80.0], dtype=pl.Float64),
        "label": ["Salaire", "Loyer", "Courses Leclerc", "Abonnement Netflix", "Restaurant"],
        "category": ["revenue", "rent", "groceries", "leisure", "meals"],
        "business_id": ["personal"] * 5,
        "is_income": [True, False, False, False, False],
        "source": ["manual", "bank", "bank", "bank", "bank"],
    })


@pytest.fixture
def three_month_history():
    """Mai : +200, Juin : +100, Juillet : +50 (revenus - dépenses par mois)."""
    return pl.DataFrame({
        "date": pl.Series(
            [date(2024, 5, 1), date(2024, 5, 2), date(2024, 6, 1), date(2024, 6, 2), date(2024, 7, 1), date(2024, 7, 2)],
            dtype=pl.Date,
        ),
        "amount": pl.Series([1000.0, -800.0, 900.0, -800.0, 850.0, -800.0], dtype=pl.Float64),
    })


class TestBreakdownByCategory:
    def test_expenses_only_by_default(self, personal_transactions):
        result = breakdown_by_category(personal_transactions)
        # Ne doit pas inclure "revenue"
        assert "revenue" not in result["category"].to_list()

    def test_includes_income_when_flag_set(self, personal_transactions):
        result = breakdown_by_category(personal_transactions, include_income=True)
        assert "revenue" in result["category"].to_list()

    def test_sorted_by_total_descending(self, personal_transactions):
        result = breakdown_by_category(personal_transactions)
        totals = result["total"].to_list()
        assert totals == sorted(totals, reverse=True)

    def test_pct_sums_to_100(self, personal_transactions):
        result = breakdown_by_category(personal_transactions)
        assert abs(result["pct"].sum() - 100.0) < 0.1

    def test_columns_present(self, personal_transactions):
        result = breakdown_by_category(personal_transactions)
        assert set(result.columns) == {"category", "total", "count", "pct"}

    def test_empty_dataframe(self):
        empty = pl.DataFrame(
            {"amount": [], "category": []},
            schema={"amount": pl.Float64, "category": pl.Utf8},
        )
        result = breakdown_by_category(empty)
        assert result.is_empty()

    def test_amounts_are_positive(self, personal_transactions):
        result = breakdown_by_category(personal_transactions)
        assert (result["total"] >= 0).all()

    def test_rent_is_largest_category(self, personal_transactions):
        result = breakdown_by_category(personal_transactions)
        assert result["category"][0] == "rent"


class TestComputeSavingsRate:
    def test_normal_case(self):
        assert compute_savings_rate(2500.0, 1500.0) == pytest.approx(40.0)

    def test_zero_savings(self):
        assert compute_savings_rate(2000.0, 2000.0) == pytest.approx(0.0)

    def test_negative_savings(self):
        # Dépenses supérieures aux revenus
        assert compute_savings_rate(1000.0, 1500.0) == pytest.approx(-50.0)

    def test_zero_income_returns_zero(self):
        assert compute_savings_rate(0.0, 500.0) == 0.0

    def test_negative_income_returns_zero(self):
        assert compute_savings_rate(-100.0, 50.0) == 0.0

    def test_full_savings(self):
        assert compute_savings_rate(3000.0, 0.0) == pytest.approx(100.0)

    def test_rounded_to_one_decimal(self):
        # 1/3 ≈ 33.3%
        rate = compute_savings_rate(3.0, 2.0)
        assert rate == pytest.approx(33.3, abs=0.1)


class TestComputeBudgetSummary:
    def test_expected_keys(self, personal_transactions):
        summary = compute_budget_summary(personal_transactions, year=2024)
        assert set(summary.keys()) == {"income", "expenses", "savings", "savings_rate", "top_category"}

    def test_income_value(self, personal_transactions):
        summary = compute_budget_summary(personal_transactions, year=2024)
        assert summary["income"] == pytest.approx(2500.0)

    def test_expenses_value(self, personal_transactions):
        summary = compute_budget_summary(personal_transactions, year=2024)
        # 900 + 300 + 150 + 80 = 1430
        assert summary["expenses"] == pytest.approx(1430.0)

    def test_savings_value(self, personal_transactions):
        summary = compute_budget_summary(personal_transactions, year=2024)
        assert summary["savings"] == pytest.approx(2500.0 - 1430.0)

    def test_savings_rate_positive(self, personal_transactions):
        summary = compute_budget_summary(personal_transactions, year=2024)
        assert summary["savings_rate"] > 0

    def test_filter_by_month(self, personal_transactions):
        summary_jan = compute_budget_summary(personal_transactions, year=2024, month=1)
        summary_all = compute_budget_summary(personal_transactions, year=2024)
        # Janvier a moins de transactions
        assert summary_jan["expenses"] < summary_all["expenses"]

    def test_wrong_year_returns_zeros(self, personal_transactions):
        summary = compute_budget_summary(personal_transactions, year=2020)
        assert summary["income"] == 0.0
        assert summary["expenses"] == 0.0

    def test_top_category_is_string_or_none(self, personal_transactions):
        summary = compute_budget_summary(personal_transactions, year=2024)
        assert summary["top_category"] is None or isinstance(summary["top_category"], str)


class TestComputeCumulativeBalance:
    def test_sums_all_months_before_not_just_the_previous_one(self, three_month_history):
        # Avant juillet : mai (+200) + juin (+100) = 300, pas seulement juin (+100)
        result = compute_cumulative_balance(three_month_history, year=2024, month=7)
        assert result == pytest.approx(300.0)

    def test_before_first_month_is_zero(self, three_month_history):
        result = compute_cumulative_balance(three_month_history, year=2024, month=5)
        assert result == pytest.approx(0.0)

    def test_before_second_month_is_first_month_only(self, three_month_history):
        result = compute_cumulative_balance(three_month_history, year=2024, month=6)
        assert result == pytest.approx(200.0)

    def test_crosses_year_boundary(self, three_month_history):
        result = compute_cumulative_balance(three_month_history, year=2025, month=1)
        assert result == pytest.approx(350.0)  # 200 + 100 + 50

    def test_empty_dataframe_returns_zero(self):
        empty = pl.DataFrame({"date": [], "amount": []}, schema={"date": pl.Date, "amount": pl.Float64})
        assert compute_cumulative_balance(empty, year=2024, month=6) == 0.0

    def test_extra_monthly_benefice_is_added(self, three_month_history):
        # Perso seul avant juillet : 300 (mai+juin). + bénéfice Phi Rising mai(+50) juin(+30) = 380
        extra = pl.DataFrame({
            "year": pl.Series([2024, 2024, 2024], dtype=pl.Int32),
            "month_num": pl.Series([5, 6, 7], dtype=pl.Int32),
            "benefice": pl.Series([50.0, 30.0, 999.0], dtype=pl.Float64),
        })
        result = compute_cumulative_balance(
            three_month_history, year=2024, month=7, extra_monthly_benefice=extra
        )
        assert result == pytest.approx(300.0 + 50.0 + 30.0)

    def test_extra_monthly_benefice_respects_month_boundary(self, three_month_history):
        # Juillet (999) ne doit pas être inclus dans le cumul avant juillet
        extra = pl.DataFrame({
            "year": pl.Series([2024], dtype=pl.Int32),
            "month_num": pl.Series([7], dtype=pl.Int32),
            "benefice": pl.Series([999.0], dtype=pl.Float64),
        })
        result = compute_cumulative_balance(
            three_month_history, year=2024, month=7, extra_monthly_benefice=extra
        )
        assert result == pytest.approx(300.0)

    def test_none_extra_monthly_benefice_unaffected(self, three_month_history):
        with_none = compute_cumulative_balance(three_month_history, year=2024, month=7, extra_monthly_benefice=None)
        without_arg = compute_cumulative_balance(three_month_history, year=2024, month=7)
        assert with_none == pytest.approx(without_arg)

    def test_opening_balance_is_added_not_replaced(self, three_month_history):
        # Sans solde d'ouverture : 300 (mai+juin) avant juillet
        result = compute_cumulative_balance(
            three_month_history, year=2024, month=7, opening_balance=1230.10
        )
        assert result == pytest.approx(300.0 + 1230.10)

    def test_opening_balance_alone_on_empty_history(self):
        empty = pl.DataFrame({"date": [], "amount": []}, schema={"date": pl.Date, "amount": pl.Float64})
        result = compute_cumulative_balance(empty, year=2025, month=5, opening_balance=1230.10)
        assert result == pytest.approx(1230.10)

    def test_opening_balance_combines_with_extra_monthly_benefice(self, three_month_history):
        extra = pl.DataFrame({
            "year": pl.Series([2024], dtype=pl.Int32),
            "month_num": pl.Series([5], dtype=pl.Int32),
            "benefice": pl.Series([40.0], dtype=pl.Float64),
        })
        result = compute_cumulative_balance(
            three_month_history, year=2024, month=7,
            extra_monthly_benefice=extra, opening_balance=1230.10,
        )
        assert result == pytest.approx(300.0 + 40.0 + 1230.10)
