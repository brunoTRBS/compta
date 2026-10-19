"""Application des règles de catégorisation automatique sur les transactions."""

from typing import Any

import polars as pl


def row_label_text(row: dict[str, Any]) -> str:
    """Texte où chercher le motif : le libellé ET le libellé brut de la banque, car une règle
    écrite sur « CARTE … CB*8589 » doit continuer de marcher quand le libellé est nettoyé."""
    return f"{row.get('label') or ''} {row.get('raw_label') or ''}".lower()


def rule_applies(rule: dict[str, Any], row: dict[str, Any]) -> bool:
    """La règle s'applique-t-elle à cette opération ? (activité, sens, puis motif)"""
    business_id = row["business_id"]
    if rule.get("business_id") is not None and rule["business_id"] != business_id:
        return False
    # Une règle sans activité s'applique à tout sauf au foyer, qui a ses propres catégories
    if rule.get("business_id") is None and business_id == "household":
        return False
    direction = "income" if (row.get("amount") or 0) > 0 else "expense"
    if rule.get("direction") and rule["direction"] != direction:
        return False
    return rule["pattern"].lower() in row_label_text(row)


def first_matching_rule(rules: list[dict[str, Any]], row: dict[str, Any]) -> dict[str, Any] | None:
    """La règle gagnante : la première qui s'applique (règles triées par priorité décroissante)."""
    return next((rule for rule in rules if rule_applies(rule, row)), None)


def apply_rules(df: pl.DataFrame, rules: list[dict]) -> pl.DataFrame:
    """Applique les règles de catégorisation sur les transactions sans catégorie.

    Les règles doivent être triées par priorité décroissante avant l'appel.
    Les transactions déjà catégorisées ne sont pas modifiées.

    Args:
        df: DataFrame de transactions.
        rules: Liste de règles depuis categorization_rules (triées par priority DESC).

    Returns:
        DataFrame complet avec les colonnes 'category' mises à jour.
    """
    if not rules or df.is_empty():
        return df

    has_category = df.filter(pl.col("category").is_not_null() & (pl.col("category") != ""))
    needs_category = df.filter(pl.col("category").is_null() | (pl.col("category") == ""))

    if needs_category.is_empty():
        return df

    categorized_rows = []
    for row in needs_category.iter_rows(named=True):
        matched_category = None
        matched_target = None
        winner = first_matching_rule(rules, row)
        if winner is not None:
            matched_category = winner["category"]
            matched_target = winner.get("target_business_id")

        # Une règle peut aussi ranger l'opération dans un autre budget (ex : Deliveroo
        # payé avec la carte du compte commun -> Perso)
        categorized_rows.append({
            **row,
            "category": matched_category,
            "business_id": matched_target or row["business_id"],
        })

    updated = pl.DataFrame(categorized_rows, schema=needs_category.schema)
    return pl.concat([has_category, updated]).sort("date", descending=True)


def get_pending_categorization(df: pl.DataFrame) -> pl.DataFrame:
    """Retourne les transactions sans catégorie, en attente de validation manuelle."""
    return df.filter(pl.col("category").is_null() | (pl.col("category") == ""))


def categorization_stats(df: pl.DataFrame) -> dict:
    """Statistiques de couverture de catégorisation."""
    total = len(df)
    if total == 0:
        return {"total": 0, "categorized": 0, "pending": 0, "coverage_pct": 0.0}

    categorized = len(df.filter(pl.col("category").is_not_null() & (pl.col("category") != "")))
    pending = total - categorized
    return {
        "total": total,
        "categorized": categorized,
        "pending": pending,
        "coverage_pct": round(categorized / total * 100, 1),
    }
