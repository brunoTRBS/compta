"""Page Transactions : rechercher, filtrer, corriger en groupe, déplacer d'un budget à l'autre.

Fonctions pures : l'écran ne fait que les appeler puis écrire en base.
"""

import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import polars as pl

from src.logic.categories import SCOPE_LABELS, resolve_category

NO_CATEGORY = "(non classé)"

PERIODS = ("Ce mois-ci", "Mois dernier", "3 derniers mois", "Cette année", "Tout", "Choisir…")


def period_bounds(
    choice: str,
    today: date,
    custom: tuple[date, date] | None = None,
) -> tuple[date | None, date | None]:
    """Bornes (début, fin) incluses d'une période ; (None, None) = sans limite."""
    first_of_month = today.replace(day=1)
    if choice == "Ce mois-ci":
        return first_of_month, today
    if choice == "Mois dernier":
        end = first_of_month - timedelta(days=1)
        return end.replace(day=1), end
    if choice == "3 derniers mois":
        month, year = first_of_month.month - 2, first_of_month.year
        if month < 1:
            month, year = month + 12, year - 1
        return date(year, month, 1), today
    if choice == "Cette année":
        return date(today.year, 1, 1), today
    if choice == "Choisir…" and custom:
        return custom
    return None, None


def normalize(text: str | None) -> str:
    """Minuscules sans accents : « Café » et « cafe » se trouvent mutuellement."""
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def filter_transactions(
    df: pl.DataFrame,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    businesses: list[str] | None = None,
    account_ids: list[str] | None = None,
    categories: list[str] | None = None,
    text: str = "",
    direction: str | None = None,
    min_amount: float = 0.0,
    only_review: bool = False,
    only_exceptional: bool = False,
    include_transfers: bool = False,
) -> pl.DataFrame:
    """Opérations correspondant aux filtres (tous les critères se cumulent).

    `categories` peut contenir NO_CATEGORY pour les opérations sans catégorie.
    `direction` : "expense", "income" ou None.
    """
    if df.is_empty():
        return df
    out = df
    if date_from:
        out = out.filter(pl.col("date") >= date_from)
    if date_to:
        out = out.filter(pl.col("date") <= date_to)
    if businesses:
        out = out.filter(pl.col("business_id").is_in(businesses))
    if account_ids:
        out = out.filter(pl.col("account_id").is_in(account_ids))
    if categories:
        named = [c for c in categories if c != NO_CATEGORY]
        wants_none = NO_CATEGORY in categories
        condition = pl.col("category").is_in(named)
        if wants_none:
            condition = condition | pl.col("category").is_null() | (pl.col("category") == "")
        out = out.filter(condition)
    if direction == "expense":
        out = out.filter(pl.col("amount") < 0)
    elif direction == "income":
        out = out.filter(pl.col("amount") > 0)
    if min_amount:
        out = out.filter(pl.col("amount").abs() >= min_amount)
    if only_review:
        out = out.filter(pl.col("needs_review").fill_null(False))
    if only_exceptional:
        out = out.filter(pl.col("is_exceptional").fill_null(False))
    if not include_transfers:
        out = out.filter(~pl.col("is_transfer").fill_null(False))
    needle = normalize(text.strip())
    if needle:
        haystack = [
            normalize(f"{label} {raw}")
            for label, raw in zip(out["label"].to_list(), out["raw_label"].to_list(), strict=True)
        ]
        out = out.filter(pl.Series([needle in h for h in haystack], dtype=pl.Boolean))
    return out.sort("date", descending=True)


def totals(df: pl.DataFrame) -> dict[str, float]:
    """Rentrées et dépenses du résultat (positives)."""
    if df.is_empty():
        return {"income": 0.0, "expenses": 0.0, "count": 0}
    return {
        "income": round(float(df.filter(pl.col("amount") > 0)["amount"].sum() or 0.0), 2),
        "expenses": round(abs(float(df.filter(pl.col("amount") < 0)["amount"].sum() or 0.0)), 2),
        "count": df.height,
    }


@dataclass
class EditPlan:
    """Modifications à écrire, et ce qui a été refusé."""

    updates: list[dict[str, Any]] = field(default_factory=list)   # [{id, champs…}]
    errors: list[str] = field(default_factory=list)


def _scope_label(scope: str) -> str:
    return SCOPE_LABELS.get(scope, scope)


def plan_edits(
    originals: list[dict[str, Any]],
    edited: list[dict[str, Any]],
    categories: dict[str, dict[str, set[str]]],
) -> EditPlan:
    """Différences entre les lignes affichées et leur état en base.

    Args:
        originals: opérations en base (id, label, business_id, category, amount, is_exceptional).
        edited: lignes du tableau (id, Libellé, Budget, Catégorie, Exceptionnel) ; Budget est
            la clé de l'activité (personal, household…).
        categories: {activité: {"expense": {noms}, "income": {noms}}}.
    """
    plan = EditPlan()
    by_id = {tx["id"]: tx for tx in originals}
    for row in edited:
        tx = by_id.get(row["id"])
        if tx is None:
            continue
        fields: dict[str, Any] = {}
        label = (row.get("Libellé") or "").strip()
        if label and label != tx["label"]:
            fields["label"] = label

        scope = row.get("Budget") or tx["business_id"]
        if scope != tx["business_id"]:
            fields["business_id"] = scope

        direction = "income" if float(tx["amount"]) > 0 else "expense"
        valid = categories.get(scope, {}).get(direction, set())
        current = tx.get("category") or None
        chosen = row.get("Catégorie") or None
        final, rejected = resolve_category(current, chosen, valid)
        if rejected:
            plan.errors.append(
                f"« {tx['label']} » : la catégorie « {chosen} » n'existe pas pour {_scope_label(scope)} "
                "(non appliquée)."
            )
        if final != current:
            fields["category"] = final

        exceptional = row.get("Ne pas compter dans le mois")
        if exceptional is not None and bool(exceptional) != bool(tx.get("is_exceptional")):
            fields["is_exceptional"] = bool(exceptional)

        if fields:
            plan.updates.append({"id": tx["id"], **fields})
    return plan


def plan_bulk(
    selected: list[dict[str, Any]],
    categories: dict[str, dict[str, set[str]]],
    *,
    business_id: str | None = None,
    category: str | None = None,
    exceptional: bool | None = None,
) -> EditPlan:
    """Applique les mêmes changements à toutes les opérations sélectionnées.

    Une catégorie qui n'existe pas pour le budget (ou le sens) d'une opération est refusée
    pour celle-ci ; ses autres changements s'appliquent.
    """
    edited = []
    for tx in selected:
        edited.append({
            "id": tx["id"],
            "Libellé": tx["label"],
            "Budget": business_id or tx["business_id"],
            "Catégorie": category or tx.get("category"),
            "Ne pas compter dans le mois": exceptional,
        })
    return plan_edits(selected, edited, categories)


def plan_delete(rows: list[dict[str, Any]]) -> tuple[list[str], list[str], int]:
    """Que supprimer pour ces opérations ?

    Returns:
        (ids isolés, groupes de virement entiers, nombre d'opérations importées d'un relevé).
        Un virement se supprime avec ses deux écritures ; une opération importée réapparaîtra
        si le même relevé est déposé de nouveau.
    """
    groups = sorted({r["transfer_group_id"] for r in rows if r.get("transfer_group_id")})
    ids = [r["id"] for r in rows if not r.get("transfer_group_id")]
    imported = sum(1 for r in rows if r.get("external_id"))
    return ids, groups, imported
