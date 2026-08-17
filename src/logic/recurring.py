"""Logique des transactions récurrentes : modèles dus, date de matérialisation."""

import calendar
from datetime import date

import polars as pl


def due_templates(templates_df: pl.DataFrame, year: int, month: int) -> pl.DataFrame:
    """Modèles actifs pas encore validés pour (year, month).

    Args:
        templates_df: recurring_transactions (colonnes is_active,
            last_materialized_year, last_materialized_month attendues).
        year: année du mois pour lequel on cherche les modèles à proposer.
        month: mois (1-12).

    Returns:
        Sous-ensemble de templates_df : actifs, et dont le dernier mois validé
        n'est pas (year, month). Vide si templates_df est vide.
    """
    if templates_df.is_empty():
        return templates_df

    # fill_null(False) : un modèle jamais matérialisé (colonnes null) doit être dû,
    # pas silencieusement exclu par la propagation de null de Polars.
    already_materialized = (
        (pl.col("last_materialized_year") == year)
        & (pl.col("last_materialized_month") == month)
    ).fill_null(False)

    return templates_df.filter(pl.col("is_active") & ~already_materialized)


def default_materialize_date(day_of_month: int, year: int, month: int) -> date:
    """Jour du mois voulu, ramené au dernier jour du mois s'il n'existe pas.

    Ex : day_of_month=31 pour un mois de 30 jours → le 30.
    """
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day_of_month, last_day))
