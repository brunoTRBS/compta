"""Vérifications de l'état des connexions aux services externes."""

import time
from typing import NamedTuple


class HealthStatus(NamedTuple):
    name: str
    ok: bool
    message: str
    latency_ms: float | None = None


def check_supabase() -> HealthStatus:
    """Teste la connexion Supabase avec une requête légère."""
    from src.services.supabase import get_supabase

    t0 = time.monotonic()
    try:
        get_supabase().table("transactions").select("id").limit(1).execute()
        ms = round((time.monotonic() - t0) * 1000, 1)
        return HealthStatus("Supabase", True, "Connecté", ms)
    except Exception as exc:
        return HealthStatus("Supabase", False, str(exc)[:120])


def check_stripe() -> HealthStatus:
    """Teste la connexion Stripe via Balance.retrieve()."""
    import os

    try:
        import streamlit as _st
        key = _st.secrets.get("STRIPE_SECRET_KEY", "")
    except Exception:
        key = os.environ.get("STRIPE_SECRET_KEY", "")

    if not key:
        return HealthStatus("Stripe", False, "Clé STRIPE_SECRET_KEY non configurée")

    t0 = time.monotonic()
    try:
        import stripe as _stripe

        _stripe.api_key = key
        _stripe.Balance.retrieve()
        ms = round((time.monotonic() - t0) * 1000, 1)
        return HealthStatus("Stripe", True, "Connecté", ms)
    except Exception as exc:
        return HealthStatus("Stripe", False, str(exc)[:120])


def check_gocardless() -> HealthStatus:
    """Teste GoCardless en récupérant un token d'accès."""
    from src.services.gocardless import get_access_token

    t0 = time.monotonic()
    try:
        get_access_token()
        ms = round((time.monotonic() - t0) * 1000, 1)
        return HealthStatus("GoCardless", True, "Token actif", ms)
    except Exception as exc:
        return HealthStatus("GoCardless", False, str(exc)[:120])


def run_all_checks() -> list[HealthStatus]:
    """Lance les trois vérifications et retourne la liste ordonnée."""
    return [check_supabase(), check_stripe(), check_gocardless()]
