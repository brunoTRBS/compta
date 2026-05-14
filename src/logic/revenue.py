"""Agrégations de revenus et calcul de la marge nette via Polars."""

from decimal import Decimal

import polars as pl

from src.config import BusinessId
from src.logic.urssaf import compute_cotisations


def aggregate_monthly(df: pl.DataFrame, year: int) -> pl.DataFrame:
    """Agrège les transactions par mois pour une année donnée.

    Les 12 mois sont toujours présents (valeur 0.0 pour les mois sans données).
    Retourne : month (Int32), revenue (Float64), expenses (Float64), net (Float64).
    """
    monthly = (
        df.lazy()
        .filter(pl.col("date").dt.year() == year)
        .with_columns(pl.col("date").dt.month().alias("month"))
        .group_by("month")
        .agg(
            pl.col("amount").filter(pl.col("amount") > 0).sum().fill_null(0).alias("revenue"),
            pl.col("amount").filter(pl.col("amount") < 0).sum().abs().fill_null(0).alias("expenses"),
        )
        .with_columns((pl.col("revenue") - pl.col("expenses")).alias("net"))
        .collect()
    )

    all_months = pl.DataFrame({"month": list(range(1, 13))}, schema={"month": pl.Int32})
    return (
        all_months.join(monthly, on="month", how="left")
        .with_columns(
            pl.col("revenue").fill_null(0.0),
            pl.col("expenses").fill_null(0.0),
            pl.col("net").fill_null(0.0),
        )
        .sort("month")
    )


def compute_ytd_summary(
    df: pl.DataFrame,
    business_id: BusinessId,
    year: int,
    with_versement_liberatoire: bool = False,
) -> dict:
    """Calcule un résumé YTD : CA, charges, cotisations, marge nette.

    Returns:
        dict avec les clés : ca, expenses, cotisations, versement_liberatoire,
        total_charges, net_margin, ca_threshold, is_above_threshold.
    """
    yearly = df.filter(pl.col("date").dt.year() == year)

    ca = float(yearly.filter(pl.col("amount") > 0)["amount"].sum() or 0.0)
    expenses = abs(float(yearly.filter(pl.col("amount") < 0)["amount"].sum() or 0.0))

    urssaf = compute_cotisations(
        Decimal(str(round(ca, 2))),
        business_id,
        with_versement_liberatoire=with_versement_liberatoire,
    )

    return {
        "ca": ca,
        "expenses": expenses,
        "cotisations": float(urssaf.cotisations),
        "versement_liberatoire": float(urssaf.versement_liberatoire),
        "total_charges": float(urssaf.total_charges),
        "net_margin": ca - expenses - float(urssaf.total_charges),
        "ca_threshold": float(urssaf.ca_threshold),
        "is_above_threshold": urssaf.is_above_threshold,
    }


def compute_net_margin(ca: float, expenses: float, total_charges: float) -> float:
    """Calcule la marge nette : CA - charges - cotisations."""
    return ca - expenses - total_charges
