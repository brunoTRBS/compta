"""Simulateur de budget pro : « si je fais ces prestations, combien me reste-t-il ? ».

Ne lit ni n'écrit rien en base : on saisit des prestations futures (mois, catégorie, montant,
frais Stripe éventuels) et des charges habituelles ; le calcul de l'URSSAF est exactement celui
des pages Phi Rising / Booth (compute_ytd_summary), pour que la simulation et la réalité
donnent le même résultat à l'euro près.
"""

from datetime import date
from typing import Any

import polars as pl

from src.config import (
    CA_THRESHOLDS,
    TVA_FRANCHISE_THRESHOLDS,
    URSSAF_RATES_BY_CATEGORY,
    BusinessId,
)
from src.logic.revenue import _MONTH_LABELS, compute_ytd_summary

# Catégorie des frais Stripe : déduits du CA BNC avant le calcul de l'URSSAF (voir revenue.py)
STRIPE_CATEGORY = "Stripe"
CHARGES_CATEGORY = "Charges"

_FORECAST_MONTHS = 12


def categories_for(business_id: BusinessId) -> list[str]:
    """Catégories de chiffre d'affaires qui ont un taux URSSAF pour cette activité."""
    return list(URSSAF_RATES_BY_CATEGORY.get(business_id, {}))


def month_options(today: date, count: int = _FORECAST_MONTHS) -> list[str]:
    """Les `count` prochains mois à partir du mois en cours, au format « 2026-11 »."""
    options = []
    year, month = today.year, today.month
    for _ in range(count):
        options.append(f"{year}-{month:02d}")
        year, month = (year, month + 1) if month < 12 else (year + 1, 1)
    return options


def month_label(key: str) -> str:
    """« 2026-11 » → « Nov 2026 »."""
    year, month = key.split("-")
    return f"{_MONTH_LABELS[int(month)]} {year}"


def average_monthly_expenses(history: pl.DataFrame, today: date, months: int = 3) -> float:
    """Dépenses pro moyennes des `months` derniers mois terminés (frais Stripe exclus :
    ils sont saisis ligne par ligne dans la simulation). 0 si l'historique est vide."""
    if history.is_empty():
        return 0.0
    year, month = today.year, today.month
    wanted = []
    for _ in range(months):
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
        wanted.append(year * 12 + month)
    spent = history.filter(
        (pl.col("amount") < 0)
        & (pl.col("category").fill_null("") != STRIPE_CATEGORY)
        & ~pl.col("is_transfer").fill_null(False)
        & (pl.col("date").dt.year() * 12 + pl.col("date").dt.month()).is_in(wanted)
    )
    return round(abs(float(spent["amount"].sum() or 0.0)) / months, 2)


def simulate_month(
    prestations: list[dict[str, Any]],
    charges: float,
    business_id: BusinessId,
    month: str,
    with_versement_liberatoire: bool = False,
) -> dict[str, Any]:
    """Résultat d'un mois : CA, frais, URSSAF, charges, et ce qu'il reste.

    Args:
        prestations: lignes du mois, {category, amount, fees}.
        charges: charges pro du mois (abonnements, outils…), en euros positifs.
    """
    year, month_number = (int(part) for part in month.split("-"))
    day = date(year, month_number, 1)
    rows: list[dict[str, Any]] = []
    for item in prestations:
        amount = float(item.get("amount") or 0.0)
        fees = float(item.get("fees") or 0.0)
        if amount > 0:
            rows.append({"date": day, "amount": amount, "category": item.get("category")})
        if fees > 0:
            rows.append({"date": day, "amount": -fees, "category": STRIPE_CATEGORY})
    if charges > 0:
        rows.append({"date": day, "amount": -float(charges), "category": CHARGES_CATEGORY})

    frame = pl.DataFrame(
        rows,
        schema={"date": pl.Date, "amount": pl.Float64, "category": pl.Utf8},
    )
    summary = compute_ytd_summary(frame, business_id, year, with_versement_liberatoire)
    return {
        "month": month,
        "ca": summary["ca"],
        "stripe_fees": summary["stripe_fees"],
        "charges": float(charges),
        "urssaf": summary["total_charges"],
        "remaining": summary["net_margin"],
    }


def simulate(
    prestations: list[dict[str, Any]],
    charges: float,
    business_id: BusinessId,
    year_to_date_ca: float = 0.0,
    with_versement_liberatoire: bool = False,
    year: int | None = None,
) -> dict[str, Any]:
    """Simule tous les mois présents dans les prestations (charges identiques chaque mois).

    Args:
        year_to_date_ca: CA déjà encaissé depuis le 1er janvier de `year`.
        year: année suivie pour les seuils (None = tous les mois simulés comptent).

    Returns:
        {months: [résultat par mois, dans l'ordre], total: {...}, ca_after: CA de l'année
        après simulation, threshold, tva_threshold}.
    """
    by_month: dict[str, list[dict[str, Any]]] = {}
    for item in prestations:
        if item.get("month") and float(item.get("amount") or 0.0) > 0:
            by_month.setdefault(item["month"], []).append(item)

    months = [
        simulate_month(by_month[key], charges, business_id, key, with_versement_liberatoire)
        for key in sorted(by_month)
    ]
    total = {
        field: round(sum(m[field] for m in months), 2)
        for field in ("ca", "stripe_fees", "charges", "urssaf", "remaining")
    }
    return {
        "months": months,
        "total": total,
        "ca_after": round(
            year_to_date_ca + sum(m["ca"] for m in months if year is None or m["month"].startswith(f"{year}-")),
            2,
        ),
        "threshold": float(CA_THRESHOLDS[business_id]),
        "tva_threshold": float(TVA_FRANCHISE_THRESHOLDS[business_id]),
    }
