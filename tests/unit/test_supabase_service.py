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


# ---------------------------------------------------------------------------
# insert_transfer
# ---------------------------------------------------------------------------

class TestInsertTransfer:
    @patch("src.services.supabase.get_supabase")
    def test_creates_two_linked_rows(self, mock_get):
        mock_client = _make_supabase_mock([{"id": "row-1"}, {"id": "row-2"}])
        mock_get.return_value = mock_client

        from src.services.supabase import insert_transfer
        insert_transfer(
            from_account_id="acc-booth",
            to_account_id="acc-perso",
            from_business_id="booth_in_lyon",
            to_business_id="personal",
            amount=200.0,
            date="2024-06-01",
            label="Retrait Revolut vers perso",
        )

        rows = mock_client.table.return_value.insert.call_args[0][0]
        assert len(rows) == 2
        assert all(r["is_transfer"] is True for r in rows)
        assert rows[0]["transfer_group_id"] == rows[1]["transfer_group_id"]

    @patch("src.services.supabase.get_supabase")
    def test_amounts_are_opposite_signs(self, mock_get):
        mock_client = _make_supabase_mock([{"id": "row-1"}, {"id": "row-2"}])
        mock_get.return_value = mock_client

        from src.services.supabase import insert_transfer
        insert_transfer(
            from_account_id="acc-a", to_account_id="acc-b",
            from_business_id="phi_rising", to_business_id="personal",
            amount=-150.0,  # signe fourni indifférent, doit toujours ressortir en valeur absolue
            date="2024-06-01", label="Virement",
        )

        rows = mock_client.table.return_value.insert.call_args[0][0]
        from_row = next(r for r in rows if r["account_id"] == "acc-a")
        to_row = next(r for r in rows if r["account_id"] == "acc-b")
        assert from_row["amount"] == -150.0
        assert to_row["amount"] == 150.0

    @patch("src.services.supabase.get_supabase")
    def test_business_id_follows_each_account(self, mock_get):
        mock_client = _make_supabase_mock([{"id": "row-1"}, {"id": "row-2"}])
        mock_get.return_value = mock_client

        from src.services.supabase import insert_transfer
        insert_transfer(
            from_account_id="acc-booth", to_account_id="acc-perso",
            from_business_id="booth_in_lyon", to_business_id="personal",
            amount=200.0, date="2024-06-01", label="Retrait",
        )

        rows = mock_client.table.return_value.insert.call_args[0][0]
        from_row = next(r for r in rows if r["account_id"] == "acc-booth")
        to_row = next(r for r in rows if r["account_id"] == "acc-perso")
        assert from_row["business_id"] == "booth_in_lyon"
        assert to_row["business_id"] == "personal"


# ---------------------------------------------------------------------------
# delete_transfer
# ---------------------------------------------------------------------------

class TestDeleteTransfer:
    @patch("src.services.supabase.get_supabase")
    def test_deletes_by_transfer_group_id(self, mock_get):
        mock_client = _make_supabase_mock([])
        mock_get.return_value = mock_client

        from src.services.supabase import delete_transfer
        delete_transfer("tg-123")

        mock_client.table.assert_called_with("transactions")
        mock_client.table.return_value.delete.return_value.eq.assert_called_with(
            "transfer_group_id", "tg-123"
        )


# ---------------------------------------------------------------------------
# delete_balance_snapshot
# ---------------------------------------------------------------------------

def _make_balance_snapshot_mock(remaining_data: list) -> MagicMock:
    """Mock dédié : delete().eq().execute() puis select().eq().order().limit().execute()."""
    mock = MagicMock()
    delete_execute = MagicMock()
    delete_execute.data = []
    mock.table.return_value.delete.return_value.eq.return_value.execute.return_value = delete_execute

    select_execute = MagicMock()
    select_execute.data = remaining_data
    (
        mock.table.return_value.select.return_value.eq.return_value
        .order.return_value.limit.return_value.execute.return_value
    ) = select_execute

    update_execute = MagicMock()
    update_execute.data = []
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value = update_execute

    return mock


class TestDeleteBalanceSnapshot:
    @patch("src.services.supabase.get_supabase")
    def test_deletes_the_snapshot_row(self, mock_get):
        mock_client = _make_balance_snapshot_mock([{"balance": 100.0}])
        mock_get.return_value = mock_client

        from src.services.supabase import delete_balance_snapshot
        delete_balance_snapshot("acc-1", "snap-1")

        mock_client.table.return_value.delete.return_value.eq.assert_called_with("id", "snap-1")

    @patch("src.services.supabase.get_supabase")
    def test_resets_balance_to_remaining_latest_snapshot(self, mock_get):
        mock_client = _make_balance_snapshot_mock([{"balance": 850.0}])
        mock_get.return_value = mock_client

        from src.services.supabase import delete_balance_snapshot
        delete_balance_snapshot("acc-1", "snap-1")

        mock_client.table.return_value.update.assert_called_with({"balance": 850.0})
        mock_client.table.return_value.update.return_value.eq.assert_called_with("id", "acc-1")

    @patch("src.services.supabase.get_supabase")
    def test_resets_balance_to_zero_when_no_snapshot_remains(self, mock_get):
        mock_client = _make_balance_snapshot_mock([])
        mock_get.return_value = mock_client

        from src.services.supabase import delete_balance_snapshot
        delete_balance_snapshot("acc-1", "snap-1")

        mock_client.table.return_value.update.assert_called_with({"balance": 0})


# ---------------------------------------------------------------------------
# Transactions récurrentes
# ---------------------------------------------------------------------------

class TestInsertRecurringTransaction:
    @patch("src.services.supabase.get_supabase")
    def test_returns_created_row(self, mock_get):
        row = {"label": "Loyer", "amount": -800.0, "business_id": "personal", "day_of_month": 5}
        created = {**row, "id": "rec-1"}
        mock_get.return_value = _make_supabase_mock([created])

        from src.services.supabase import insert_recurring_transaction
        result = insert_recurring_transaction(row)
        assert result["id"] == "rec-1"


class TestUpdateRecurringTransaction:
    @patch("src.services.supabase.get_supabase")
    def test_updates_given_fields(self, mock_get):
        mock_client = _make_supabase_mock([{"id": "rec-1", "is_active": False}])
        mock_get.return_value = mock_client

        from src.services.supabase import update_recurring_transaction
        update_recurring_transaction("rec-1", {"is_active": False})

        mock_client.table.return_value.update.assert_called_once_with({"is_active": False})
        mock_client.table.return_value.update.return_value.eq.assert_called_with("id", "rec-1")


class TestDeleteRecurringTransaction:
    @patch("src.services.supabase.get_supabase")
    def test_deletes_by_id(self, mock_get):
        mock_client = _make_supabase_mock([])
        mock_get.return_value = mock_client

        from src.services.supabase import delete_recurring_transaction
        delete_recurring_transaction("rec-1")

        mock_client.table.return_value.delete.return_value.eq.assert_called_with("id", "rec-1")


class TestMaterializeRecurringTransactions:
    @patch("src.services.supabase.get_supabase")
    def test_inserts_transaction_and_marks_materialized(self, mock_get):
        mock_client = _make_supabase_mock([{"id": "tx-1"}])
        mock_get.return_value = mock_client

        from src.services.supabase import materialize_recurring_transactions
        created = materialize_recurring_transactions([
            {
                "recurring_id": "rec-1",
                "year": 2026,
                "month": 7,
                "transaction": {"date": "2026-07-05", "amount": -800.0, "label": "Loyer"},
            }
        ])

        assert len(created) == 1
        mock_client.table.return_value.insert.assert_called_with(
            {"date": "2026-07-05", "amount": -800.0, "label": "Loyer"}
        )
        mock_client.table.return_value.update.assert_called_with(
            {"last_materialized_year": 2026, "last_materialized_month": 7}
        )
        mock_client.table.return_value.update.return_value.eq.assert_called_with("id", "rec-1")

    @patch("src.services.supabase.get_supabase")
    def test_handles_multiple_items(self, mock_get):
        mock_client = _make_supabase_mock([{"id": "tx-1"}])
        mock_get.return_value = mock_client

        from src.services.supabase import materialize_recurring_transactions
        created = materialize_recurring_transactions([
            {"recurring_id": "rec-1", "year": 2026, "month": 7, "transaction": {"amount": -10.0}},
            {"recurring_id": "rec-2", "year": 2026, "month": 7, "transaction": {"amount": 2000.0}},
        ])

        assert len(created) == 2
