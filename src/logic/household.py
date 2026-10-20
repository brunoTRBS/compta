"""Tri des opérations du compte commun (foyer).

Le compte commun est alimenté chaque mois par la participation de l'utilisatrice,
qui couvre toutes les dépenses communes. Ses opérations sont donc importées en
l'activité « household » (hors budget perso). Tout compte pour le foyer tant que
l'utilisatrice ne le change pas ligne par ligne (« Ça compte pour » dans À traiter), y compris
ses achats avec sa propre carte. Une seule exception, soumise à vérification :

- les virements qu'elle y fait : la participation mensuelle, qui devient une
  dépense dans son budget perso.
"""

import uuid
from typing import Any

from src.config import (
    EXCEPTIONAL_THRESHOLD,
    HOUSEHOLD_REGULAR_CATEGORIES,
    JOINT_OWN_NAME_PATTERNS,
    PARTICIPATION_CATEGORY,
    PARTICIPATION_LABEL,
    BusinessId,
)
from src.logic.scopes import default_business_id, is_household  # noqa: F401  (ré-exportés)
from src.logic.transfers import find_rejected_pairs

KIND_PARTICIPATION = "participation"

_PARTICIPATION_SUFFIX = "_part"


def _bank_label(tx: dict[str, Any]) -> str:
    return (tx.get("raw_label") or tx.get("label") or "").upper()


def review_kind(tx: dict[str, Any]) -> str | None:
    """Type de vérification nécessaire pour une opération du compte commun, ou None.

    - KIND_PARTICIPATION : virement reçu de sa part (hors rejet de virement).
    """
    label = _bank_label(tx)
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
