"""Tests unitaires du service Supabase (client mocké)."""

import pytest
from unittest.mock import MagicMock, patch, call


def _make_supabase_mock(return_data: list | None = None) -> MagicMock:
    """Construit un mock Supabase qui retourne `return_data` sur .execute().data."""
    data = return_data or []
    mock = MagicMock()
    execute = MagicMock()
    execute.data = data
    # Chaîne : .table().xxx().yyy().execute()
    mock.table.return_value.insert.return_value.execute.return_value = execute
    mock.table.return_value.upsert.return_value.execute.return_value = execute
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value = execute
    mock.table.return_value.delete.return_value.eq.return_value.execute.return_value = execute
    mock.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = execute
    return mock


# ---------------------------------------------------------------------------
# upsert_transaction
# ---------------------------------------------------------------------------

class TestUpsertTransaction:
    @patch("src.services.supabase.get_supabase")
    def test_insert_when_no_id(self, mock_get):
        row = {"date": "2024-03-01", "amount": 500.0, "label": "Coaching", "source": "manual",
               "business_id": "phi_rising", "category": "revenue"}
        created = {**row, "id": "new-uuid"}
        mock_get.return_value = _make_supabase_mock([created])

        from src.services.supabase import upsert_transaction
        result = upsert_transaction(row)
        assert result["id"] == "new-uuid"

    @patch("src.services.supabase.get_supabase")
    def test_upsert_when_id_present(self, mock_get):
        row = {"id": "existing-uuid", "label": "Coaching modifié", "amount": 600.0,
               "date": "2024-03-01", "source": "manual", "business_id": "phi_rising"}
        updated = {**row}
        mock_get.return_value = _make_supabase_mock([updated])

        from src.services.supabase import upsert_transaction
        result = upsert_transaction(row)
        assert result["id"] == "existing-uuid"


# ---------------------------------------------------------------------------
# update_transaction
# ---------------------------------------------------------------------------

class TestUpdateTransaction:
    @patch("src.services.supabase.get_supabase")
    def test_updates_allowed_fields(self, mock_get):
        updated_row = {"id": "tx-1", "label": "Nouveau libellé", "amount": -80.0}
        mock_client = _make_supabase_mock([updated_row])
        mock_get.return_value = mock_client

        from src.services.supabase import update_transaction
        result = update_transaction("tx-1", {"label": "Nouveau libellé", "amount": -80.0})

        assert result["label"] == "Nouveau libellé"
        # Vérifie que .update() a bien été appelé
        mock_client.table.return_value.update.assert_called_once()

    @patch("src.services.supabase.get_supabase")
    def test_strips_immutable_fields(self, mock_get):
        mock_client = _make_supabase_mock([{"id": "tx-1"}])
        mock_get.return_value = mock_client

        from src.services.supabase import update_transaction
        # Passe des champs immutables — ils ne doivent pas arriver dans l'update
        update_transaction("tx-1", {
            "id": "autre-id",
            "created_at": "2020-01-01",
            "external_id": "gc-xxx",
            "label": "Label valide",
        })

        call_args = mock_client.table.return_value.update.call_args[0][0]
        assert "id" not in call_args
        assert "created_at" not in call_args
        assert "external_id" not in call_args
        assert "label" in call_args

    @patch("src.services.supabase.get_supabase")
    def test_empty_updates_calls_update_with_empty_dict(self, mock_get):
        mock_get.return_value = _make_supabase_mock([{"id": "tx-1"}])

        from src.services.supabase import update_transaction
        update_transaction("tx-1", {"id": "tx-1", "created_at": "..."})

        # Tous les champs étaient immutables → dict vide passé à update()
        from src.services.supabase import get_supabase
        mock_get.return_value.table.return_value.update.assert_called_once_with({})


# ---------------------------------------------------------------------------
# delete_transaction
# ---------------------------------------------------------------------------

class TestDeleteTransaction:
    @patch("src.services.supabase.get_supabase")
    def test_calls_delete_with_correct_id(self, mock_get):
        mock_client = _make_supabase_mock([])
        mock_get.return_value = mock_client

        from src.services.supabase import delete_transaction
        delete_transaction("tx-to-delete")

        mock_client.table.assert_called_with("transactions")
        mock_client.table.return_value.delete.assert_called_once()
        mock_client.table.return_value.delete.return_value.eq.assert_called_with(
            "id", "tx-to-delete"
        )

    @patch("src.services.supabase.get_supabase")
    def test_returns_none(self, mock_get):
        mock_get.return_value = _make_supabase_mock([])

        from src.services.supabase import delete_transaction
        result = delete_transaction("any-id")
        assert result is None


# ---------------------------------------------------------------------------
# bulk_update_categories
# ---------------------------------------------------------------------------

class TestBulkUpdateCategories:
    @patch("src.services.supabase.get_supabase")
    def test_calls_update_for_each_item(self, mock_get):
        mock_client = _make_supabase_mock([{"id": "x"}])
        mock_get.return_value = mock_client

        from src.services.supabase import bulk_update_categories
        updates = [
            {"id": "tx-1", "category": "transport"},
            {"id": "tx-2", "category": "groceries"},
        ]
        bulk_update_categories(updates)

        assert mock_client.table.return_value.update.call_count == 2

    @patch("src.services.supabase.get_supabase")
    def test_empty_list_does_nothing(self, mock_get):
        mock_client = _make_supabase_mock([])
        mock_get.return_value = mock_client

        from src.services.supabase import bulk_update_categories
        bulk_update_categories([])

        mock_client.table.return_value.update.assert_not_called()


# ---------------------------------------------------------------------------
# insert_transaction
# ---------------------------------------------------------------------------

class TestInsertTransaction:
    @patch("src.services.supabase.get_supabase")
    def test_returns_created_row(self, mock_get):
        row = {"date": "2024-01-01", "amount": -50.0, "label": "Courses", "source": "manual",
               "business_id": "personal", "category": "groceries"}
        created = {**row, "id": "new-id", "created_at": "2024-01-01T10:00:00"}
        mock_get.return_value = _make_supabase_mock([created])

        from src.services.supabase import insert_transaction
        result = insert_transaction(row)
        assert result["id"] == "new-id"
