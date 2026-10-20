"""Gestion des règles de catégorisation : statistiques, test d'un libellé, modifications.

Une règle range les opérations dont le libellé contient son motif : elle donne une catégorie
et, si elle le précise, un autre budget. Quand plusieurs règles s'appliquent, la première par
priorité décroissante gagne.
"""

from typing import Any

from src.logic.categories import SCOPE_LABELS
from src.logic.categorizer import first_matching_rule, rule_applies

BUDGET_LABELS: dict[str | None, str] = {None: "Tous (sauf le foyer)", **SCOPE_LABELS}
DIRECTION_LABELS: dict[str | None, str] = {None: "Les deux", "expense": "Dépenses", "income": "Revenus"}
TARGET_LABELS: dict[str | None, str] = {None: "Reste dans son budget", **SCOPE_LABELS}

_BY_LABEL = {
    "budget": {label: key for key, label in BUDGET_LABELS.items()},
    "direction": {label: key for key, label in DIRECTION_LABELS.items()},
    "target": {label: key for key, label in TARGET_LABELS.items()},
}


def sort_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Règles actives d'abord, par priorité décroissante (ordre d'application)."""
    return sorted(rules, key=lambda r: (not r.get("is_active", True), -(r.get("priority") or 0)))


def rule_stats(
    rules: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Pour chaque règle : à combien d'opérations elle s'applique, et pour combien elle gagne.

    « matches » compte toutes les opérations dont le libellé correspond ; « wins » celles où
    cette règle est la gagnante. Une règle active avec des correspondances mais aucune victoire
    est masquée par une règle plus prioritaire.
    """
    active = [r for r in sort_rules(rules) if r.get("is_active", True)]
    stats = {r["id"]: {"matches": 0, "wins": 0} for r in rules}
    for tx in transactions:
        for rule in rules:
            if rule_applies(rule, tx):
                stats[rule["id"]]["matches"] += 1
        winner = first_matching_rule(active, tx)
        if winner is not None:
            stats[winner["id"]]["wins"] += 1
    return stats


def which_rule(
    rules: list[dict[str, Any]],
    label: str,
    business_id: str,
    amount: float,
) -> dict[str, Any] | None:
    """La règle qui rangerait une opération fictive, ou None. (« Tester un libellé »)"""
    active = [r for r in sort_rules(rules) if r.get("is_active", True)]
    return first_matching_rule(active, {"label": label, "raw_label": label,
                                        "business_id": business_id, "amount": amount})


def diff_rules(
    current: list[dict[str, Any]],
    edited: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    """Différences entre les règles en base et le tableau modifié à l'écran.

    Args:
        current: règles en base.
        edited: lignes du tableau (clés id, Motif, Budget visé, Sens, Catégorie, Ranger dans,
            Priorité, Actif, Supprimer).

    Returns:
        (modifications {id: champs}, ids à supprimer, erreurs)
    """
    by_id = {r["id"]: r for r in current}
    updates: dict[str, dict[str, Any]] = {}
    deletes: list[str] = []
    errors: list[str] = []

    for row in edited:
        rule = by_id.get(row["id"])
        if rule is None:
            continue
        if row.get("Supprimer"):
            deletes.append(rule["id"])
            continue
        pattern = (row.get("Motif") or "").strip()
        category = (row.get("Catégorie") or "").strip()
        if not pattern or not category:
            errors.append(f"Règle « {rule['pattern']} » : le motif et la catégorie sont obligatoires.")
            continue
        wanted = {
            "pattern": pattern,
            "category": category,
            "business_id": _BY_LABEL["budget"].get(row.get("Budget visé"), rule.get("business_id")),
            "direction": _BY_LABEL["direction"].get(row.get("Sens"), rule.get("direction")),
            "target_business_id": _BY_LABEL["target"].get(row.get("Ranger dans"), rule.get("target_business_id")),
            "priority": int(row.get("Priorité") if row.get("Priorité") is not None else rule.get("priority") or 0),
            "is_active": bool(row.get("Actif")),
        }
        changes = {k: v for k, v in wanted.items() if v != rule.get(k)}
        if changes:
            updates[rule["id"]] = changes
    return updates, deletes, errors
