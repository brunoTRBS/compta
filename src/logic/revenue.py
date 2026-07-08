"""Agrégations de revenus et calcul de la marge nette via Polars."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

import polars as pl

from src.config import (
    BusinessId,
    CA_THRESHOLDS,
    TVA_FRANCHISE_THRESHOLDS,
    URSSAF_RATES,
    URSSAF_RATES_BY_CATEGORY,
    VERSEMENT_LIBERATOIRE_RATES,
)

_MONTH_LABELS: dict[int, str] = {
    1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Aoû", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Déc",
}


def _month_label(month_num: int, year: int) -> str:
    return f"{_MONTH_LABELS[month_num]} {str(year)[2:]}"


def _compute_cotisations_by_category(
    df: pl.DataFrame,
    business_id: BusinessId,
    stripe_fees: float = 0.0,
) -> float:
    """Calcule les cotisations URSSAF en appliquant le taux propre à chaque catégorie.

    Pour PHI_RISING, les frais Stripe sont déduits du CA BNC avant application du taux.
    Les catégories sans taux explicite utilisent URSSAF_RATES[business_id] comme fallback.
    """
    rates = URSSAF_RATES_BY_CATEGORY.get(business_id, {})
    default_rate = float(URSSAF_RATES[business_id])

    income = df.filter(pl.col("amount") > 0).with_columns(
        pl.col("category").fill_null("non classé")
    )

    if income.is_empty():
        return 0.0

    by_cat = (
        income
        .group_by("category")
        .agg(pl.col("amount").sum().alias("ca"))
    )

    if rates:
        rate_df = pl.DataFrame({
            "category": list(rates.keys()),
            "rate": [float(r) for r in rates.values()],
        })
        by_cat = by_cat.join(rate_df, on="category", how="left")
    else:
        by_cat = by_cat.with_columns(pl.lit(None).cast(pl.Float64).alias("rate"))

    by_cat = by_cat.with_columns(pl.col("rate").fill_null(default_rate))

    if business_id == BusinessId.PHI_RISING and stripe_fees > 0:
        by_cat = by_cat.with_columns(
            pl.when((pl.col("category") == "BNC") & (pl.col("ca") > stripe_fees))
            .then(pl.col("ca") - stripe_fees)
            .when(pl.col("category") == "BNC")
            .then(pl.lit(0.0))
            .otherwise(pl.col("ca"))
            .alias("ca")
        )

    total = float((by_cat["ca"] * by_cat["rate"]).sum() or 0.0)
    return round(total, 2)


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
        total_charges, net_margin, ca_threshold, is_above_threshold,
        tva_threshold, is_above_tva_threshold.
    """
    yearly = df.filter(pl.col("date").dt.year() == year)

    ca = float(yearly.filter(pl.col("amount") > 0)["amount"].sum() or 0.0)
    expenses = abs(float(yearly.filter(pl.col("amount") < 0)["amount"].sum() or 0.0))

    stripe_fees_series = yearly.filter(
        (pl.col("amount") < 0) & (pl.col("category") == "Stripe")
    )["amount"]
    stripe_fees = abs(float(stripe_fees_series.sum() or 0.0))
    ca_for_urssaf = max(0.0, ca - stripe_fees)

    cotisations = _compute_cotisations_by_category(yearly, business_id, stripe_fees)

    vl_rate = VERSEMENT_LIBERATOIRE_RATES[business_id] if with_versement_liberatoire else Decimal("0")
    versement_liberatoire = float(
        (Decimal(str(round(ca_for_urssaf, 2))) * vl_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
    total_charges = round(cotisations + versement_liberatoire, 2)
    threshold = float(CA_THRESHOLDS[business_id])
    tva_threshold = float(TVA_FRANCHISE_THRESHOLDS[business_id])

    return {
        "ca": ca,
        "stripe_fees": stripe_fees,
        "ca_for_urssaf": ca_for_urssaf,
        "expenses": expenses,
        "cotisations": cotisations,
        "versement_liberatoire": versement_liberatoire,
        "total_charges": total_charges,
        "net_margin": ca - expenses - total_charges,
        "ca_threshold": threshold,
        "is_above_threshold": ca > threshold,
        "tva_threshold": tva_threshold,
        "is_above_tva_threshold": ca > tva_threshold,
    }


def monthly_benefice(df: pl.DataFrame, business_id: BusinessId) -> pl.DataFrame:
    """Bénéfice net (CA - dépenses - cotisations URSSAF) mois par mois, sur tout l'historique de df.

    Contrairement à compute_ytd_summary (agrégat annuel), isole chaque mois présent dans df
    et lui applique la même formule de bénéfice net que la Vue mensuelle de chaque activité.

    Returns:
        DataFrame : year (Int32), month_num (Int32), benefice (Float64). Vide si df est vide.
    """
    schema = {"year": pl.Int32, "month_num": pl.Int32, "benefice": pl.Float64}
    if df.is_empty():
        return pl.DataFrame(schema=schema)

    periods = (
        df.select(
            pl.col("date").dt.year().alias("year"),
            pl.col("date").dt.month().alias("month_num"),
        )
        .unique()
        .sort(["year", "month_num"])
    )

    rows = []
    for year, month_num in periods.iter_rows():
        month_df = df.filter(
            (pl.col("date").dt.year() == year) & (pl.col("date").dt.month() == month_num)
        )
        summary = compute_ytd_summary(month_df, business_id, year)
        rows.append({"year": year, "month_num": month_num, "benefice": summary["net_margin"]})

    return pl.DataFrame(rows, schema=schema)


def compute_net_margin(ca: float, expenses: float, total_charges: float) -> float:
    """Calcule la marge nette : CA - charges - cotisations."""
    return ca - expenses - total_charges


def aggregate_revenue_by_category(
    df: pl.DataFrame,
    business_id: BusinessId,
) -> pl.DataFrame:
    """Revenus par catégorie : ca_brut, urssaf (taux propre à chaque catégorie), ca_net, pct_ca.

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

    rates = URSSAF_RATES_BY_CATEGORY.get(business_id, {})
    default_rate = float(URSSAF_RATES[business_id])

    if rates:
        rate_df = pl.DataFrame({
            "category": list(rates.keys()),
            "rate": [float(r) for r in rates.values()],
        })
        by_cat = by_cat.join(rate_df, on="category", how="left")
    else:
        by_cat = by_cat.with_columns(pl.lit(None).cast(pl.Float64).alias("rate"))

    by_cat = by_cat.with_columns(pl.col("rate").fill_null(default_rate))

    return by_cat.with_columns(
        (pl.col("ca_brut") * pl.col("rate")).round(2).alias("urssaf"),
        (pl.col("ca_brut") * (1.0 - pl.col("rate"))).round(2).alias("ca_net"),
        (pl.col("ca_brut") / total_ca * 100.0).round(1).alias("pct_ca"),
    ).drop("rate")


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
