"""Tri des opérations du compte commun (foyer).

Le compte commun est alimenté chaque mois par la participation de l'utilisatrice,
qui couvre toutes les dépenses communes. Ses opérations sont donc importées en
is_household (hors budget perso), à deux exceptions près, soumises à vérification :

- ses paiements avec sa propre carte : par défaut une dépense du foyer, mais
  certains sont des achats perso à compter dans son budget ;
- les virements qu'elle y fait : la participation mensuelle, qui devient une
  dépense dans son budget perso.
"""

import re
from typing import Any

from src.config import (
    JOINT_OWN_CARD,
    JOINT_OWN_NAME_PATTERNS,
    PARTICIPATION_CATEGORY,
    PARTICIPATION_LABEL,
    BusinessId,
)

KIND_CARD = "card"
KIND_PARTICIPATION = "participation"

_PARTICIPATION_SUFFIX = "_part"


def _bank_label(tx: dict[str, Any]) -> str:
    return (tx.get("raw_label") or tx.get("label") or "").upper()


def review_kind(tx: dict[str, Any]) -> str | None:
    """Type de vérification nécessaire pour une opération du compte commun, ou None.

    - KIND_CARD : paiement avec la carte de l'utilisatrice ;
    - KIND_PARTICIPATION : virement reçu de sa part (hors rejet de virement).
    """
    label = _bank_label(tx)
    if re.search(rf"\bCARTE {re.escape(JOINT_OWN_CARD)}\b", label):
        return KIND_CARD
    if (
        float(tx["amount"]) > 0
        and not label.startswith("REJ")
        and any(name in label for name in JOINT_OWN_NAME_PATTERNS)
    ):
        return KIND_PARTICIPATION
    return None


def classify_joint_transactions(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Marque les opérations du compte commun : toutes du foyer, certaines à vérifier."""
    return [
        {**tx, "is_household": True, "needs_review": review_kind(tx) is not None}
        for tx in transactions
    ]


def default_counts_in_budget(tx: dict[str, Any]) -> bool:
    """Proposition par défaut : un virement reçu d'elle est sa participation ;
    un paiement carte reste une dépense du foyer tant qu'elle ne dit pas « perso »."""
    return review_kind(tx) == KIND_PARTICIPATION


def participation_expense(tx: dict[str, Any]) -> dict[str, Any]:
    """Dépense perso correspondant à un virement de participation reçu sur le commun."""
    return {
        "date": str(tx["date"])[:10],
        "amount": -abs(float(tx["amount"])),
        "label": PARTICIPATION_LABEL,
        "raw_label": tx.get("raw_label") or tx.get("label"),
        "bank_category": None,
        "source": "bank",
        "business_id": str(BusinessId.PERSONAL),
        "account_id": tx.get("account_id"),
        "category": PARTICIPATION_CATEGORY,
        # Dérivé de la ligne bancaire : la valider deux fois ne crée pas 2 dépenses
        "external_id": f"{tx['external_id']}{_PARTICIPATION_SUFFIX}" if tx.get("external_id") else None,
        "notes": None,
        "is_household": False,
        "needs_review": False,
    }


def resolve_review(
    transactions: list[dict[str, Any]],
    counts_in_budget: dict[str, bool],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Applique les choix de l'utilisatrice sur les opérations à vérifier.

    Args:
        transactions: opérations needs_review (avec id).
        counts_in_budget: {id: True si l'opération compte dans son budget perso}.

    Returns:
        (mises_à_jour, participations) — mises_à_jour = [{id, is_household, needs_review}],
        participations = dépenses perso à créer pour les virements retenus.
    """
    updates: list[dict[str, Any]] = []
    participations: list[dict[str, Any]] = []
    for tx in transactions:
        keep = counts_in_budget.get(tx["id"], default_counts_in_budget(tx))
        kind = review_kind(tx)
        # Un achat perso sort du foyer ; un virement reste une rentrée du foyer,
        # c'est sa contrepartie (la participation) qui entre dans le budget perso.
        is_household = not (keep and kind == KIND_CARD)
        updates.append({"id": tx["id"], "is_household": is_household, "needs_review": False})
        if keep and kind == KIND_PARTICIPATION:
            participations.append(participation_expense(tx))
    return updates, participations
