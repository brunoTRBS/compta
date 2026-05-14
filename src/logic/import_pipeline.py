"""Pipeline d'import : déduplication → catégorisation → persistance."""

from dataclasses import dataclass, field
from typing import Any

import polars as pl

from src.logic.categorizer import apply_rules
from src.services.supabase import bulk_upsert_transactions, fetch_categorization_rules


@dataclass
class ImportReport:
    """Rapport de résultats d'un import."""

    source: str
    total_fetched: int = 0
    new: int = 0
    duplicates_ignored: int = 0
    auto_categorized: int = 0
    pending_manual: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.errors


def deduplicate(
    raw_transactions: list[dict[str, Any]],
    existing_external_ids: set[str],
) -> tuple[list[dict[str, Any]], int]:
    """Filtre les transactions déjà présentes en base (par external_id).

    Returns:
        (nouvelles_transactions, nb_doublons_ignorés)
    """
    new: list[dict[str, Any]] = []
    duplicates = 0
    for tx in raw_transactions:
        ext_id = tx.get("external_id")
        if ext_id and ext_id in existing_external_ids:
            duplicates += 1
        else:
            new.append(tx)
    return new, duplicates


def categorize(
    transactions: list[dict[str, Any]],
    rules: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    """Applique les règles de catégorisation automatique.

    Returns:
        (transactions_mises_à_jour, nb_catégorisées_auto, nb_en_attente)
    """
    if not transactions or not rules:
        return transactions, 0, len(transactions)

    df = pl.DataFrame(transactions)
    # Polars infère Null quand toutes les valeurs sont None — forcer Utf8 pour apply_rules
    if "category" not in df.columns or df.schema.get("category") == pl.Null:
        df = df.with_columns(pl.lit(None).cast(pl.Utf8).alias("category"))

    categorized_df = apply_rules(df, rules)
    result = categorized_df.to_dicts()

    auto = sum(1 for tx in result if tx.get("category"))
    pending = len(result) - auto
    return result, auto, pending


def run_full_pipeline(
    raw_transactions: list[dict[str, Any]],
    existing_external_ids: set[str],
    source: str,
) -> ImportReport:
    """Orchestre : déduplication → catégorisation → persistance en base.

    Args:
        raw_transactions: Transactions mappées vers le schéma `transactions`.
        existing_external_ids: external_id déjà présents en base.
        source: "bank" ou "stripe" (pour le rapport).

    Returns:
        ImportReport avec les statistiques complètes de l'import.
    """
    report = ImportReport(source=source, total_fetched=len(raw_transactions))

    # Étape 1 — Déduplication
    new_txs, report.duplicates_ignored = deduplicate(raw_transactions, existing_external_ids)
    report.new = len(new_txs)

    if not new_txs:
        return report

    # Étape 2 — Catégorisation automatique
    try:
        rules = fetch_categorization_rules()
        new_txs, report.auto_categorized, report.pending_manual = categorize(new_txs, rules)
    except Exception as exc:
        report.errors.append(f"Catégorisation impossible : {exc}")
        report.pending_manual = report.new

    # Étape 3 — Persistance
    try:
        bulk_upsert_transactions(new_txs)
    except Exception as exc:
        report.errors.append(f"Erreur de persistance : {exc}")

    return report
