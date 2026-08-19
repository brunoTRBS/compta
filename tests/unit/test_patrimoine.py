from datetime import date

import polars as pl
import pytest

from src.logic.patrimoine import (
    aggregate_by_account_type,
    compute_net_worth,
    compute_patrimoine_evolution,
    group_by_owner,
)


@pytest.fixture
def sample_accounts():
    return pl.DataFrame({
        "id": ["acc-1", "acc-2", "acc-3", "acc-4", "acc-5"],
        "name": ["Compte courant CIC", "Livret A", "Revolut", "Compte courant Phi", "LDDS"],
        "type": ["current", "savings", "revolut", "current", "savings"],
        "owner": ["personal", "personal", "personal", "phi_rising", "personal"],
        "balance": pl.Series([3500.0, 15000.0, 2000.0, 5000.0, 8000.0], dtype=pl.Float64),
        "currency": ["EUR", "EUR", "EUR", "EUR", "EUR"],
    })


@pytest.fixture
def sample_balance_history():
    return pl.DataFrame({
        "date": pl.Series(
            [date(2024, 1, 1), date(2024, 1, 1), date(2024, 2, 1), date(2024, 2, 1)],
            dtype=pl.Date,
        ),
        "account_id": ["acc-1", "acc-2", "acc-1", "acc-2"],
        "balance": pl.Series([3000.0, 14000.0, 3500.0, 15000.0], dtype=pl.Float64),
    })


class TestAggregateByAccountType:
    def test_returns_correct_types(self, sample_accounts):
        result = aggregate_by_account_type(sample_accounts)
        types_in_result = set(result["type"].to_list())
        assert types_in_result == {"current", "savings", "revolut"}

    def test_sorted_by_balance_descending(self, sample_accounts):
        result = aggregate_by_account_type(sample_accounts)
        balances = result["total_balance"].to_list()
        assert balances == sorted(balances, reverse=True)

    def test_savings_total(self, sample_accounts):
        result = aggregate_by_account_type(sample_accounts)
        savings_row = result.filter(pl.col("type") == "savings")
        # 15000 + 8000 = 23000
        assert float(savings_row["total_balance"][0]) == pytest.approx(23000.0)

    def test_columns_present(self, sample_accounts):
        result = aggregate_by_account_type(sample_accounts)
        assert set(result.columns) == {"type", "total_balance", "account_count"}

    def test_empty_returns_empty(self):
        empty = pl.DataFrame(
            {"type": [], "balance": []},
            schema={"type": pl.Utf8, "balance": pl.Float64},
        )
        result = aggregate_by_account_type(empty)
        assert result.is_empty()

    def test_account_count_correct(self, sample_accounts):
        result = aggregate_by_account_type(sample_accounts)
        savings_row = result.filter(pl.col("type") == "savings")
        assert savings_row["account_count"][0] == 2


class TestComputeNetWorth:
    def test_sums_all_balances(self, sample_accounts):
        # 3500 + 15000 + 2000 + 5000 + 8000 = 33500
        result = compute_net_worth(sample_accounts)
        assert result == pytest.approx(33500.0)

    def test_empty_returns_zero(self):
        empty = pl.DataFrame({"balance": []}, schema={"balance": pl.Float64})
        assert compute_net_worth(empty) == 0.0

    def test_single_account(self):
        df = pl.DataFrame({"balance": pl.Series([5000.0], dtype=pl.Float64)})
        assert compute_net_worth(df) == pytest.approx(5000.0)


class TestComputePatrimoineEvolution:
    def test_aggregates_by_date(self, sample_balance_history):
        result = compute_patrimoine_evolution(sample_balance_history)
        assert len(result) == 2  # 2 dates uniques

    def test_totals_correct(self, sample_balance_history):
        result = compute_patrimoine_evolution(sample_balance_history)
        jan = result.filter(pl.col("date") == date(2024, 1, 1))
        # 3000 + 14000 = 17000
        assert float(jan["total_balance"][0]) == pytest.approx(17000.0)

    def test_sorted_chronologically(self, sample_balance_history):
        result = compute_patrimoine_evolution(sample_balance_history)
        dates = result["date"].to_list()
        assert dates == sorted(dates)

    def test_columns_present(self, sample_balance_history):
        result = compute_patrimoine_evolution(sample_balance_history)
        assert set(result.columns) == {"date", "total_balance"}

    def test_empty_returns_empty(self):
        empty = pl.DataFrame(
            {"date": [], "balance": []},
            schema={"date": pl.Date, "balance": pl.Float64},
        )
        result = compute_patrimoine_evolution(empty)
        assert result.is_empty()


class TestGroupByOwner:
    def test_keys_are_owners(self, sample_accounts):
        result = group_by_owner(sample_accounts)
        assert set(result.keys()) == {"personal", "phi_rising"}

    def test_personal_total(self, sample_accounts):
        result = group_by_owner(sample_accounts)
        # 3500 + 15000 + 2000 + 8000 = 28500
        assert result["personal"] == pytest.approx(28500.0)

    def test_phi_rising_total(self, sample_accounts):
        result = group_by_owner(sample_accounts)
        assert result["phi_rising"] == pytest.approx(5000.0)

    def test_empty_returns_empty_dict(self):
        empty = pl.DataFrame({"owner": [], "balance": []}, schema={"owner": pl.Utf8, "balance": pl.Float64})
        assert group_by_owner(empty) == {}
