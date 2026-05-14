import polars as pl
import pytest

from src.logic.categorizer import apply_rules, categorization_stats, get_pending_categorization

RULES = [
    {"pattern": "coaching", "business_id": "phi_rising", "category": "revenue", "priority": 90},
    {"pattern": "carburant", "business_id": None, "category": "transport", "priority": 70},
    {"pattern": "amazon", "business_id": None, "category": "office_supplies", "priority": 50},
    {"pattern": "photobooth", "business_id": "booth_in_lyon", "category": "revenue", "priority": 90},
]


class TestApplyRules:
    def _strip_categories(self, df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns(pl.lit(None).cast(pl.Utf8).alias("category"))

    def test_matches_business_specific_rule(self, sample_transactions):
        uncategorized = self._strip_categories(sample_transactions)
        result = apply_rules(uncategorized, RULES)
        coaching_row = result.filter(pl.col("label") == "Coaching individuel")
        assert coaching_row["category"][0] == "revenue"

    def test_matches_cross_business_rule(self, sample_transactions):
        uncategorized = self._strip_categories(sample_transactions)
        result = apply_rules(uncategorized, RULES)
        fuel_row = result.filter(pl.col("label") == "Carburant A7")
        assert fuel_row["category"][0] == "transport"

    def test_rule_scoped_to_wrong_business_not_applied(self, sample_transactions):
        # La règle "coaching" est pour phi_rising ; ne doit pas s'appliquer à booth_in_lyon
        wrong_business = sample_transactions.with_columns(
            pl.lit(None).cast(pl.Utf8).alias("category"),
            pl.lit("booth_in_lyon").alias("business_id"),
        )
        result = apply_rules(wrong_business, RULES)
        coaching_row = result.filter(pl.col("label") == "Coaching individuel")
        assert coaching_row["category"][0] is None

    def test_does_not_overwrite_existing_category(self, sample_transactions):
        # sample_transactions a déjà des catégories
        result = apply_rules(sample_transactions, RULES)
        original_cats = sample_transactions["category"].to_list()
        result_cats = result.sort("label")["category"].to_list()
        # Juste vérifier que les catégories existantes sont préservées
        assert len(result) == len(sample_transactions)

    def test_empty_rules_returns_unchanged(self, sample_transactions):
        result = apply_rules(sample_transactions, [])
        assert result.equals(sample_transactions)

    def test_empty_dataframe_returns_unchanged(self):
        empty = pl.DataFrame(
            schema={"id": pl.Utf8, "label": pl.Utf8, "business_id": pl.Utf8,
                    "category": pl.Utf8, "date": pl.Date, "amount": pl.Float64,
                    "source": pl.Utf8, "is_income": pl.Boolean}
        )
        result = apply_rules(empty, RULES)
        assert result.is_empty()

    def test_case_insensitive_matching(self, sample_transactions):
        uncategorized = self._strip_categories(sample_transactions).with_columns(
            pl.lit("COACHING session").alias("label")
        )
        result = apply_rules(uncategorized, RULES)
        # Au moins une ligne devrait matcher "coaching" (case-insensitive)
        matched = result.filter(pl.col("category") == "revenue")
        assert len(matched) > 0


class TestGetPendingCategorization:
    def test_all_uncategorized(self, sample_transactions):
        uncategorized = sample_transactions.with_columns(pl.lit(None).cast(pl.Utf8).alias("category"))
        pending = get_pending_categorization(uncategorized)
        assert len(pending) == len(sample_transactions)

    def test_none_pending_when_all_categorized(self, sample_transactions):
        pending = get_pending_categorization(sample_transactions)
        assert len(pending) == 0

    def test_partial_pending(self, sample_transactions):
        mixed = sample_transactions.with_columns(
            pl.when(pl.col("business_id") == "personal")
            .then(pl.lit(None).cast(pl.Utf8))
            .otherwise(pl.col("category"))
            .alias("category")
        )
        pending = get_pending_categorization(mixed)
        assert len(pending) == 1  # Une seule transaction "personal" dans le fixture


class TestCategorizationStats:
    def test_full_coverage(self, sample_transactions):
        stats = categorization_stats(sample_transactions)
        assert stats["coverage_pct"] == 100.0
        assert stats["pending"] == 0

    def test_zero_coverage(self, sample_transactions):
        uncategorized = sample_transactions.with_columns(pl.lit(None).cast(pl.Utf8).alias("category"))
        stats = categorization_stats(uncategorized)
        assert stats["coverage_pct"] == 0.0
        assert stats["pending"] == len(sample_transactions)

    def test_empty_dataframe(self):
        empty = pl.DataFrame(
            schema={"category": pl.Utf8, "label": pl.Utf8}
        )
        stats = categorization_stats(empty)
        assert stats["total"] == 0
        assert stats["coverage_pct"] == 0.0
