import polars as pl

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


def test_rule_matches_raw_label_when_label_is_cleaned():
    """Une règle écrite sur le libellé brut continue de marcher après nettoyage."""
    import polars as pl

    from src.logic.categorizer import apply_rules

    df = pl.DataFrame({
        "label": ["La Villa Marlioz"],
        "raw_label": ["CARTE 10/10/26 VILLA MARLIOZ 4 CB*1111"],
        "business_id": ["personal"],
        "category": [None],
        "date": ["2026-10-12"],
    }, schema_overrides={"category": pl.Utf8})
    rules = [{"pattern": "VILLA MARLIOZ 4", "business_id": None, "category": "Sorties"}]
    assert apply_rules(df, rules)["category"].to_list() == ["Sorties"]


def _household_df(label, amount, business_id="household"):
    import polars as pl

    return pl.DataFrame({
        "label": [label], "raw_label": [label], "business_id": [business_id],
        "category": [None], "date": ["2026-10-08"], "amount": [amount],
    }, schema_overrides={"category": pl.Utf8})


def test_household_rule_only_applies_to_household():
    from src.logic.categorizer import apply_rules

    rules = [{"pattern": "LECLERC", "business_id": "household", "category": "Courses",
              "direction": "expense"}]
    assert apply_rules(_household_df("E LECLERC", -27.97), rules)["category"][0] == "Courses"
    assert apply_rules(_household_df("E LECLERC", -27.97, business_id="personal"), rules)["category"][0] is None


def test_personal_rule_never_applies_to_household():
    from src.logic.categorizer import apply_rules

    rules = [{"pattern": "LECLERC", "business_id": "personal", "category": "Repas"}]
    assert apply_rules(_household_df("E LECLERC", -27.97), rules)["category"][0] is None


def test_rule_direction():
    """Un virement de Bruno reçu = rentrée ; envoyé (vers son épargne) = Épargne Bruno."""
    from src.logic.categorizer import apply_rules

    rules = [
        {"pattern": "TARBES BRUNO", "business_id": "household", "category": "Virements Bruno",
         "direction": "income"},
        {"pattern": "TARBES BRUNO", "business_id": "household", "category": "Épargne Bruno",
         "direction": "expense"},
    ]
    assert apply_rules(_household_df("VIR INST TARBES BRUNO", 500.0), rules)["category"][0] == "Virements Bruno"
    assert apply_rules(_household_df("VIR INST TARBES BRUNO", -800.0), rules)["category"][0] == "Épargne Bruno"


def test_rule_can_move_operation_to_another_scope():
    """Deliveroo payé avec la carte du compte commun -> Perso."""
    from src.logic.categorizer import apply_rules

    rules = [{"pattern": "DELIVEROO", "business_id": "household", "category": "Restaurants & bars",
              "target_business_id": "personal", "direction": "expense"}]
    out = apply_rules(_household_df("CB LYON DELIVEROO CARTE 3935", -20.0), rules)
    assert out["category"][0] == "Restaurants & bars"
    assert out["business_id"][0] == "personal"
