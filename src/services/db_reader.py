"""Lecture des données depuis Supabase via REST API → Polars.

Remplace l'ancienne approche ADBC/connectorx (connexion TCP directe bloquée sur
Streamlit Cloud). Utilise la REST API HTTPS de Supabase, puis convertit en Polars.

Les ÉCRITURES restent dans supabase.py.
"""

from calendar import monthrange
from datetime import date as Date
from typing import Literal

import polars as pl
import streamlit as st

from src.services.supabase import get_supabase

_CACHE_TTL = 300

_TXN_COLS = (
    "id,date,amount,label,source,business_id,category,is_income,external_id,created_at,"
    "account_id,is_transfer,transfer_group_id"
)
_TXN_LIMIT = 50_000

_TXN_SCHEMA: dict[str, type[pl.DataType]] = {
    "id": pl.Utf8,
    "date": pl.Date,
    "amount": pl.Float64,
    "label": pl.Utf8,
    "source": pl.Utf8,
    "business_id": pl.Utf8,
    "category": pl.Utf8,
    "is_income": pl.Boolean,
    "external_id": pl.Utf8,
    "created_at": pl.Datetime("us", "UTC"),
    "account_id": pl.Utf8,
    "is_transfer": pl.Boolean,
    "transfer_group_id": pl.Utf8,
}


@st.cache_data(ttl=_CACHE_TTL)
def read_transactions(
    business_id: str | None = None,
    year: int | None = None,
    month: int | None = None,
    date_from: Date | None = None,
    date_to: Date | None = None,
    include_transfers: bool = False,
) -> pl.DataFrame:
    """Lit les transactions via Supabase REST. Retourne un DataFrame Polars typé.

    Par défaut, exclut les virements internes (is_transfer=true) : ils ne
    représentent jamais du CA, une dépense ou une base URSSAF, seulement un
    déplacement d'argent entre deux comptes. Passer include_transfers=True
    pour les vues qui suivent l'argent compte par compte (ex : Vue consolidée).
    """
    q = get_supabase().table("transactions").select(_TXN_COLS)

    if business_id is not None:
        q = q.eq("business_id", business_id)

    if not include_transfers:
        q = q.eq("is_transfer", False)

    if date_from is not None:
        q = q.gte("date", date_from.isoformat())
    if date_to is not None:
        q = q.lte("date", date_to.isoformat())

    if date_from is None and date_to is None:
        if year is not None and month is not None:
            last_day = monthrange(year, month)[1]
            q = q.gte("date", f"{year}-{month:02d}-01").lte("date", f"{year}-{month:02d}-{last_day:02d}")
        elif year is not None:
            q = q.gte("date", f"{year}-01-01").lte("date", f"{year}-12-31")

    data = q.order("date", desc=True).limit(_TXN_LIMIT).execute().data
    if not data:
        return pl.DataFrame(schema=_TXN_SCHEMA)
    return _cast_transactions(pl.DataFrame(data))


@st.cache_data(ttl=_CACHE_TTL)
def read_accounts(owner: str | None = None) -> pl.DataFrame:
    """Lit les comptes bancaires et d'épargne."""
    q = (
        get_supabase()
        .table("accounts")
        .select("id,name,institution,type,owner,currency,balance,last_synced_at")
        .eq("is_active", True)
    )
    if owner is not None:
        q = q.eq("owner", owner)
    data = q.order("name").execute().data
    if not data:
        return pl.DataFrame()
    return pl.DataFrame(data)


@st.cache_data(ttl=_CACHE_TTL)
def read_account_balance_history(account_id: str) -> pl.DataFrame:
    """Lit l'historique des soldes d'un compte pour les courbes d'évolution."""
    data = (
        get_supabase()
        .table("account_balance_history")
        .select("date,balance")
        .eq("account_id", account_id)
        .order("date")
        .execute()
        .data
    )
    if not data:
        return pl.DataFrame(schema={"date": pl.Date, "balance": pl.Float64})
    return pl.DataFrame(data).with_columns(
        pl.col("date").cast(pl.Date),
        pl.col("balance").cast(pl.Float64),
    )


@st.cache_data(ttl=_CACHE_TTL)
def read_monthly_revenue(business_id: str, year: int) -> pl.DataFrame:
    """Retourne le CA mensuel agrégé pour une activité et une année."""
    data = (
        get_supabase()
        .table("transactions")
        .select("date,amount")
        .eq("business_id", business_id)
        .gte("date", f"{year}-01-01")
        .lte("date", f"{year}-12-31")
        .gt("amount", 0)
        .execute()
        .data
    )
    if not data:
        return pl.DataFrame(schema={"month": pl.Int32, "revenue": pl.Float64})
    return (
        pl.DataFrame(data)
        .with_columns(
            pl.col("date").cast(pl.Date),
            pl.col("amount").cast(pl.Float64),
        )
        .with_columns(pl.col("date").dt.month().alias("month"))
        .group_by("month")
        .agg(pl.col("amount").sum().alias("revenue"))
        .sort("month")
    )


@st.cache_data(ttl=_CACHE_TTL)
def read_category_breakdown(
    business_id: str,
    year: int,
    month: int | None = None,
    direction: Literal["income", "expense", "all"] = "all",
) -> pl.DataFrame:
    """Retourne la répartition des montants par catégorie."""
    q = (
        get_supabase()
        .table("transactions")
        .select("category,amount")
        .eq("business_id", business_id)
    )
    if month is not None:
        last_day = monthrange(year, month)[1]
        q = q.gte("date", f"{year}-{month:02d}-01").lte("date", f"{year}-{month:02d}-{last_day:02d}")
    else:
        q = q.gte("date", f"{year}-01-01").lte("date", f"{year}-12-31")
    if direction == "income":
        q = q.gt("amount", 0)
    elif direction == "expense":
        q = q.lt("amount", 0)

    data = q.execute().data
    if not data:
        return pl.DataFrame(schema={"category": pl.Utf8, "total": pl.Float64, "count": pl.Int32})
    return (
        pl.DataFrame(data)
        .with_columns(
            pl.col("category").fill_null("non classé"),
            pl.col("amount").cast(pl.Float64),
        )
        .group_by("category")
        .agg(
            pl.col("amount").sum().alias("total"),
            pl.len().alias("count"),
        )
        .sort(pl.col("total").abs(), descending=True)
    )


@st.cache_data(ttl=_CACHE_TTL)
def read_patrimoine_evolution(
    owner: str | None = None,
    year: int | None = None,
) -> pl.DataFrame:
    """Lit l'évolution du patrimoine agrégé depuis account_balance_history."""
    # Résoudre d'abord les account_ids pour l'owner donné
    acc_q = get_supabase().table("accounts").select("id").eq("is_active", True)
    if owner is not None:
        acc_q = acc_q.eq("owner", owner)
    acc_data = acc_q.execute().data
    if not acc_data:
        return pl.DataFrame(schema={"date": pl.Date, "total_balance": pl.Float64})

    account_ids = [a["id"] for a in acc_data]

    hist_q = (
        get_supabase()
        .table("account_balance_history")
        .select("date,balance")
        .in_("account_id", account_ids)
    )
    if year is not None:
        hist_q = hist_q.gte("date", f"{year}-01-01").lte("date", f"{year}-12-31")

    hist_data = hist_q.execute().data
    if not hist_data:
        return pl.DataFrame(schema={"date": pl.Date, "total_balance": pl.Float64})

    return (
        pl.DataFrame(hist_data)
        .with_columns(
            pl.col("date").cast(pl.Date),
            pl.col("balance").cast(pl.Float64),
        )
        .group_by("date")
        .agg(pl.col("balance").sum().alias("total_balance"))
        .sort("date")
    )


@st.cache_data(ttl=_CACHE_TTL)
def read_categories(business_id: str | None = None) -> pl.DataFrame:
    """Lit les catégories depuis Supabase (résultat mis en cache 5 min)."""
    q = get_supabase().table("categories").select("id,business_id,name,direction")
    if business_id is not None:
        q = q.eq("business_id", business_id)
    data = q.order("direction").order("name").execute().data
    if not data:
        return pl.DataFrame()
    return pl.DataFrame(data)


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
        pl.col("is_transfer").cast(pl.Boolean),
        pl.col("created_at").str.to_datetime(time_unit="us", time_zone="UTC"),
    )
