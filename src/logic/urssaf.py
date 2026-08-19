"""Calcul des cotisations sociales URSSAF pour micro-entrepreneur."""

from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

from src.config import (
    CA_THRESHOLDS,
    URSSAF_RATES,
    VERSEMENT_LIBERATOIRE_RATES,
    BusinessId,
)


class UrssafResult(NamedTuple):
    ca: Decimal
    cotisations: Decimal
    versement_liberatoire: Decimal
    total_charges: Decimal
    ca_threshold: Decimal
    is_above_threshold: bool


def compute_cotisations(
    ca: Decimal,
    business_id: BusinessId,
    with_versement_liberatoire: bool = False,
) -> UrssafResult:
    """Calcule les cotisations URSSAF pour un CA encaissé.

    En micro-entreprise, les cotisations sont calculées sur le CA total déclaré,
    sans plafonnement. Le dépassement du seuil déclenche uniquement une alerte.

    Args:
        ca: Chiffre d'affaires encaissé (Decimal, positif ou nul).
        business_id: Activité concernée.
        with_versement_liberatoire: Inclure le versement libératoire de l'IR.
    """
    if ca < Decimal("0"):
        raise ValueError(f"Le CA ne peut pas être négatif : {ca}")

    rate = URSSAF_RATES[business_id]
    threshold = CA_THRESHOLDS[business_id]

    cotisations = (ca * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    vl_rate = VERSEMENT_LIBERATOIRE_RATES[business_id] if with_versement_liberatoire else Decimal("0")
    versement_liberatoire = (ca * vl_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return UrssafResult(
        ca=ca,
        cotisations=cotisations,
        versement_liberatoire=versement_liberatoire,
        total_charges=cotisations + versement_liberatoire,
        ca_threshold=threshold,
        is_above_threshold=ca > threshold,
    )


def compute_quarterly_estimate(
    monthly_revenues: list[Decimal],
    business_id: BusinessId,
    quarter: int,
    with_versement_liberatoire: bool = False,
) -> UrssafResult:
    """Calcule les cotisations à verser pour un trimestre.

    Args:
        monthly_revenues: CA mensuel pour les 3 mois du trimestre.
        business_id: Activité concernée.
        quarter: Numéro du trimestre (1–4), pour validation uniquement.
        with_versement_liberatoire: Inclure le versement libératoire.
    """
    if len(monthly_revenues) != 3:
        raise ValueError(f"Un trimestre contient 3 mois, reçu {len(monthly_revenues)}")
    if not (1 <= quarter <= 4):
        raise ValueError(f"Le trimestre doit être entre 1 et 4, reçu {quarter}")

    ca_trimestre = sum(monthly_revenues, Decimal("0"))
    return compute_cotisations(ca_trimestre, business_id, with_versement_liberatoire)
