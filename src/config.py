"""
Constantes métier centralisées.
Mettre à jour les taux URSSAF chaque année (source : urssaf.fr/portail/home/independant/mes-cotisations).
"""

from decimal import Decimal
from enum import StrEnum


class BusinessId(StrEnum):
    PHI_RISING = "phi_rising"
    BOOTH_IN_LYON = "booth_in_lyon"
    PERSONAL = "personal"


class TransactionSource(StrEnum):
    BANK = "bank"
    STRIPE = "stripe"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# URSSAF — Taux de cotisations sociales 2024 (micro-entreprise)
# Phi Rising  : coaching / formation → BNC professions libérales
# Booth in Lyon : location photobooth → BIC prestations de services
# ---------------------------------------------------------------------------
URSSAF_RATES: dict[BusinessId, Decimal] = {
    BusinessId.PHI_RISING: Decimal("0.212"),     # BNC libéral hors CIPAV
    BusinessId.BOOTH_IN_LYON: Decimal("0.212"),  # BIC prestations de services
}

# Plafonds de CA annuels micro-entreprise 2024
CA_THRESHOLDS: dict[BusinessId, Decimal] = {
    BusinessId.PHI_RISING: Decimal("77700"),     # BNC / services
    BusinessId.BOOTH_IN_LYON: Decimal("77700"),  # BIC services
}

# Franchise en base de TVA 2024 (pas de TVA sous ces seuils)
TVA_FRANCHISE_THRESHOLDS: dict[BusinessId, Decimal] = {
    BusinessId.PHI_RISING: Decimal("36800"),
    BusinessId.BOOTH_IN_LYON: Decimal("36800"),
}

# ---------------------------------------------------------------------------
# Versements libératoires de l'impôt sur le revenu (optionnel)
# À activer si l'option a été choisie auprès de l'URSSAF
# ---------------------------------------------------------------------------
VERSEMENT_LIBERATOIRE_RATES: dict[BusinessId, Decimal] = {
    BusinessId.PHI_RISING: Decimal("0.022"),     # 2.2 % BNC
    BusinessId.BOOTH_IN_LYON: Decimal("0.017"),  # 1.7 % BIC services
}

# ---------------------------------------------------------------------------
# Catégories de transactions (référence partagée)
# ---------------------------------------------------------------------------
INCOME_CATEGORIES: frozenset[str] = frozenset({
    "revenue",
    "refund_received",
})

EXPENSE_CATEGORIES: frozenset[str] = frozenset({
    "office_supplies",
    "transport",
    "meals",
    "software",
    "marketing",
    "rent",
    "utilities",
    "groceries",
    "leisure",
    "savings",
    "other",
})
