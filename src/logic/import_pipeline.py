"""Pipeline d'import : déduplication → catégorisation → persistance."""

from dataclasses import dataclass, field
from datetime import date as Date
from typing import Any

import polars as pl

from src.logic.categorizer import apply_rules
from src.logic.household import propose_exceptional
from src.logic.transfers import detect_transfers
from src.services.supabase import (
    bulk_update_transaction_fields,
    bulk_upsert_transactions,
    fetch_categorization_rules,
    link_transactions_to_bank,
)

# Écart max (en jours) entre une saisie manuelle et la ligne du relevé
# correspondante : la banque enregistre souvent un paiement carte 1 à 3 jours
# après l'achat.
MANUAL_MATCH_WINDOW_DAYS = 4


@dataclass
class ImportReport:
    """Rapport de résultats d'un import."""

    source: str
    total_fetched: int = 0
    new: int = 0
    duplicates_ignored: int = 0
    linked_manual: int = 0
    transfers_detected: int = 0
    transfers_to_review: int = 0
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
    """Filtre les transactions déjà présentes en base ET les doublons intra-batch.

    Returns:
        (nouvelles_transactions, nb_doublons_ignorés)
    """
    new: list[dict[str, Any]] = []
    duplicates = 0
    seen_in_batch: set[str] = set()
    for tx in raw_transactions:
        ext_id = tx.get("external_id")
        if ext_id and (ext_id in existing_external_ids or ext_id in seen_in_batch):
            duplicates += 1
        else:
            new.append(tx)
            if ext_id:
                seen_in_batch.add(ext_id)
    return new, duplicates


def _as_date(value: Any) -> Date:
    return value if isinstance(value, Date) else Date.fromisoformat(str(value)[:10])


def match_manual_entries(
    bank_transactions: list[dict[str, Any]],
    manual_transactions: list[dict[str, Any]],
    window_days: int = MANUAL_MATCH_WINDOW_DAYS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rapproche les lignes du relevé des transactions déjà saisies à la main.

    Une ligne bancaire correspond à une saisie manuelle si le montant est
    identique, l'écart de date ≤ window_days, et le compte de la saisie est le
    même (ou non renseigné de part ou d'autre). Chaque saisie ne sert qu'une fois ; à égalité, la
    plus proche en date gagne.

    Returns:
        (lignes_bancaires_sans_correspondance, liens) où chaque lien vaut
        {id, external_id, raw_label, bank_category, account_id} : la saisie
        manuelle garde son libellé et sa catégorie, et reçoit l'identifiant
        bancaire pour ne plus être proposée aux imports suivants.
    """
    unused = list(manual_transactions)
    unmatched: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []

    for tx in sorted(bank_transactions, key=lambda t: str(t["date"])):
        tx_date = _as_date(tx["date"])
        tx_amount = round(float(tx["amount"]), 2)
        best, best_gap = None, None
        for cand in unused:
            if round(float(cand["amount"]), 2) != tx_amount:
                continue
            if cand.get("account_id") and tx.get("account_id") and cand["account_id"] != tx["account_id"]:
                continue
            gap = abs((_as_date(cand["date"]) - tx_date).days)
            if gap <= window_days and (best_gap is None or gap < best_gap):
                best, best_gap = cand, gap
        if best is None:
            unmatched.append(tx)
            continue
        unused.remove(best)
        links.append({
            "id": best["id"],
            "external_id": tx.get("external_id"),
            "raw_label": tx.get("raw_label"),
            "bank_category": tx.get("bank_category"),
            "account_id": tx.get("account_id"),
        })
    return unmatched, links


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
    manual_transactions: list[dict[str, Any]] | None = None,
    existing_bank_transactions: list[dict[str, Any]] | None = None,
) -> ImportReport:
    """Orchestre : déduplication → rapprochement des saisies manuelles →
    catégorisation → persistance en base.

    Args:
        raw_transactions: Transactions mappées vers le schéma `transactions`.
        existing_external_ids: external_id déjà présents en base.
        source: "bank" ou "stripe" (pour le rapport).
        manual_transactions: saisies manuelles candidates au rapprochement
            (relevés bancaires uniquement) — voir match_manual_entries.
        existing_bank_transactions: lignes bancaires déjà en base pouvant être
            l'autre côté d'un virement (relevés bancaires uniquement) — voir
            transfers.detect_transfers. None = pas de détection des virements.

    Returns:
        ImportReport avec les statistiques complètes de l'import.
    """
    report = ImportReport(source=source, total_fetched=len(raw_transactions))

    # Étape 1 — Déduplication
    new_txs, report.duplicates_ignored = deduplicate(raw_transactions, existing_external_ids)

    # Étape 1 bis — Rapprochement avec les saisies manuelles existantes
    links: list[dict[str, Any]] = []
    if manual_transactions:
        new_txs, links = match_manual_entries(new_txs, manual_transactions)
        report.linked_manual = len(links)
        try:
            link_transactions_to_bank(links)
        except Exception as exc:
            report.errors.append(f"Rapprochement des saisies manuelles impossible : {exc}")

    report.new = len(new_txs)
    if not new_txs:
        return report

    # Étape 1 ter — Virements internes (rejets, 2 côtés importés, à vérifier)
    if existing_bank_transactions is not None:
        new_txs, existing_updates, report.transfers_detected = detect_transfers(
            new_txs, existing_bank_transactions
        )
        report.transfers_to_review = sum(
            1 for tx in new_txs if tx.get("needs_review") and tx.get("business_id") != "household"
        )
        try:
            bulk_update_transaction_fields(existing_updates)
        except Exception as exc:
            report.errors.append(f"Mise à jour des virements existants impossible : {exc}")

    # Étape 2 — Catégorisation automatique
    try:
        rules = fetch_categorization_rules()
        new_txs, report.auto_categorized, report.pending_manual = categorize(new_txs, rules)
    except Exception as exc:
        report.errors.append(f"Catégorisation impossible : {exc}")
        report.pending_manual = report.new

    # Étape 2 bis — Opérations exceptionnelles du foyer (après catégorisation : un
    # salaire ou une échéance de prêt n'est jamais exceptionnel)
    for tx in new_txs:
        if propose_exceptional(tx):
            tx["is_exceptional"] = True

    # Étape 3 — Persistance
    try:
        bulk_upsert_transactions(new_txs)
    except Exception as exc:
        report.errors.append(f"Erreur de persistance : {exc}")

    return report
