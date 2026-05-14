"""Tests unitaires du pipeline d'import (appels Supabase mockés)."""

import pytest
from unittest.mock import patch

from src.logic.import_pipeline import (
    ImportReport,
    categorize,
    deduplicate,
    run_full_pipeline,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_TRANSACTIONS = [
    {"external_id": "tx-001", "label": "Coaching session", "amount": 500.0,
     "date": "2024-03-01", "source": "stripe", "business_id": "phi_rising", "category": None},
    {"external_id": "tx-002", "label": "Carburant A7", "amount": -60.0,
     "date": "2024-03-05", "source": "bank", "business_id": "phi_rising", "category": None},
    {"external_id": "tx-003", "label": "Fournitures Amazon", "amount": -120.0,
     "date": "2024-03-10", "source": "bank", "business_id": "phi_rising", "category": None},
]

RULES = [
    {"pattern": "coaching", "business_id": "phi_rising", "category": "revenue", "priority": 90},
    {"pattern": "carburant", "business_id": None, "category": "transport", "priority": 70},
    {"pattern": "amazon", "business_id": None, "category": "office_supplies", "priority": 50},
]


# ---------------------------------------------------------------------------
# Tests : deduplicate
# ---------------------------------------------------------------------------

class TestDeduplicate:
    def test_no_duplicates(self):
        new, dupes = deduplicate(SAMPLE_TRANSACTIONS, existing_external_ids=set())
        assert len(new) == 3
        assert dupes == 0

    def test_all_duplicates(self):
        existing = {"tx-001", "tx-002", "tx-003"}
        new, dupes = deduplicate(SAMPLE_TRANSACTIONS, existing_external_ids=existing)
        assert len(new) == 0
        assert dupes == 3

    def test_partial_duplicates(self):
        existing = {"tx-001"}
        new, dupes = deduplicate(SAMPLE_TRANSACTIONS, existing_external_ids=existing)
        assert len(new) == 2
        assert dupes == 1

    def test_transaction_without_external_id_always_passes(self):
        txs = [{"label": "Espèces", "amount": -20.0, "external_id": None}]
        new, dupes = deduplicate(txs, existing_external_ids={"tx-001"})
        assert len(new) == 1
        assert dupes == 0

    def test_empty_input(self):
        new, dupes = deduplicate([], existing_external_ids={"tx-001"})
        assert new == []
        assert dupes == 0

    def test_does_not_mutate_input(self):
        existing = {"tx-001"}
        original_len = len(SAMPLE_TRANSACTIONS)
        deduplicate(SAMPLE_TRANSACTIONS, existing_external_ids=existing)
        assert len(SAMPLE_TRANSACTIONS) == original_len


# ---------------------------------------------------------------------------
# Tests : categorize
# ---------------------------------------------------------------------------

class TestCategorize:
    def test_applies_rules(self):
        result, auto, pending = categorize(SAMPLE_TRANSACTIONS, RULES)
        auto_cats = [tx["category"] for tx in result if tx["category"]]
        assert len(auto_cats) == auto

    def test_empty_rules_returns_all_pending(self):
        result, auto, pending = categorize(SAMPLE_TRANSACTIONS, rules=[])
        assert auto == 0
        assert pending == len(SAMPLE_TRANSACTIONS)

    def test_empty_transactions(self):
        result, auto, pending = categorize([], RULES)
        assert result == []
        assert auto == 0
        assert pending == 0

    def test_coaching_gets_revenue_category(self):
        txs = [SAMPLE_TRANSACTIONS[0]]  # "Coaching session"
        result, auto, _ = categorize(txs, RULES)
        assert result[0]["category"] == "revenue"
        assert auto == 1

    def test_carburant_gets_transport_category(self):
        txs = [SAMPLE_TRANSACTIONS[1]]  # "Carburant A7"
        result, auto, _ = categorize(txs, RULES)
        assert result[0]["category"] == "transport"

    def test_count_pending_manual(self):
        # tx-001 et tx-002 ont des règles, tx-003 devrait matcher "amazon"
        result, auto, pending = categorize(SAMPLE_TRANSACTIONS, RULES)
        assert auto + pending == len(SAMPLE_TRANSACTIONS)


# ---------------------------------------------------------------------------
# Tests : run_full_pipeline
# ---------------------------------------------------------------------------

class TestRunFullPipeline:
    def test_returns_import_report(self):
        with (
            patch("src.logic.import_pipeline.fetch_categorization_rules", return_value=RULES),
            patch("src.logic.import_pipeline.bulk_upsert_transactions", return_value=[]),
        ):
            report = run_full_pipeline(SAMPLE_TRANSACTIONS, set(), source="bank")
        assert isinstance(report, ImportReport)

    def test_new_count_correct(self):
        with (
            patch("src.logic.import_pipeline.fetch_categorization_rules", return_value=[]),
            patch("src.logic.import_pipeline.bulk_upsert_transactions", return_value=[]),
        ):
            report = run_full_pipeline(SAMPLE_TRANSACTIONS, set(), source="bank")
        assert report.new == 3
        assert report.duplicates_ignored == 0

    def test_dedup_counted(self):
        with (
            patch("src.logic.import_pipeline.fetch_categorization_rules", return_value=[]),
            patch("src.logic.import_pipeline.bulk_upsert_transactions", return_value=[]),
        ):
            report = run_full_pipeline(
                SAMPLE_TRANSACTIONS, {"tx-001", "tx-002"}, source="bank"
            )
        assert report.new == 1
        assert report.duplicates_ignored == 2

    def test_all_duplicates_skips_db(self):
        existing = {tx["external_id"] for tx in SAMPLE_TRANSACTIONS}
        with patch("src.logic.import_pipeline.bulk_upsert_transactions") as mock_upsert:
            report = run_full_pipeline(SAMPLE_TRANSACTIONS, existing, source="stripe")
        mock_upsert.assert_not_called()
        assert report.new == 0

    def test_db_error_recorded_in_report(self):
        with (
            patch("src.logic.import_pipeline.fetch_categorization_rules", return_value=[]),
            patch(
                "src.logic.import_pipeline.bulk_upsert_transactions",
                side_effect=Exception("DB unavailable"),
            ),
        ):
            report = run_full_pipeline(SAMPLE_TRANSACTIONS, set(), source="bank")
        assert not report.success
        assert len(report.errors) == 1
        assert "DB unavailable" in report.errors[0]

    def test_total_fetched_matches_input(self):
        with (
            patch("src.logic.import_pipeline.fetch_categorization_rules", return_value=[]),
            patch("src.logic.import_pipeline.bulk_upsert_transactions", return_value=[]),
        ):
            report = run_full_pipeline(SAMPLE_TRANSACTIONS, set(), source="bank")
        assert report.total_fetched == len(SAMPLE_TRANSACTIONS)

    def test_source_in_report(self):
        with (
            patch("src.logic.import_pipeline.fetch_categorization_rules", return_value=[]),
            patch("src.logic.import_pipeline.bulk_upsert_transactions", return_value=[]),
        ):
            report = run_full_pipeline([], set(), source="stripe")
        assert report.source == "stripe"
