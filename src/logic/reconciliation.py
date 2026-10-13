"""Contrôle de solde : l'app a-t-elle bien toutes les opérations de chaque compte ?

Chaque relevé importé donne le solde réel du compte à sa dernière date. Entre deux
soldes connus, la somme des opérations enregistrées dans l'app doit être égale à la
variation du solde. Un écart signale une période non importée, une opération
supprimée, ou une saisie manuelle qui ne correspond à rien sur le compte.
"""

from datetime import date as Date
from typing import Any

import polars as pl

# Arrondis bancaires : en dessous, on considère que c'est juste
TOLERANCE = 0.01

# Écritures sans mouvement réel sur le compte : la participation (dépense du budget
# perso déduite d'un virement reçu sur le compte commun) — voir household.py.
_NOT_A_BANK_MOVEMENT_SUFFIX = "_part"


def statement_closing_balance(rows: list[dict[str, Any]]) -> tuple[str, float] | None:
    """Solde du compte à la dernière date du relevé, ou None si le relevé n'en donne pas.

    Les lignes sont dans l'ordre du fichier. Pour une même date, la dernière ligne du
    fichier porte le solde final (Crédit Mutuel, solde après chaque opération) ;
    BoursoBank donne le même solde de fin de journée sur toutes les lignes du jour.
    """
    dated = [r for r in rows if r.get("balance") is not None]
    if not dated:
        return None
    last_date = max(r["date"] for r in dated)
    closing = [r for r in dated if r["date"] == last_date][-1]
    return last_date, float(closing["balance"])


def check_account(
    snapshots: pl.DataFrame,
    transactions: pl.DataFrame,
) -> list[dict[str, Any]]:
    """Compare, entre chaque paire de soldes connus, variation réelle et opérations de l'app.

    Args:
        snapshots: soldes connus du compte (colonnes date, balance).
        transactions: toutes les opérations du compte (virements et foyer compris),
            colonnes date, amount, external_id.

    Returns:
        Une entrée par période : {start, end, bank_change, app_change, gap}
        où gap = variation réelle - opérations de l'app (0 si tout est là).
    """
    if snapshots.height < 2:
        return []

    snaps = snapshots.select(["date", "balance"]).sort("date").to_dicts()
    tx = transactions
    if not tx.is_empty():
        tx = tx.filter(
            pl.col("external_id").is_null()
            | ~pl.col("external_id").str.ends_with(_NOT_A_BANK_MOVEMENT_SUFFIX)
        )

    periods: list[dict[str, Any]] = []
    for prev, cur in zip(snaps, snaps[1:], strict=False):
        start, end = _as_date(prev["date"]), _as_date(cur["date"])
        app_change = 0.0
        if not tx.is_empty():
            app_change = float(
                tx.filter((pl.col("date") > start) & (pl.col("date") <= end))["amount"].sum() or 0.0
            )
        bank_change = float(cur["balance"]) - float(prev["balance"])
        periods.append({
            "start": start,
            "end": end,
            "bank_change": round(bank_change, 2),
            "app_change": round(app_change, 2),
            "gap": round(bank_change - app_change, 2),
        })
    return periods


def account_status(periods: list[dict[str, Any]]) -> tuple[bool, float]:
    """(compte complet ?, total des écarts) — complet si chaque période tombe juste."""
    total_gap = round(sum(p["gap"] for p in periods), 2)
    return all(abs(p["gap"]) < TOLERANCE for p in periods), total_gap


def _as_date(value: Any) -> Date:
    return value if isinstance(value, Date) else Date.fromisoformat(str(value)[:10])
