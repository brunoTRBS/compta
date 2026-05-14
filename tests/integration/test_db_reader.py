"""Tests d'intégration db_reader — pl.read_database et get_db_url mockés.

Ces tests vérifient la construction des requêtes SQL et le typage des retours
sans connexion réelle à Supabase.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date

import polars as pl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tx_df(n: int = 1) -> pl.DataFrame:
    """Retourne un DataFrame de transactions typé, prêt à traverser _cast_transactions."""
    return pl.DataFrame({
        "id": [f"tx-{i}" for i in range(n)],
        "date": pl.Series([date(2024, 3, 1)] * n, dtype=pl.Date),
        "amount": pl.Series([500.0] * n, dtype=pl.Float64),
        "label": ["Coaching"] * n,
        "source": ["stripe"] * n,
        "business_id": ["phi_rising"] * n,
        "category": ["revenue"] * n,
        "is_income": pl.Series([True] * n, dtype=pl.Boolean),
        "external_id": [f"gc-{i}" for i in range(n)],
        "created_at": pl.Series([None] * n, dtype=pl.Datetime("us", "UTC")),
    })


def _make_accounts_df(n: int = 1) -> pl.DataFrame:
    return pl.DataFrame({
        "id": [f"acc-{i}" for i in range(n)],
        "name": [f"Compte {i}" for i in range(n)],
        "institution": ["CIC"] * n,
        "type": ["current"] * n,
        "owner": ["personal"] * n,
        "currency": ["EUR"] * n,
        "balance": pl.Series([1000.0] * n, dtype=pl.Float64),
        "last_synced_at": pl.Series([None] * n, dtype=pl.Datetime("us", "UTC")),
    })


# ---------------------------------------------------------------------------
# read_transactions
# ---------------------------------------------------------------------------

class TestReadTransactions:
    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_returns_polars_dataframe(self, mock_read_db, mock_url):
        mock_read_db.return_value = _make_tx_df()

        from src.services.db_reader import read_transactions
        result = read_transactions()

        assert isinstance(result, pl.DataFrame)
        mock_read_db.assert_called_once()

    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_business_id_filter_in_query(self, mock_read_db, mock_url):
        mock_read_db.return_value = _make_tx_df()

        from src.services.db_reader import read_transactions
        read_transactions(business_id="phi_rising")

        query = mock_read_db.call_args[1]["query"]
        assert "phi_rising" in query

    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_year_filter_in_query(self, mock_read_db, mock_url):
        mock_read_db.return_value = _make_tx_df()

        from src.services.db_reader import read_transactions
        read_transactions(year=2024)

        query = mock_read_db.call_args[1]["query"]
        assert "2024" in query

    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_month_filter_in_query(self, mock_read_db, mock_url):
        mock_read_db.return_value = _make_tx_df()

        from src.services.db_reader import read_transactions
        read_transactions(year=2024, month=3)

        query = mock_read_db.call_args[1]["query"]
        assert "= 3" in query

    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_no_where_when_no_filters(self, mock_read_db, mock_url):
        mock_read_db.return_value = _make_tx_df()

        from src.services.db_reader import read_transactions
        read_transactions()

        query = mock_read_db.call_args[1]["query"]
        assert "WHERE" not in query

    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_connectorx_engine_used(self, mock_read_db, mock_url):
        mock_read_db.return_value = _make_tx_df()

        from src.services.db_reader import read_transactions
        read_transactions(business_id="personal")

        assert mock_read_db.call_args[1]["engine"] == "connectorx"

    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_combined_filters_all_present(self, mock_read_db, mock_url):
        mock_read_db.return_value = _make_tx_df()

        from src.services.db_reader import read_transactions
        read_transactions(business_id="booth_in_lyon", year=2024, month=6)

        query = mock_read_db.call_args[1]["query"]
        assert "booth_in_lyon" in query
        assert "2024" in query
        assert "= 6" in query


# ---------------------------------------------------------------------------
# read_accounts
# ---------------------------------------------------------------------------

class TestReadAccounts:
    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_returns_dataframe(self, mock_read_db, mock_url):
        mock_read_db.return_value = _make_accounts_df()

        from src.services.db_reader import read_accounts
        result = read_accounts()
        assert isinstance(result, pl.DataFrame)

    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_owner_filter_in_query(self, mock_read_db, mock_url):
        mock_read_db.return_value = _make_accounts_df()

        from src.services.db_reader import read_accounts
        read_accounts(owner="personal")

        query = mock_read_db.call_args[1]["query"]
        assert "personal" in query

    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_no_owner_filter_when_owner_none(self, mock_read_db, mock_url):
        mock_read_db.return_value = _make_accounts_df()

        from src.services.db_reader import read_accounts
        read_accounts(owner=None)

        query = mock_read_db.call_args[1]["query"]
        # La clause WHERE est toujours là (is_active = true), mais sans filtre owner
        assert "is_active" in query
        assert "owner = " not in query


# ---------------------------------------------------------------------------
# read_monthly_revenue
# ---------------------------------------------------------------------------

class TestReadMonthlyRevenue:
    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_business_id_and_year_in_query(self, mock_read_db, mock_url):
        mock_read_db.return_value = pl.DataFrame({
            "month": pl.Series([1, 2, 3], dtype=pl.Int32),
            "revenue": pl.Series([1000.0, 1500.0, 800.0], dtype=pl.Float64),
        })

        from src.services.db_reader import read_monthly_revenue
        read_monthly_revenue(business_id="phi_rising", year=2024)

        query = mock_read_db.call_args[1]["query"]
        assert "phi_rising" in query
        assert "2024" in query

    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_returns_dataframe(self, mock_read_db, mock_url):
        mock_read_db.return_value = pl.DataFrame({
            "month": pl.Series([1], dtype=pl.Int32),
            "revenue": pl.Series([500.0], dtype=pl.Float64),
        })

        from src.services.db_reader import read_monthly_revenue
        result = read_monthly_revenue(business_id="booth_in_lyon", year=2024)
        assert isinstance(result, pl.DataFrame)


# ---------------------------------------------------------------------------
# read_patrimoine_evolution
# ---------------------------------------------------------------------------

class TestReadPatrimoineEvolution:
    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_owner_filter_in_query(self, mock_read_db, mock_url):
        mock_read_db.return_value = pl.DataFrame({
            "date": pl.Series([date(2024, 1, 1)], dtype=pl.Date),
            "total_balance": pl.Series([25000.0], dtype=pl.Float64),
        })

        from src.services.db_reader import read_patrimoine_evolution
        read_patrimoine_evolution(owner="personal")

        query = mock_read_db.call_args[1]["query"]
        assert "personal" in query
        assert "JOIN accounts" in query

    @patch("src.services.db_reader.get_db_url", return_value="postgresql://test")
    @patch("src.services.db_reader.pl.read_database")
    def test_year_filter_in_query(self, mock_read_db, mock_url):
        mock_read_db.return_value = pl.DataFrame({
            "date": pl.Series([date(2024, 1, 1)], dtype=pl.Date),
            "total_balance": pl.Series([25000.0], dtype=pl.Float64),
        })

        from src.services.db_reader import read_patrimoine_evolution
        read_patrimoine_evolution(year=2024)

        query = mock_read_db.call_args[1]["query"]
        assert "2024" in query
