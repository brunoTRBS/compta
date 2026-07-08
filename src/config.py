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
# URSSAF — Taux de cotisations sociales (micro-entreprise)
# Taux "principal" par activité, utilisé comme fallback pour les catégories
# non listées dans URSSAF_RATES_BY_CATEGORY.
# ---------------------------------------------------------------------------
URSSAF_RATES: dict[BusinessId, Decimal] = {
    BusinessId.PHI_RISING: Decimal("0.28"),     # BNC (taux principal)
    BusinessId.BOOTH_IN_LYON: Decimal("0.23"),  # revenus déclarés
}

# Taux par catégorie de revenu — prioritaire sur URSSAF_RATES.
# Phi Rising  : BNC 28 %, BIC 27 %, ND 0 % (frais Stripe déduits du BNC)
# Booth in Lyon : Évenement Privé 23 %, ND 0 %
URSSAF_RATES_BY_CATEGORY: dict[BusinessId, dict[str, Decimal]] = {
    BusinessId.PHI_RISING: {
        "BNC": Decimal("0.28"),
        "BIC": Decimal("0.27"),
        "ND": Decimal("0.00"),
    },
    BusinessId.BOOTH_IN_LYON: {
        "ND": Decimal("0.00"),
        "Évenement Privé": Decimal("0.23"),
    },
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


