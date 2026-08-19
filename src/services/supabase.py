"""Client Supabase et opérations CRUD.

Règle d'usage :
- Ce module gère les ÉCRITURES et les opérations nécessitant RLS (auth).
- Pour les lectures analytiques vers Polars, utiliser db_reader.py (REST API).
"""

import uuid
from typing import Any

import streamlit as st

from supabase import Client, ClientOptions, create_client

# Le timeout par défaut de supabase-py (120s) fait qu'un simple hoquet réseau
# bloque l'écriture en silence pendant 2 minutes — largement au-delà du délai
# où la connexion websocket de Streamlit Cloud se coupe d'elle-même, ce qui
# réinitialise la session et fait disparaître la saisie en cours sans message
# clair. Un timeout court fait échouer l'appel vite, avec une erreur visible.
_WRITE_TIMEOUT_SECONDS = 15


@st.cache_resource
def get_supabase() -> Client:
    """Retourne un client Supabase partagé (singleton par session Streamlit).

    En DEV_MODE, utilise la service role key pour bypasser les RLS locales.
    """
    url: str = st.secrets["SUPABASE_URL"]
    dev_mode = str(st.secrets.get("DEV_MODE", "false")).lower() == "true"
    key: str = st.secrets["SUPABASE_SERVICE_KEY"] if dev_mode else st.secrets["SUPABASE_KEY"]
    options = ClientOptions(postgrest_client_timeout=_WRITE_TIMEOUT_SECONDS)
    return create_client(url, key, options=options)


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


def insert_transfer(
    from_account_id: str,
    to_account_id: str,
    from_business_id: str,
    to_business_id: str,
    amount: float,
    date: str,
    label: str,
    notes: str | None = None,
) -> list[dict[str, Any]]:
    """Crée un virement entre 2 comptes : 2 écritures liées, jamais comptées comme du CA.

    Les deux lignes partagent un transfer_group_id et sont marquées is_transfer=true,
    ce qui les exclut par défaut des calculs de CA/dépenses/URSSAF (voir db_reader.read_transactions).
    """
    transfer_group_id = str(uuid.uuid4())
    signed_amount = abs(float(amount))
    rows = [
        {
            "date": date,
            "amount": -signed_amount,
            "label": label,
            "source": "manual",
            "business_id": from_business_id,
            "account_id": from_account_id,
            "is_transfer": True,
            "transfer_group_id": transfer_group_id,
            "notes": notes,
        },
        {
            "date": date,
            "amount": signed_amount,
            "label": label,
            "source": "manual",
            "business_id": to_business_id,
            "account_id": to_account_id,
            "is_transfer": True,
            "transfer_group_id": transfer_group_id,
            "notes": notes,
        },
    ]
    result = get_supabase().table("transactions").insert(rows).execute()
    return result.data


def delete_transfer(transfer_group_id: str) -> None:
    """Supprime les 2 écritures d'un virement (les 2 lignes partageant ce transfer_group_id)."""
    get_supabase().table("transactions").delete().eq("transfer_group_id", transfer_group_id).execute()


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


def delete_balance_snapshot(account_id: str, snapshot_id: str) -> None:
    """Supprime un point de l'historique des soldes d'un compte (erreur de saisie).

    Si le point supprimé était le plus récent, le solde courant du compte
    (accounts.balance) est ramené au point restant le plus récent (0 s'il n'en reste aucun).
    """
    client = get_supabase()
    client.table("account_balance_history").delete().eq("id", snapshot_id).execute()

    remaining = (
        client.table("account_balance_history")
        .select("balance")
        .eq("account_id", account_id)
        .order("date", desc=True)
        .limit(1)
        .execute()
        .data
    )
    new_balance = remaining[0]["balance"] if remaining else 0
    client.table("accounts").update({"balance": new_balance}).eq("id", account_id).execute()


def restore_balance_snapshot(account_id: str, date: str, balance: float) -> None:
    """Réinsère un point d'historique supprimé par erreur (annulation immédiate).

    Recalcule ensuite accounts.balance à partir du point le plus récent restant,
    avec la même logique que delete_balance_snapshot — évite toute divergence entre
    les deux selon l'ordre des opérations.
    """
    client = get_supabase()
    snapshot = {"account_id": account_id, "date": date, "balance": balance}
    client.table("account_balance_history").upsert(snapshot, on_conflict="account_id,date").execute()

    remaining = (
        client.table("account_balance_history")
        .select("balance")
        .eq("account_id", account_id)
        .order("date", desc=True)
        .limit(1)
        .execute()
        .data
    )
    new_balance = remaining[0]["balance"] if remaining else 0
    client.table("accounts").update({"balance": new_balance}).eq("id", account_id).execute()


# ---------------------------------------------------------------------------
# Transactions récurrentes
# ---------------------------------------------------------------------------

def insert_recurring_transaction(payload: dict[str, Any]) -> dict[str, Any]:
    """Crée un modèle de transaction récurrente."""
    result = get_supabase().table("recurring_transactions").insert(payload).execute()
    return result.data[0]


def update_recurring_transaction(recurring_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Met à jour des champs arbitraires d'un modèle récurrent (ex : is_active)."""
    result = (
        get_supabase()
        .table("recurring_transactions")
        .update(updates)
        .eq("id", recurring_id)
        .execute()
    )
    return result.data[0]


def delete_recurring_transaction(recurring_id: str) -> None:
    """Supprime définitivement un modèle de transaction récurrente."""
    get_supabase().table("recurring_transactions").delete().eq("id", recurring_id).execute()


def materialize_recurring_transactions(
    materializations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Crée les transactions réelles pour une liste de modèles validés et marque
    chaque modèle comme matérialisé pour ce mois.

    Args:
        materializations: liste de {recurring_id, transaction, year, month} où
            `transaction` est le payload prêt pour la table transactions.

    Returns:
        Les transactions créées.
    """
    client = get_supabase()
    created: list[dict[str, Any]] = []
    for item in materializations:
        result = client.table("transactions").insert(item["transaction"]).execute()
        created.append(result.data[0])
        client.table("recurring_transactions").update({
            "last_materialized_year": item["year"],
            "last_materialized_month": item["month"],
        }).eq("id", item["recurring_id"]).execute()
    return created


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
