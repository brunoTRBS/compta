"""Tri des opérations du compte commun (foyer).

Le compte commun est alimenté chaque mois par la participation de l'utilisatrice,
qui couvre toutes les dépenses communes. Ses opérations sont donc importées en
l'activité « household » (hors budget perso), à deux exceptions près, soumises à vérification :

- ses paiements avec sa propre carte : par défaut une dépense du foyer, mais
  certains sont des achats perso à compter dans son budget ;
- les virements qu'elle y fait : la participation mensuelle, qui devient une
  dépense dans son budget perso.
"""

import re
import uuid
from typing import Any

from src.config import (
    EXCEPTIONAL_THRESHOLD,
    HOUSEHOLD_REGULAR_CATEGORIES,
    JOINT_ACCOUNT_NAME,
    JOINT_OWN_CARD,
    JOINT_OWN_NAME_PATTERNS,
    PARTICIPATION_CATEGORY,
    PARTICIPATION_LABEL,
    BusinessId,
)
from src.logic.transfers import find_rejected_pairs

KIND_CARD = "card"
KIND_PARTICIPATION = "participation"

_PARTICIPATION_SUFFIX = "_part"


def is_household(tx: dict[str, Any]) -> bool:
    """L'opération appartient au budget du foyer (compte commun)."""
    return tx.get("business_id") == str(BusinessId.HOUSEHOLD)


def default_business_id(account: dict[str, Any]) -> str:
    """Activité proposée par défaut aux opérations importées d'un compte :
    le foyer pour le compte commun, sinon l'activité propriétaire du compte."""
    if account.get("name") == JOINT_ACCOUNT_NAME:
        return str(BusinessId.HOUSEHOLD)
    return account["owner"]


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
    """Marque les opérations du compte commun : toutes du foyer, certaines à vérifier.

    Un virement rejeté et son rejet s'annulent : ils deviennent un virement interne
    (is_transfer), hors budget du foyer.
    """
    rows = [
        {**tx, "business_id": str(BusinessId.HOUSEHOLD), "needs_review": review_kind(tx) is not None}
        for tx in transactions
    ]
    for pair in find_rejected_pairs(rows, include_household=True):
        group_id = str(uuid.uuid4())
        for row in pair:
            row.update({"is_transfer": True, "transfer_group_id": group_id, "needs_review": False})
    return rows


def propose_exceptional(tx: dict[str, Any]) -> bool:
    """Opération du foyer à sortir du budget courant : gros montant (apport, caution,
    clôture de compte…), sauf catégories régulières par nature (salaire, prêt…)."""
    return (
        is_household(tx)
        and abs(float(tx["amount"])) >= EXCEPTIONAL_THRESHOLD
        and tx.get("category") not in HOUSEHOLD_REGULAR_CATEGORIES
    )


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
        "needs_review": False,
        "is_transfer": False,
        "transfer_group_id": None,
        "is_exceptional": False,
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
        (mises_à_jour, participations) — mises_à_jour = [{id, business_id, needs_review}],
        participations = dépenses perso à créer pour les virements retenus.
    """
    updates: list[dict[str, Any]] = []
    participations: list[dict[str, Any]] = []
    for tx in transactions:
        keep = counts_in_budget.get(tx["id"], default_counts_in_budget(tx))
        kind = review_kind(tx)
        # Un achat perso sort du foyer ; un virement reste une rentrée du foyer,
        # c'est sa contrepartie (la participation) qui entre dans le budget perso.
        business_id = BusinessId.PERSONAL if (keep and kind == KIND_CARD) else BusinessId.HOUSEHOLD
        updates.append({"id": tx["id"], "business_id": str(business_id), "needs_review": False})
        if keep and kind == KIND_PARTICIPATION:
            participations.append(participation_expense(tx))
    return updates, participations
