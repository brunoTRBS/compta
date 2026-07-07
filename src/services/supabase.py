"""Client Supabase et opérations CRUD.

Règle d'usage :
- Ce module gère les ÉCRITURES et les opérations nécessitant RLS (auth).
- Pour les lectures analytiques vers Polars, utiliser db_reader.py (REST API).
"""

from typing import Any

import streamlit as st
from supabase import Client, create_client


@st.cache_resource
def get_supabase() -> Client:
    """Retourne un client Supabase partagé (singleton par session Streamlit)."""
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def get_db_url() -> str:
    """Retourne l'URL PostgreSQL directe pour connectorx / adbc."""
    return str(st.secrets["DB_URL"])


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

def fetch_transactions(
    business_id: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Récupère les transactions via supabase-py (adapté aux petits volumes)."""
    client = get_supabase()
    query = client.table("transactions").select("*").order("date", desc=True).limit(limit)
    if business_id is not None:
        query = query.eq("business_id", business_id)
    return query.execute().data


def insert_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    """Insère une transaction et retourne la ligne créée."""
    result = get_supabase().table("transactions").insert(transaction).execute()
    return result.data[0]


def bulk_upsert_transactions(transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Insère ou met à jour un batch de transactions (sur external_id)."""
    result = (
        get_supabase()
        .table("transactions")
        .upsert(transactions, on_conflict="external_id")
        .execute()
    )
    return result.data


def update_transaction_category(transaction_id: str, category: str) -> dict[str, Any]:
    """Met à jour la catégorie d'une transaction."""
    result = (
        get_supabase()
        .table("transactions")
        .update({"category": category})
        .eq("id", transaction_id)
        .execute()
    )
    return result.data[0]


def upsert_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    """Insère ou met à jour une transaction (sur id si présent, sinon insert)."""
    if transaction.get("id"):
        result = (
            get_supabase()
            .table("transactions")
            .upsert(transaction, on_conflict="id")
            .execute()
        )
    else:
        result = get_supabase().table("transactions").insert(transaction).execute()
    return result.data[0]


def update_transaction(transaction_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Met à jour des champs arbitraires d'une transaction.

    Args:
        transaction_id: UUID de la transaction.
        updates: Dict des champs à mettre à jour (ex : {"label": "...", "amount": -50}).
    """
    _IMMUTABLE = {"id", "created_at", "source", "external_id"}
    safe_updates = {k: v for k, v in updates.items() if k not in _IMMUTABLE}
    result = (
        get_supabase()
        .table("transactions")
        .update(safe_updates)
        .eq("id", transaction_id)
        .execute()
    )
    return result.data[0]


def delete_transaction(transaction_id: str) -> None:
    """Supprime définitivement une transaction par son id."""
    get_supabase().table("transactions").delete().eq("id", transaction_id).execute()


def bulk_update_categories(updates: list[dict[str, str]]) -> None:
    """Met à jour les catégories en batch. `updates` = liste de {id, category}."""
    client = get_supabase()
    for item in updates:
        client.table("transactions").update({"category": item["category"]}).eq("id", item["id"]).execute()


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def fetch_accounts(owner: str | None = None) -> list[dict[str, Any]]:
    """Récupère les comptes actifs."""
    client = get_supabase()
    query = client.table("accounts").select("*").eq("is_active", True).order("name")
    if owner is not None:
        query = query.eq("owner", owner)
    return query.execute().data


def update_account_balance(account_id: str, balance: float) -> dict[str, Any]:
    """Met à jour le solde d'un compte et enregistre un snapshot historique."""
    from datetime import date

    client = get_supabase()
    client.table("accounts").update({"balance": balance, "last_synced_at": "now()"}).eq(
        "id", account_id
    ).execute()
    snapshot = {"account_id": account_id, "date": date.today().isoformat(), "balance": balance}
    client.table("account_balance_history").upsert(snapshot, on_conflict="account_id,date").execute()
    return {"account_id": account_id, "balance": balance}


# ---------------------------------------------------------------------------
# Categorization rules
# ---------------------------------------------------------------------------

def fetch_categorization_rules() -> list[dict[str, Any]]:
    """Récupère les règles de catégorisation actives, triées par priorité."""
    return (
        get_supabase()
        .table("categorization_rules")
        .select("*")
        .eq("is_active", True)
        .order("priority", desc=True)
        .execute()
        .data
    )


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def fetch_categories(
    business_id: str | None = None,
    direction: str | None = None,
) -> list[dict[str, Any]]:
    """Récupère les catégories (sans cache — toujours à jour)."""
    client = get_supabase()
    query = client.table("categories").select("*").order("name")
    if business_id is not None:
        query = query.eq("business_id", business_id)
    if direction is not None:
        query = query.eq("direction", direction)
    return query.execute().data


def insert_category(business_id: str, name: str, direction: str) -> dict[str, Any]:
    """Crée une nouvelle catégorie."""
    result = (
        get_supabase()
        .table("categories")
        .insert({"business_id": business_id, "name": name, "direction": direction})
        .execute()
    )
    return result.data[0]


def delete_category(category_id: str) -> None:
    """Supprime une catégorie par son id."""
    get_supabase().table("categories").delete().eq("id", category_id).execute()
