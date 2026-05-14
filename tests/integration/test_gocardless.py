"""Tests d'intégration GoCardless — tous les appels HTTP sont mockés."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# Tests : map_transaction (fonction pure, aucun mock requis)
# ---------------------------------------------------------------------------

class TestMapTransaction:
    def setup_method(self):
        from src.services.gocardless import map_transaction
        self.map = map_transaction

    def test_maps_basic_fields(self):
        raw = {
            "transactionId": "gc-txn-001",
            "bookingDate": "2024-03-15",
            "transactionAmount": {"amount": "-120.50", "currency": "EUR"},
            "remittanceInformationUnstructured": "Carburant Total",
        }
        result = self.map(raw, "personal")
        assert result["external_id"] == "gc-txn-001"
        assert result["date"] == "2024-03-15"
        assert result["amount"] == pytest.approx(-120.50)
        assert result["label"] == "Carburant Total"
        assert result["source"] == "bank"
        assert result["business_id"] == "personal"
        assert result["category"] is None

    def test_positive_amount_is_credit(self):
        raw = {
            "transactionId": "gc-txn-002",
            "bookingDate": "2024-03-20",
            "transactionAmount": {"amount": "1500.00", "currency": "EUR"},
            "debtorName": "Client Coaching",
        }
        result = self.map(raw, "phi_rising")
        assert result["amount"] == pytest.approx(1500.0)

    def test_fallback_label_order(self):
        # creditorName > debtorName > défaut
        raw = {"transactionId": "x", "bookingDate": "2024-01-01",
               "transactionAmount": {"amount": "-50", "currency": "EUR"},
               "creditorName": "SNCF"}
        assert self.map(raw, "personal")["label"] == "SNCF"

        raw2 = {"transactionId": "x", "bookingDate": "2024-01-01",
                "transactionAmount": {"amount": "100", "currency": "EUR"},
                "debtorName": "John Doe"}
        assert self.map(raw2, "personal")["label"] == "John Doe"

    def test_fallback_to_value_date(self):
        raw = {
            "transactionId": "gc-txn-003",
            "valueDate": "2024-03-18",
            "transactionAmount": {"amount": "-30.00", "currency": "EUR"},
        }
        result = self.map(raw, "personal")
        assert result["date"] == "2024-03-18"

    def test_fallback_external_id(self):
        raw = {
            "internalTransactionId": "internal-001",
            "bookingDate": "2024-03-01",
            "transactionAmount": {"amount": "-10.00", "currency": "EUR"},
        }
        result = self.map(raw, "personal")
        assert result["external_id"] == "internal-001"

    def test_missing_remittance_defaults_to_label(self):
        raw = {"transactionId": "x", "bookingDate": "2024-01-01",
               "transactionAmount": {"amount": "-5", "currency": "EUR"}}
        result = self.map(raw, "personal")
        assert result["label"] == "Transaction bancaire"


# ---------------------------------------------------------------------------
# Tests : fetch_transactions (appels HTTP mockés)
# ---------------------------------------------------------------------------

class TestFetchTransactions:
    @patch("src.services.gocardless.get_access_token", return_value="fake-token")
    @patch("src.services.gocardless.requests.get")
    def test_returns_booked_transactions(self, mock_get, mock_token):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "transactions": {
                    "booked": [
                        {"transactionId": "t1", "bookingDate": "2024-03-01",
                         "transactionAmount": {"amount": "-50.00", "currency": "EUR"}},
                    ],
                    "pending": [],
                }
            },
        )
        mock_get.return_value.raise_for_status = MagicMock()

        from src.services.gocardless import fetch_transactions
        result = fetch_transactions("account-uuid", date_from="2024-03-01", date_to="2024-03-31")

        assert len(result) == 1
        assert result[0]["transactionId"] == "t1"

    @patch("src.services.gocardless.get_access_token", return_value="fake-token")
    @patch("src.services.gocardless.requests.get")
    def test_excludes_pending(self, mock_get, mock_token):
        mock_get.return_value = MagicMock(
            json=lambda: {
                "transactions": {
                    "booked": [],
                    "pending": [{"transactionId": "p1"}],
                }
            }
        )
        mock_get.return_value.raise_for_status = MagicMock()

        from src.services.gocardless import fetch_transactions
        result = fetch_transactions("account-uuid")
        assert result == []

    @patch("src.services.gocardless.get_access_token", return_value="fake-token")
    @patch("src.services.gocardless.requests.get")
    def test_passes_date_params(self, mock_get, mock_token):
        mock_get.return_value = MagicMock(
            json=lambda: {"transactions": {"booked": [], "pending": []}}
        )
        mock_get.return_value.raise_for_status = MagicMock()

        from src.services.gocardless import fetch_transactions
        fetch_transactions("account-uuid", date_from="2024-01-01", date_to="2024-01-31")

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["params"]["date_from"] == "2024-01-01"
        assert call_kwargs["params"]["date_to"] == "2024-01-31"


# ---------------------------------------------------------------------------
# Tests : list_accounts (appels HTTP mockés)
# ---------------------------------------------------------------------------

class TestListAccounts:
    @patch("src.services.gocardless.get_access_token", return_value="fake-token")
    @patch("src.services.gocardless.requests.get")
    def test_returns_account_ids(self, mock_get, mock_token):
        mock_get.return_value = MagicMock(
            json=lambda: {"accounts": ["uuid-1", "uuid-2"]}
        )
        mock_get.return_value.raise_for_status = MagicMock()

        from src.services.gocardless import list_accounts
        result = list_accounts("req-id-123")
        assert result == ["uuid-1", "uuid-2"]

    @patch("src.services.gocardless.get_access_token", return_value="fake-token")
    @patch("src.services.gocardless.requests.get")
    def test_empty_requisition(self, mock_get, mock_token):
        mock_get.return_value = MagicMock(json=lambda: {"accounts": []})
        mock_get.return_value.raise_for_status = MagicMock()

        from src.services.gocardless import list_accounts
        assert list_accounts("empty-req") == []


# ---------------------------------------------------------------------------
# Tests : get_access_token (token refresh)
# ---------------------------------------------------------------------------

class TestGetAccessToken:
    def setup_method(self):
        import src.services.gocardless as gc
        gc._token_cache.clear()

    @patch("src.services.gocardless._get_cache", return_value={})
    @patch("src.services.gocardless._get_credentials", return_value=("id", "key"))
    @patch("src.services.gocardless.requests.post")
    def test_fetches_new_token(self, mock_post, mock_creds, mock_cache):
        mock_post.return_value = MagicMock(
            json=lambda: {"access": "new-token", "access_expires": 86400}
        )
        mock_post.return_value.raise_for_status = MagicMock()

        from src.services.gocardless import get_access_token
        token = get_access_token()

        mock_post.assert_called_once()
        assert token == "new-token"

    @patch("src.services.gocardless._get_cache")
    @patch("src.services.gocardless.requests.post")
    def test_reuses_cached_token(self, mock_post, mock_get_cache):
        mock_get_cache.return_value = {
            "_gc_token": {
                "access": "cached-token",
                "expires_at": datetime.now(tz=timezone.utc) + timedelta(hours=1),
            }
        }

        from src.services.gocardless import get_access_token
        token = get_access_token()

        mock_post.assert_not_called()
        assert token == "cached-token"
