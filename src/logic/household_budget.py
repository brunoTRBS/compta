"""Budget du foyer : ce qui entre sur le compte commun, ce qui en sort, et qui fait quoi.

Opérations concernées : activité « household » (compte commun), hors virements internes.
Les opérations exceptionnelles (apport, caution…) sont toujours traitées à part pour
ne pas fausser le budget courant. Parmi les sorties, les achats perso et l'épargne de
Bruno ne sont pas des dépenses communes : ils sont isolés (HOUSEHOLD_NON_COMMON_CATEGORIES).
"""

import re
import uuid
from typing import Any

import polars as pl

from src.config import HOUSEHOLD_NON_COMMON_CATEGORIES, JOINT_CARD_OWNERS
from src.logic.categorizer import apply_rules
from src.logic.household import propose_exceptional
from src.logic.inbox import rule_updates
from src.logic.transfers import find_rejected_pairs

UNCATEGORIZED = "non classé"
OTHER_PAYER = "Prélèvements & virements"

_CARD_RE = re.compile(r"\bCARTE (\d{4})\b")


def regular_operations(df: pl.DataFrame) -> pl.DataFrame:
    """Opérations du budget courant (hors exceptionnelles)."""
    if df.is_empty():
        return df
    return df.filter(~pl.col("is_exceptional").fill_null(False))


def exceptional_operations(df: pl.DataFrame) -> pl.DataFrame:
    if df.is_empty():
        return df
    return df.filter(pl.col("is_exceptional").fill_null(False))


def _is_non_common() -> pl.Expr:
    return pl.col("category").is_in(list(HOUSEHOLD_NON_COMMON_CATEGORIES))


def summarize(df: pl.DataFrame) -> dict[str, float]:
    """Totaux d'une période (opérations régulières attendues).

    Returns:
        {income, common_expenses, non_common, difference} — montants positifs sauf
        difference (= rentrées - toutes les sorties).
    """
    if df.is_empty():
        return {"income": 0.0, "common_expenses": 0.0, "non_common": 0.0, "difference": 0.0}
    income = float(df.filter(pl.col("amount") > 0)["amount"].sum() or 0.0)
    out = df.filter(pl.col("amount") < 0)
    non_common = abs(float(out.filter(_is_non_common())["amount"].sum() or 0.0))
    common = abs(float(out.filter(~_is_non_common().fill_null(False))["amount"].sum() or 0.0))
    return {
        "income": round(income, 2),
        "common_expenses": round(common, 2),
        "non_common": round(non_common, 2),
        "difference": round(income - common - non_common, 2),
    }


def common_expenses(df: pl.DataFrame) -> pl.DataFrame:
    """Dépenses communes (hors achats perso / épargne de Bruno), catégorie renseignée."""
    if df.is_empty():
        return df
    return df.filter(
        (pl.col("amount") < 0) & ~_is_non_common().fill_null(False)
    ).with_columns(pl.col("category").fill_null(UNCATEGORIZED))


def contributions(df: pl.DataFrame) -> pl.DataFrame:
    """Rentrées par catégorie (qui met quoi) : category, total, pct."""
    income = df.filter(pl.col("amount") > 0) if not df.is_empty() else df
    if income.is_empty():
        return pl.DataFrame(schema={"category": pl.Utf8, "total": pl.Float64, "pct": pl.Float64})
    grouped = (
        income.with_columns(pl.col("category").fill_null(UNCATEGORIZED))
        .group_by("category")
        .agg(pl.col("amount").sum().alias("total"))
        .sort("total", descending=True)
    )
    total = float(grouped["total"].sum())
    return grouped.with_columns((pl.col("total") / total * 100).round(1).alias("pct"))


def payer_of(tx: dict[str, Any]) -> str:
    """Qui a payé : titulaire de la carte, ou prélèvement / virement."""
    match = _CARD_RE.search((tx.get("raw_label") or tx.get("label") or "").upper())
    if match:
        return JOINT_CARD_OWNERS.get(match.group(1), f"Carte {match.group(1)}")
    return OTHER_PAYER


def spending_by_payer(df: pl.DataFrame) -> pl.DataFrame:
    """Dépenses communes par payeur : payer, total, count."""
    expenses = common_expenses(df)
    if expenses.is_empty():
        return pl.DataFrame(schema={"payer": pl.Utf8, "total": pl.Float64, "count": pl.UInt32})
    payers = [payer_of(r) for r in expenses.select(["label", "raw_label"]).to_dicts()]
    return (
        expenses.with_columns(pl.Series("payer", payers), pl.col("amount").abs())
        .group_by("payer")
        .agg(pl.col("amount").sum().alias("total"), pl.len().alias("count"))
        .sort("total", descending=True)
    )


def retro_classify(
    df: pl.DataFrame,
    rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Applique aux opérations du foyer déjà importées ce que fait désormais l'import :
    règles (catégorie, affectation), opérations exceptionnelles, virements rejetés.

    Returns:
        mises à jour [{id, champ: valeur…}] — seules les lignes qui changent.
    """
    if df.is_empty():
        return []
    updates: dict[str, dict[str, Any]] = {r["id"]: r for r in rule_updates(df, rules)}
    categorized = {r["id"]: r for r in apply_rules(df, rules).to_dicts()}

    for row_id, row in categorized.items():
        if not row.get("is_exceptional") and propose_exceptional(row):
            updates.setdefault(row_id, {"id": row_id})["is_exceptional"] = True

    for pair in find_rejected_pairs(list(categorized.values()), include_household=True):
        group_id = str(uuid.uuid4())
        for row in pair:
            updates.setdefault(row["id"], {"id": row["id"]}).update(
                {"is_transfer": True, "transfer_group_id": group_id}
            )

    return list(updates.values())


def operation_changes(original: dict[str, Any], edited: dict[str, Any]) -> dict[str, Any]:
    """Champs modifiés d'une opération corrigée dans le tableau du mois.

    Args:
        original: l'opération en base (label, category, is_exceptional).
        edited: la ligne du tableau (Libellé, Catégorie, Exceptionnel).

    Returns:
        {champ: nouvelle valeur} pour les seuls champs qui changent (vide si rien).
    """
    changes: dict[str, Any] = {}
    label = (edited.get("Libellé") or "").strip()
    if label and label != original["label"]:
        changes["label"] = label
    category = edited.get("Catégorie") or None
    if category != (original.get("category") or None):
        changes["category"] = category
    if bool(edited.get("Ne pas compter dans le mois")) != bool(original.get("is_exceptional")):
        changes["is_exceptional"] = bool(edited.get("Ne pas compter dans le mois"))
    return changes
