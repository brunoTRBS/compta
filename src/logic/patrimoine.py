"""Logique de bilan patrimonial : agrégation et évolution des actifs."""

import polars as pl


def aggregate_by_account_type(accounts_df: pl.DataFrame) -> pl.DataFrame:
    """Agrège les soldes par type de compte.

    Returns:
        DataFrame : type, total_balance (Float64), account_count (Int32).
    """
    if accounts_df.is_empty():
        return pl.DataFrame(
            {"type": [], "total_balance": [], "account_count": []},
            schema={"type": pl.Utf8, "total_balance": pl.Float64, "account_count": pl.Int32},
        )

    return (
        accounts_df.lazy()
        .group_by("type")
        .agg(
            pl.col("balance").sum().alias("total_balance"),
            pl.len().cast(pl.Int32).alias("account_count"),
        )
        .sort("total_balance", descending=True)
        .collect()
    )


def compute_net_worth(accounts_df: pl.DataFrame) -> float:
    """Calcule le patrimoine net total (somme de tous les soldes actifs)."""
    if accounts_df.is_empty():
        return 0.0
    return float(accounts_df["balance"].sum() or 0.0)


def compute_patrimoine_evolution(history_df: pl.DataFrame) -> pl.DataFrame:
    """Agrège l'évolution du patrimoine total par date.

    Args:
        history_df: DataFrame avec colonnes date, balance (et optionnellement account_id).
                    Chaque ligne = solde d'un compte à une date donnée.

    Returns:
        DataFrame : date (Date), total_balance (Float64), trié chronologiquement.
    """
    if history_df.is_empty():
        return pl.DataFrame(
            {"date": [], "total_balance": []},
            schema={"date": pl.Date, "total_balance": pl.Float64},
        )

    return (
        history_df.lazy()
        .group_by("date")
        .agg(pl.col("balance").sum().alias("total_balance"))
        .sort("date")
        .collect()
    )


def group_by_owner(accounts_df: pl.DataFrame) -> dict[str, float]:
    """Retourne le patrimoine total par owner (personal, phi_rising, booth_in_lyon).

    Utile pour ventiler entre actifs perso et actifs pro.
    """
    if accounts_df.is_empty():
        return {}

    result = (
        accounts_df.lazy()
        .group_by("owner")
        .agg(pl.col("balance").sum().alias("total"))
        .collect()
    )
    return {row["owner"]: float(row["total"]) for row in result.iter_rows(named=True)}
