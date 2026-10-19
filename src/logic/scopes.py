"""Affectation des opérations : à quel budget (activité) appartient une opération.

Un compte propose une affectation par défaut à ses opérations importées : le foyer pour
le compte commun, sinon l'activité propriétaire du compte. Une règle ou l'utilisatrice
peut ensuite la changer ligne par ligne (un achat perso payé avec la carte du commun).
"""

from typing import Any

from src.config import JOINT_ACCOUNT_NAME, BusinessId


def is_household(tx: dict[str, Any]) -> bool:
    """L'opération appartient au budget du foyer (compte commun)."""
    return tx.get("business_id") == str(BusinessId.HOUSEHOLD)


def default_business_id(account: dict[str, Any]) -> str:
    """Activité proposée par défaut aux opérations importées d'un compte :
    le foyer pour le compte commun, sinon l'activité propriétaire du compte."""
    if account.get("name") == JOINT_ACCOUNT_NAME:
        return str(BusinessId.HOUSEHOLD)
    return account["owner"]
