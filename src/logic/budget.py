"""Logique budgétaire pour le suivi des dépenses et de l'épargne personnelle."""

import polars as pl


def breakdown_by_category(
    df: pl.DataFrame,
    include_income: bool = False,
) -> pl.DataFrame:
    """Ventile les transactions par catégorie avec montant total et pourcentage.

    Args:
        df: DataFrame de transactions.
        include_income: Si False (défaut), filtre uniquement les dépenses (amount < 0).

    Returns:
        DataFrame : category, total (Float64), count (Int32), pct (Float64).
    """
    filtered = df if include_income else df.filter(pl.col("amount") < 0)
    if filtered.is_empty():
        return pl.DataFrame(
            {"category": [], "total": [], "count": [], "pct": []},
            schema={"category": pl.Utf8, "total": pl.Float64, "count": pl.Int32, "pct": pl.Float64},
        )

    breakdown = (
        filtered.lazy()
        .with_columns(pl.col("amount").abs().alias("amount_abs"))
        .group_by("category")
        .agg(
            pl.col("amount_abs").sum().alias("total"),
            pl.len().cast(pl.Int32).alias("count"),
        )
        .sort("total", descending=True)
        .collect()
    )

    total_sum = breakdown["total"].sum()
    if total_sum and total_sum > 0:
        return breakdown.with_columns(
            (pl.col("total") / total_sum * 100).round(1).alias("pct")
        )
    return breakdown.with_columns(pl.lit(0.0).alias("pct"))


def compute_savings_rate(income: float, expenses: float) -> float:
    """Calcule le taux d'épargne = (revenus - dépenses) / revenus × 100.

    Retourne 0.0 si les revenus sont nuls ou négatifs.
    """
    if income <= 0:
        return 0.0
    return round((income - expenses) / income * 100, 1)


def compute_budget_summary(
    df: pl.DataFrame,
    year: int,
    month: int | None = None,
) -> dict:
    """Calcule un résumé budgétaire pour une période.

    Returns:
        dict : income, expenses, savings, savings_rate, top_category (str | None).
    """
    period_df = df.filter(pl.col("date").dt.year() == year)
    if month is not None:
        period_df = period_df.filter(pl.col("date").dt.month() == month)

    income = float(period_df.filter(pl.col("amount") > 0)["amount"].sum() or 0.0)
    expenses = abs(float(period_df.filter(pl.col("amount") < 0)["amount"].sum() or 0.0))

    breakdown = breakdown_by_category(period_df)
    top_category: str | None = breakdown["category"][0] if not breakdown.is_empty() else None

    return {
        "income": income,
        "expenses": expenses,
        "savings": income - expenses,
        "savings_rate": compute_savings_rate(income, expenses),
        "top_category": top_category,
    }
