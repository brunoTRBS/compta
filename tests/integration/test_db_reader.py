"""Tests db_reader — Supabase REST mockée → Polars."""

from datetime import date
from unittest.mock import MagicMock, patch

import polars as pl
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chain_mock(data: list[dict]) -> MagicMock:
    """Mock client Supabase avec chaînage fluent et données de retour configurables."""
    client = MagicMock()
    for method in ("table", "select", "eq", "neq", "gte", "lte", "gt", "lt", "in_", "order", "limit"):
        getattr(client, method).return_value = client
    client.execute.return_value = MagicMock(data=data)
    return client


def _two_step_mock(first_data: list[dict], second_data: list[dict]) -> MagicMock:
    """Mock pour les fonctions qui appellent get_supabase() deux fois (ex: patrimoine)."""
    first = _chain_mock(first_data)
    second = _chain_mock(second_data)
    return MagicMock(side_effect=[first, second])


_TX_ROW = {
    "id": "tx-1",
    "date": "2024-03-01",
    "amount": 500.0,
    "label": "Coaching",
    "source": "stripe",
    "business_id": "phi_rising",
    "category": "revenue",
    "is_income": True,
    "external_id": "gc-1",
    "created_at": "2024-03-01T10:00:00+00:00",
}


# ---------------------------------------------------------------------------
# read_transactions
# ---------------------------------------------------------------------------

class TestReadTransactions:
    def test_returns_dataframe(self):
        client = _chain_mock([_TX_ROW])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            result = db_reader.read_transactions()
            assert isinstance(result, pl.DataFrame)
            assert result.shape[0] == 1

    def test_empty_returns_typed_schema(self):
        client = _chain_mock([])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            result = db_reader.read_transactions()
            assert result.shape[0] == 0
            assert result.schema["amount"] == pl.Float64
            assert result.schema["is_income"] == pl.Boolean

    def test_business_id_filter_applied(self):
        client = _chain_mock([])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            db_reader.read_transactions(business_id="phi_rising")
            client.eq.assert_any_call("business_id", "phi_rising")

    def test_year_filter_applied(self):
        client = _chain_mock([])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            db_reader.read_transactions(year=2024)
            client.gte.assert_any_call("date", "2024-01-01")
            client.lte.assert_any_call("date", "2024-12-31")

    def test_year_month_filter_leap_year(self):
        client = _chain_mock([])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            db_reader.read_transactions(year=2024, month=2)
            client.gte.assert_any_call("date", "2024-02-01")
            client.lte.assert_any_call("date", "2024-02-29")

    def test_date_from_to_overrides_year_month(self):
        client = _chain_mock([])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            db_reader.read_transactions(date_from=date(2024, 1, 1), date_to=date(2024, 6, 30))
            client.gte.assert_any_call("date", "2024-01-01")
            client.lte.assert_any_call("date", "2024-06-30")

    def test_combined_filters(self):
        client = _chain_mock([])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            db_reader.read_transactions(business_id="booth_in_lyon", year=2024, month=6)
            client.eq.assert_any_call("business_id", "booth_in_lyon")
            client.gte.assert_any_call("date", "2024-06-01")
            client.lte.assert_any_call("date", "2024-06-30")


# ---------------------------------------------------------------------------
# read_accounts
# ---------------------------------------------------------------------------

class TestReadAccounts:
    def test_returns_dataframe(self):
        rows = [{"id": "acc-1", "name": "CIC", "institution": "CIC", "type": "current",
                 "owner": "personal", "currency": "EUR", "balance": 1000.0, "last_synced_at": None}]
        client = _chain_mock(rows)
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            result = db_reader.read_accounts()
            assert isinstance(result, pl.DataFrame)
            assert result.shape[0] == 1

    def test_owner_filter_applied(self):
        client = _chain_mock([])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            db_reader.read_accounts(owner="personal")
            client.eq.assert_any_call("owner", "personal")

    def test_is_active_always_filtered(self):
        client = _chain_mock([])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            db_reader.read_accounts()
            client.eq.assert_any_call("is_active", True)


# ---------------------------------------------------------------------------
# read_monthly_revenue
# ---------------------------------------------------------------------------

class TestReadMonthlyRevenue:
    def test_aggregation_by_month(self):
        rows = [
            {"date": "2024-01-15", "amount": 500.0},
            {"date": "2024-01-20", "amount": 300.0},
            {"date": "2024-03-01", "amount": 800.0},
        ]
        client = _chain_mock(rows)
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            result = db_reader.read_monthly_revenue(business_id="phi_rising", year=2024)
            assert isinstance(result, pl.DataFrame)
            assert set(result.columns) >= {"month", "revenue"}
            jan = result.filter(pl.col("month") == 1)
            assert jan["revenue"][0] == pytest.approx(800.0)

    def test_empty_returns_schema(self):
        client = _chain_mock([])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            result = db_reader.read_monthly_revenue(business_id="phi", year=2024)
            assert result.shape[0] == 0
            assert "month" in result.columns
            assert "revenue" in result.columns

    def test_only_positive_amounts_fetched(self):
        client = _chain_mock([])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            db_reader.read_monthly_revenue(business_id="phi", year=2024)
            client.gt.assert_any_call("amount", 0)


# ---------------------------------------------------------------------------
# read_category_breakdown
# ---------------------------------------------------------------------------

class TestReadCategoryBreakdown:
    def test_aggregation_by_category(self):
        rows = [
            {"category": "services", "amount": -100.0},
            {"category": "services", "amount": -200.0},
            {"category": "loyer", "amount": -800.0},
        ]
        client = _chain_mock(rows)
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            result = db_reader.read_category_breakdown(business_id="phi", year=2024)
            assert isinstance(result, pl.DataFrame)
            loyer = result.filter(pl.col("category") == "loyer")
            assert loyer["total"][0] == pytest.approx(-800.0)

    def test_null_category_filled(self):
        rows = [{"category": None, "amount": -50.0}]
        client = _chain_mock(rows)
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            result = db_reader.read_category_breakdown(business_id="phi", year=2024)
            assert "non classé" in result["category"].to_list()

    def test_income_direction_filter(self):
        client = _chain_mock([])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            db_reader.read_category_breakdown(business_id="phi", year=2024, direction="income")
            client.gt.assert_any_call("amount", 0)

    def test_expense_direction_filter(self):
        client = _chain_mock([])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            db_reader.read_category_breakdown(business_id="phi", year=2024, direction="expense")
            client.lt.assert_any_call("amount", 0)


# ---------------------------------------------------------------------------
# read_patrimoine_evolution
# ---------------------------------------------------------------------------

class TestReadPatrimoineEvolution:
    def test_aggregates_balance_by_date(self):
        acc_data = [{"id": "acc-1"}, {"id": "acc-2"}]
        hist_data = [
            {"date": "2024-01-01", "balance": 10000.0},
            {"date": "2024-01-01", "balance": 15000.0},
            {"date": "2024-02-01", "balance": 25000.0},
        ]
        mock_factory = _two_step_mock(acc_data, hist_data)
        with patch("src.services.db_reader.get_supabase", mock_factory):
            from src.services import db_reader
            result = db_reader.read_patrimoine_evolution()
            jan = result.filter(pl.col("date") == date(2024, 1, 1))
            assert jan["total_balance"][0] == pytest.approx(25000.0)

    def test_owner_filter_on_accounts(self):
        acc_client = _chain_mock([{"id": "acc-1"}])
        hist_client = _chain_mock([{"date": "2024-01-01", "balance": 5000.0}])
        mock_factory = MagicMock(side_effect=[acc_client, hist_client])
        with patch("src.services.db_reader.get_supabase", mock_factory):
            from src.services import db_reader
            db_reader.read_patrimoine_evolution(owner="personal")
            acc_client.eq.assert_any_call("owner", "personal")

    def test_empty_accounts_returns_empty_df(self):
        client = _chain_mock([])
        with patch("src.services.db_reader.get_supabase", return_value=client):
            from src.services import db_reader
            result = db_reader.read_patrimoine_evolution(owner="nobody")
            assert result.shape[0] == 0
            assert "total_balance" in result.columns
