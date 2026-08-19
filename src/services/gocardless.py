"""Client GoCardless Bank Account Data (anciennement Nordigen).

Documentation API : https://bankaccountdata.gocardless.com/api/v2/
"""

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import requests
import streamlit as st

_BASE_URL = "https://bankaccountdata.gocardless.com/api/v2"
_SESSION_KEY = "_gc_token"

# Fallback pour les contextes hors Streamlit (tests, scripts)
_token_cache: dict[str, Any] = {}


def _get_credentials() -> tuple[str, str]:
    try:
        return st.secrets["GOCARDLESS_SECRET_ID"], st.secrets["GOCARDLESS_SECRET_KEY"]
    except Exception:
        return os.environ["GOCARDLESS_SECRET_ID"], os.environ["GOCARDLESS_SECRET_KEY"]


def _get_cache() -> dict[str, Any]:
    """Retourne le cache de token (session_state en contexte Streamlit, dict sinon)."""
    try:
        return st.session_state  # type: ignore[return-value]
    except Exception:
        return _token_cache


def get_access_token() -> str:
    """Obtient ou renouvelle le token d'accès GoCardless.

    Le token est mis en cache (session_state ou module-level) pour éviter les appels
    répétés. Durée de vie : 24 h moins 1 min de marge.
    """
    cache = _get_cache()
    cached = cache.get(_SESSION_KEY)
    if cached and cached["expires_at"] > datetime.now(tz=UTC):
        return cached["access"]

    secret_id, secret_key = _get_credentials()
    resp = requests.post(
        f"{_BASE_URL}/token/new/",
        json={"secret_id": secret_id, "secret_key": secret_key},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    expires_in = int(data.get("access_expires", 86400))
    cache[_SESSION_KEY] = {
        "access": data["access"],
        "expires_at": datetime.now(tz=UTC) + timedelta(seconds=expires_in - 60),
    }
    return data["access"]


def list_accounts(requisition_id: str) -> list[str]:
    """Retourne les account IDs liés à une réquisition GoCardless."""
    token = get_access_token()
    resp = requests.get(
        f"{_BASE_URL}/requisitions/{requisition_id}/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("accounts", [])


def fetch_transactions(
    account_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Récupère les transactions confirmées (booked) d'un compte GoCardless.

    Args:
        account_id: UUID du compte GoCardless.
        date_from: Date début ISO YYYY-MM-DD (optionnel).
        date_to: Date fin ISO YYYY-MM-DD (optionnel).

    Returns:
        Liste de transactions brutes GoCardless (booked uniquement).
    """
    token = get_access_token()
    params: dict[str, str] = {}
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to

    resp = requests.get(
        f"{_BASE_URL}/accounts/{account_id}/transactions/",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("transactions", {}).get("booked", [])


def map_transaction(raw: dict[str, Any], business_id: str) -> dict[str, Any]:
    """Mappe une transaction GoCardless brute vers le schéma `transactions`.

    Règles de mapping :
    - date       : bookingDate > valueDate
    - amount     : transactionAmount.amount (négatif = débit)
    - label      : remittanceInformationUnstructured > creditorName > debtorName
    - external_id: transactionId > internalTransactionId
    """
    tx_amount = raw.get("transactionAmount", {})
    amount = float(tx_amount.get("amount", "0"))

    label = (
        raw.get("remittanceInformationUnstructured")
        or raw.get("creditorName")
        or raw.get("debtorName")
        or "Transaction bancaire"
    )

    return {
        "date": raw.get("bookingDate") or raw.get("valueDate"),
        "amount": amount,
        "label": label.strip(),
        "source": "bank",
        "business_id": business_id,
        "category": None,
        "external_id": raw.get("transactionId") or raw.get("internalTransactionId"),
    }
