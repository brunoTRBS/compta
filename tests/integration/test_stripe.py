"""Tests d'intégration Stripe — tous les appels API sont mockés."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


# ---------------------------------------------------------------------------
# Tests : map_payment_intent (fonction pure, aucun mock requis)
# ---------------------------------------------------------------------------

class TestMapPaymentIntent:
    def setup_method(self):
        from src.services.stripe_client import map_payment_intent
        self.map = map_payment_intent

    def _pi(self, **kwargs) -> dict:
        defaults = {
            "id": "pi_test123",
            "amount": 150000,   # 1500,00 €
            "currency": "eur",
            "status": "succeeded",
            "created": int(datetime(2024, 3, 15, 10, 0).timestamp()),
            "description": "Coaching session mars",
            "metadata": {"business_id": "phi_rising"},
        }
        return {**defaults, **kwargs}

    def test_converts_amount_to_euros(self):
        result = self.map(self._pi(amount=150000), "phi_rising")
        assert result["amount"] == pytest.approx(1500.0)

    def test_maps_date_from_timestamp(self):
        result = self.map(self._pi(), "phi_rising")
        assert result["date"] == "2024-03-15"

    def test_source_is_stripe(self):
        result = self.map(self._pi(), "phi_rising")
        assert result["source"] == "stripe"

    def test_external_id_is_pi_id(self):
        result = self.map(self._pi(id="pi_abc"), "phi_rising")
        assert result["external_id"] == "pi_abc"

    def test_category_revenue_for_positive(self):
        result = self.map(self._pi(amount=100_00), "phi_rising")
        assert result["category"] == "revenue"

    def test_category_refund_for_negative(self):
        result = self.map(self._pi(amount=-50_00), "phi_rising")
        assert result["category"] == "refund_received"

    def test_uses_description_as_label(self):
        result = self.map(self._pi(description="Cours en ligne"), "phi_rising")
        assert result["label"] == "Cours en ligne"

    def test_fallback_label_when_no_description(self):
        result = self.map(self._pi(id="pi_abcdef123", description=None), "phi_rising")
        assert "pi_abcdef123" in result["label"]

    def test_business_id_set_correctly(self):
        result = self.map(self._pi(), "booth_in_lyon")
        assert result["business_id"] == "booth_in_lyon"


# ---------------------------------------------------------------------------
# Tests : map_stripe_cache_row
# ---------------------------------------------------------------------------

class TestMapStripeCacheRow:
    def setup_method(self):
        from src.services.stripe_client import map_stripe_cache_row
        self.map = map_stripe_cache_row

    def test_maps_stripe_id(self):
        pi = {
            "id": "pi_xyz", "amount": 5000, "currency": "eur",
            "status": "succeeded", "created": int(datetime(2024, 1, 1).timestamp()),
            "metadata": {}, "receipt_email": None, "description": None,
        }
        result = self.map(pi, "phi_rising")
        assert result["stripe_id"] == "pi_xyz"

    def test_amount_in_euros(self):
        pi = {
            "id": "pi_xyz", "amount": 5000, "currency": "eur",
            "status": "succeeded", "created": int(datetime(2024, 1, 1).timestamp()),
            "metadata": {}, "receipt_email": None, "description": None,
        }
        result = self.map(pi, "phi_rising")
        assert result["amount"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Tests : fetch_payment_intents (API Stripe mockée)
# ---------------------------------------------------------------------------

class TestFetchPaymentIntents:
    def _make_pi(self, pi_id: str, business_id: str, amount: int = 10000) -> MagicMock:
        mock = MagicMock()
        mock.get = lambda k, default=None: {
            "id": pi_id,
            "amount": amount,
            "currency": "eur",
            "status": "succeeded",
            "created": int(datetime(2024, 3, 1).timestamp()),
            "description": "Test",
            "metadata": {"business_id": business_id},
            "receipt_email": None,
        }.get(k, default)
        mock.__getitem__ = lambda self, k: mock.get(k)
        mock.metadata = {"business_id": business_id}
        return mock

    @patch("src.services.stripe_client._configure")
    @patch("src.services.stripe_client.stripe.PaymentIntent.list")
    def test_filters_by_business_id(self, mock_list, mock_configure):
        pi_phi = self._make_pi("pi_phi", "phi_rising")
        pi_booth = self._make_pi("pi_booth", "booth_in_lyon")
        mock_list.return_value.auto_paging_iter.return_value = iter([pi_phi, pi_booth])

        from src.services.stripe_client import fetch_payment_intents
        result = fetch_payment_intents("phi_rising")

        assert len(result) == 1

    @patch("src.services.stripe_client._configure")
    @patch("src.services.stripe_client.stripe.PaymentIntent.list")
    def test_empty_when_no_match(self, mock_list, mock_configure):
        pi = self._make_pi("pi_booth", "booth_in_lyon")
        mock_list.return_value.auto_paging_iter.return_value = iter([pi])

        from src.services.stripe_client import fetch_payment_intents
        result = fetch_payment_intents("phi_rising")
        assert result == []

    @patch("src.services.stripe_client._configure")
    @patch("src.services.stripe_client.stripe.PaymentIntent.list")
    def test_passes_created_after(self, mock_list, mock_configure):
        mock_list.return_value.auto_paging_iter.return_value = iter([])

        from src.services.stripe_client import fetch_payment_intents
        fetch_payment_intents("phi_rising", created_after=1700000000)

        call_kwargs = mock_list.call_args[1]
        assert call_kwargs["created"] == {"gte": 1700000000}
