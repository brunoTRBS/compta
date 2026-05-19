"""Lecture haute performance de la base via connectorx → Polars.

Utiliser ce module pour toutes les requêtes analytiques (agrégations, jointures,
filtres complexes). Les données sont mises en cache par Streamlit.

Les ÉCRITURES restent dans supabase.py.
"""

from typing import Literal

import polars as pl
import streamlit as st

from src.services.supabase import get_db_url

# TTL du cache Streamlit pour les requêtes (5 minutes)
_CACHE_TTL = 300


@st.cache_data(ttl=_CACHE_TTL)
def read_transactions(
    business_id: str | None = None,
    year: int | None = None,
    month: int | None = None,
) -> pl.DataFrame:
    """Lit les transactions depuis PostgreSQL via connectorx.

    Retourne un DataFrame Polars typé. Les filtres sont appliqués au niveau SQL.
    """
    conditions: list[str] = []
    if business_id is not None:
        conditions.append(f"business_id = '{business_id}'")
    if year is not None:
        conditions.append(f"EXTRACT(YEAR FROM date) = {year}")
    if month is not None:
        conditions.append(f"EXTRACT(MONTH FROM date) = {month}")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT
            id,
            date,
            amount::float8      AS amount,
            label,
            source,
            business_id,
            category,
            is_income,
            external_id,
            created_at
        FROM transactions
        {where}
        ORDER BY date DESC
    """
    df = pl.read_database_uri(query=query, uri=get_db_url(), engine="connectorx")
    return _cast_transactions(df)


@st.cache_data(ttl=_CACHE_TTL)
def read_accounts(owner: str | None = None) -> pl.DataFrame:
    """Lit les comptes bancaires et d'épargne."""
    where = f"WHERE owner = '{owner}' AND is_active = true" if owner else "WHERE is_active = true"
    query = f"""
        SELECT id, name, institution, type, owner, currency, balance, last_synced_at
        FROM accounts
        {where}
        ORDER BY owner, name
    """
    return pl.read_database_uri(query=query, uri=get_db_url(), engine="connectorx")


@st.cache_data(ttl=_CACHE_TTL)
def read_account_balance_history(account_id: str) -> pl.DataFrame:
    """Lit l'historique des soldes d'un compte pour les courbes d'évolution."""
    query = f"""
        SELECT date, balance::float8 AS balance
        FROM account_balance_history
        WHERE account_id = '{account_id}'
        ORDER BY date
    """
    return pl.read_database_uri(query=query, uri=get_db_url(), engine="connectorx")


@st.cache_data(ttl=_CACHE_TTL)
def read_monthly_revenue(
    business_id: str,
    year: int,
) -> pl.DataFrame:
    """Retourne le CA mensuel agrégé pour une activité et une année."""
    query = f"""
        SELECT
            EXTRACT(MONTH FROM date)::int AS month,
            SUM(amount)::float8           AS revenue
        FROM transactions
        WHERE business_id = '{business_id}'
          AND EXTRACT(YEAR FROM date) = {year}
          AND amount > 0
        GROUP BY month
        ORDER BY month
    """
    return pl.read_database_uri(query=query, uri=get_db_url(), engine="connectorx")


@st.cache_data(ttl=_CACHE_TTL)
def read_category_breakdown(
    business_id: str,
    year: int,
    month: int | None = None,
    direction: Literal["income", "expense", "all"] = "all",
) -> pl.DataFrame:
    """Retourne la répartition des montants par catégorie."""
    conditions = [
        f"business_id = '{business_id}'",
        f"EXTRACT(YEAR FROM date) = {year}",
    ]
    if month is not None:
        conditions.append(f"EXTRACT(MONTH FROM date) = {month}")
    if direction == "income":
        conditions.append("amount > 0")
    elif direction == "expense":
        conditions.append("amount < 0")

    where = "WHERE " + " AND ".join(conditions)
    query = f"""
        SELECT
            COALESCE(category, 'non classé') AS category,
            SUM(amount)::float8              AS total,
            COUNT(*)::int                    AS count
        FROM transactions
        {where}
        GROUP BY category
        ORDER BY ABS(SUM(amount)) DESC
    """
    return pl.read_database_uri(query=query, uri=get_db_url(), engine="connectorx")


@st.cache_data(ttl=_CACHE_TTL)
def read_patrimoine_evolution(
    owner: str | None = None,
    year: int | None = None,
) -> pl.DataFrame:
    """Lit l'évolution du patrimoine agrégé depuis account_balance_history.

    Joint avec accounts pour filtrer par owner.
    Retourne : date (Date), total_balance (Float64).
    """
    conditions: list[str] = []
    if owner is not None:
        conditions.append(f"a.owner = '{owner}'")
    if year is not None:
        conditions.append(f"EXTRACT(YEAR FROM h.date) = {year}")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT h.date, SUM(h.balance)::float8 AS total_balance
        FROM account_balance_history h
        JOIN accounts a ON h.account_id = a.id
        {where}
        GROUP BY h.date
        ORDER BY h.date
    """
    return pl.read_database_uri(query=query, uri=get_db_url(), engine="connectorx")


@st.cache_data(ttl=_CACHE_TTL)
def read_categories(business_id: str | None = None) -> pl.DataFrame:
    """Lit les catégories depuis PostgreSQL (résultat mis en cache 5 min)."""
    where = f"WHERE business_id = '{business_id}'" if business_id else ""
    query = f"""
        SELECT id, business_id, name, direction
        FROM categories
        {where}
        ORDER BY direction, name
    """
    return pl.read_database_uri(query=query, uri=get_db_url(), engine="connectorx")


def invalidate_cache() -> None:
    """Vide le cache Streamlit pour forcer un rechargement depuis la DB."""
    st.cache_data.clear()


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _cast_transactions(df: pl.DataFrame) -> pl.DataFrame:
    """Applique les types Polars corrects sur un DataFrame de transactions brut."""
    return df.with_columns(
        pl.col("date").cast(pl.Date),
        pl.col("amount").cast(pl.Float64),
        pl.col("is_income").cast(pl.Boolean),
        pl.col("created_at").cast(pl.Datetime("us", "UTC")),
    )
