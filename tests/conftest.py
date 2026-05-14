"""Fixtures partagées pour l'ensemble de la suite de tests."""

import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stubs pour les packages tiers non installés dans l'environnement de test pur.
# Les modules src/services/ les importent au niveau module ; ces stubs évitent
# ModuleNotFoundError lors de la collecte pytest.
# ---------------------------------------------------------------------------
def _identity_decorator(*args, **kwargs):
    """Retourne la fonction décorée telle quelle (no-op decorator)."""
    if args and callable(args[0]):
        return args[0]
    return lambda f: f


if "streamlit" not in sys.modules:
    _st = MagicMock()
    _st.secrets = {}
    _st.session_state = {}
    _st.cache_data = MagicMock(side_effect=_identity_decorator)
    _st.cache_resource = MagicMock(side_effect=_identity_decorator)
    sys.modules["streamlit"] = _st

if "supabase" not in sys.modules:
    _supabase = MagicMock()
    _supabase.Client = MagicMock
    _supabase.create_client = MagicMock(return_value=MagicMock())
    sys.modules["supabase"] = _supabase

if "stripe" not in sys.modules:
    _stripe = MagicMock()
    sys.modules["stripe"] = _stripe

import pytest
from datetime import date

import polars as pl

from src.config import BusinessId, TransactionSource


@pytest.fixture
def mock_supabase():
    """Client Supabase mocké. Remplace src.services.supabase.get_supabase()."""
    mock = MagicMock()
    mock.table.return_value.select.return_value.execute.return_value.data = []
    mock.table.return_value.insert.return_value.execute.return_value.data = []
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    return mock


@pytest.fixture
def mock_stripe():
    """Client Stripe mocké."""
    mock = MagicMock()
    mock.PaymentIntent.list.return_value = MagicMock(data=[], has_more=False)
    return mock


@pytest.fixture
def mock_gocardless():
    """Client GoCardless mocké."""
    mock = MagicMock()
    mock.transactions.list.return_value = MagicMock(transactions=[])
    return mock


@pytest.fixture
def sample_transactions() -> pl.DataFrame:
    """DataFrame de transactions représentatif pour les tests unitaires."""
    return pl.DataFrame(
        {
            "id": ["t-001", "t-002", "t-003", "t-004", "t-005"],
            "date": pl.Series(
                [
                    date(2024, 1, 15),
                    date(2024, 1, 20),
                    date(2024, 2, 5),
                    date(2024, 2, 10),
                    date(2024, 2, 28),
                ],
                dtype=pl.Date,
            ),
            "amount": pl.Series(
                [1500.0, -200.0, 800.0, -50.0, 0.0],
                dtype=pl.Float64,
            ),
            "label": [
                "Coaching individuel",
                "Fournitures bureau Amazon",
                "Location photobooth mariage",
                "Carburant A7",
                "Virement interne",
            ],
            "source": [
                TransactionSource.STRIPE,
                TransactionSource.MANUAL,
                TransactionSource.BANK,
                TransactionSource.BANK,
                TransactionSource.MANUAL,
            ],
            "business_id": [
                BusinessId.PHI_RISING,
                BusinessId.PHI_RISING,
                BusinessId.BOOTH_IN_LYON,
                BusinessId.BOOTH_IN_LYON,
                BusinessId.PERSONAL,
            ],
            "category": ["revenue", "office_supplies", "revenue", "transport", "other"],
            "is_income": [True, False, True, False, False],
        }
    )


@pytest.fixture
def phi_rising_transactions(sample_transactions: pl.DataFrame) -> pl.DataFrame:
    """Sous-ensemble filtré sur Phi Rising uniquement."""
    return sample_transactions.filter(pl.col("business_id") == BusinessId.PHI_RISING)


@pytest.fixture
def booth_in_lyon_transactions(sample_transactions: pl.DataFrame) -> pl.DataFrame:
    """Sous-ensemble filtré sur Booth in Lyon uniquement."""
    return sample_transactions.filter(pl.col("business_id") == BusinessId.BOOTH_IN_LYON)
