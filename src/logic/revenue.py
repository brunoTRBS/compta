"""Agrégations de revenus et calcul de la marge nette via Polars."""

from decimal import Decimal
from typing import Literal

import polars as pl

from src.config import BusinessId, URSSAF_RATES
from src.logic.urssaf import compute_cotisations

_MONTH_LABELS: dict[int, str] = {
    1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Aoû", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Déc",
}


def _month_label(month_num: int, year: int) -> str:
    return f"{_MONTH_LABELS[month_num]} {str(year)[2:]}"


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


def aggregate_revenue_by_category(
    df: pl.DataFrame,
    business_id: BusinessId,
) -> pl.DataFrame:
    """Revenus par catégorie : ca_brut, urssaf (proportionnel), ca_net, pct_ca.

    L'URSSAF est calculée au taux de l'activité appliqué sur le CA brut de chaque
    catégorie — cohérent avec le calcul global puisque le taux est uniforme.
    Retourne : category, ca_brut, urssaf, ca_net, pct_ca (Float64).
    """
    income = df.filter(pl.col("amount") > 0).with_columns(
        pl.col("category").fill_null("non classé")
    )
    total_ca = float(income["amount"].sum() or 0.0)

    by_cat = (
        income
        .group_by("category")
        .agg(pl.col("amount").sum().alias("ca_brut"))
        .sort("ca_brut", descending=True)
    )

    if by_cat.is_empty() or total_ca == 0.0:
        return by_cat.with_columns(
            pl.lit(0.0).alias("urssaf"),
            pl.lit(0.0).alias("ca_net"),
            pl.lit(0.0).alias("pct_ca"),
        )

    rate = float(URSSAF_RATES[business_id])
    return by_cat.with_columns(
        (pl.col("ca_brut") * rate).round(2).alias("urssaf"),
        (pl.col("ca_brut") * (1.0 - rate)).round(2).alias("ca_net"),
        (pl.col("ca_brut") / total_ca * 100.0).round(1).alias("pct_ca"),
    )


def aggregate_expenses_by_category(df: pl.DataFrame) -> pl.DataFrame:
    """Dépenses par catégorie : total (valeur absolue), pct.

    Retourne : category, total, pct (Float64).
    """
    expenses = (
        df.filter(pl.col("amount") < 0)
        .with_columns(
            pl.col("amount").abs().alias("amount"),
            pl.col("category").fill_null("non classé"),
        )
    )
    total_exp = float(expenses["amount"].sum() or 0.0)

    by_cat = (
        expenses
        .group_by("category")
        .agg(pl.col("amount").sum().alias("total"))
        .sort("total", descending=True)
    )

    if by_cat.is_empty() or total_exp == 0.0:
        return by_cat.with_columns(pl.lit(0.0).alias("pct"))

    return by_cat.with_columns(
        (pl.col("total") / total_exp * 100.0).round(1).alias("pct")
    )


def pivot_by_category_month(
    df: pl.DataFrame,
    direction: Literal["income", "expense"],
) -> pl.DataFrame:
    """Tableau croisé catégories × mois pour la vue globale.

    Colonnes : category, <mois chronologiques...>, Total.
    Les mois sont libellés "Mmm AA" (ex. "Jan 25").
    Retourne un DataFrame vide si aucune transaction ne correspond.
    """
    if direction == "income":
        filtered = df.filter(pl.col("amount") > 0)
    else:
        filtered = df.filter(pl.col("amount") < 0).with_columns(
            pl.col("amount").abs()
        )

    if filtered.is_empty():
        return pl.DataFrame()

    with_keys = filtered.with_columns(
        pl.col("category").fill_null("non classé"),
        pl.col("date").dt.year().alias("year"),
        pl.col("date").dt.month().alias("month_num"),
        pl.col("date").dt.truncate("1mo").alias("month_date"),
    ).with_columns(
        pl.struct(["year", "month_num"]).map_elements(
            lambda s: _month_label(s["month_num"], s["year"]),
            return_dtype=pl.Utf8,
        ).alias("month_label")
    )

    month_order: list[str] = (
        with_keys
        .select(["month_date", "month_label"])
        .unique()
        .sort("month_date")
        ["month_label"]
        .to_list()
    )

    grouped = (
        with_keys
        .group_by(["category", "month_label"])
        .agg(pl.col("amount").sum().round(2).alias("total"))
    )

    pivoted = (
        grouped
        .pivot(values="total", index="category", on="month_label", aggregate_function="sum")
        .fill_null(0.0)
    )

    ordered_cols = ["category"] + [m for m in month_order if m in pivoted.columns]
    pivoted = pivoted.select(ordered_cols)

    month_cols = [c for c in pivoted.columns if c != "category"]
    return (
        pivoted
        .with_columns(pl.sum_horizontal(month_cols).round(2).alias("Total"))
        .sort("Total", descending=True)
    )


def aggregate_monthly_from_df(df: pl.DataFrame) -> pl.DataFrame:
    """Agrège par mois sans filtre sur l'année — adapté aux périodes multi-années.

    Retourne : year, month_num, month_label, revenue, expenses, net.
    Trié chronologiquement.
    """
    monthly = (
        df.lazy()
        .with_columns(
            pl.col("date").dt.year().alias("year"),
            pl.col("date").dt.month().alias("month_num"),
        )
        .group_by(["year", "month_num"])
        .agg(
            pl.col("amount").filter(pl.col("amount") > 0).sum().fill_null(0.0).alias("revenue"),
            pl.col("amount").filter(pl.col("amount") < 0).sum().abs().fill_null(0.0).alias("expenses"),
        )
        .with_columns((pl.col("revenue") - pl.col("expenses")).alias("net"))
        .sort(["year", "month_num"])
        .collect()
    )

    return monthly.with_columns(
        pl.struct(["year", "month_num"]).map_elements(
            lambda s: _month_label(s["month_num"], s["year"]),
            return_dtype=pl.Utf8,
        ).alias("month_label")
    )
