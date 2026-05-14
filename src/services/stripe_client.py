"""Client Stripe pour la récupération des paiements et remboursements pro."""

import os
from datetime import datetime
from typing import Any

import stripe
import streamlit as st


def _get_stripe_key() -> str:
    try:
        return str(st.secrets["STRIPE_SECRET_KEY"])
    except Exception:
        return os.environ["STRIPE_SECRET_KEY"]


def _configure() -> None:
    """Configure la clé API Stripe au niveau module."""
    stripe.api_key = _get_stripe_key()


def fetch_payment_intents(
    business_id: str,
    limit: int = 100,
    created_after: int | None = None,
) -> list[dict[str, Any]]:
    """Récupère les PaymentIntents filtrés par business_id (metadata).

    Stripe ne supporte pas le filtrage serveur par metadata dans list().
    Le filtrage est fait côté client après récupération.

    Args:
        business_id: Valeur de metadata["business_id"] sur Stripe.
        limit: Nombre max de PI à récupérer par page.
        created_after: Timestamp Unix, filtre les PI créés après cette date.

    Returns:
        Liste de PaymentIntents (dict) matchant le business_id.
    """
    _configure()
    params: dict[str, Any] = {"limit": limit}
    if created_after is not None:
        params["created"] = {"gte": created_after}

    result = []
    for pi in stripe.PaymentIntent.list(**params).auto_paging_iter():
        if pi.get("metadata", {}).get("business_id") == business_id:
            result.append(dict(pi))
    return result


def fetch_refunds(payment_intent_id: str) -> list[dict[str, Any]]:
    """Récupère les remboursements associés à un PaymentIntent."""
    _configure()
    refunds = stripe.Refund.list(payment_intent=payment_intent_id, limit=10)
    return [dict(r) for r in refunds.auto_paging_iter()]


def map_payment_intent(pi: dict[str, Any], business_id: str) -> dict[str, Any]:
    """Mappe un PaymentIntent Stripe vers le schéma `transactions`.

    Règles de mapping :
    - amount : converti de centimes en euros (positif = encaissement)
    - date   : depuis le timestamp Unix `created`
    - label  : description Stripe ou identifiant court
    - category : revenue si amount > 0, sinon refund_received
    """
    amount_eur = pi.get("amount", 0) / 100.0
    date_str = datetime.fromtimestamp(pi["created"]).strftime("%Y-%m-%d")
    label = pi.get("description") or f"Paiement Stripe {pi['id'][:12]}"

    return {
        "date": date_str,
        "amount": amount_eur,
        "label": label,
        "source": "stripe",
        "business_id": business_id,
        "category": "revenue" if amount_eur >= 0 else "refund_received",
        "external_id": pi["id"],
    }


def map_stripe_cache_row(pi: dict[str, Any], business_id: str) -> dict[str, Any]:
    """Mappe un PaymentIntent vers le schéma `stripe_transactions` (cache brut)."""
    return {
        "stripe_id": pi["id"],
        "business_id": business_id,
        "amount": pi.get("amount", 0) / 100.0,
        "currency": pi.get("currency", "eur"),
        "status": pi.get("status", "unknown"),
        "customer_email": pi.get("receipt_email"),
        "description": pi.get("description"),
        "metadata": pi.get("metadata", {}),
        "stripe_created_at": datetime.fromtimestamp(pi["created"]).isoformat(),
    }
