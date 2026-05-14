"""Page Paramètres & Statut — diagnostic des connexions et gestion du cache."""

import streamlit as st

from src.services.db_reader import invalidate_cache
from src.utils.health import HealthStatus, run_all_checks

st.set_page_config(page_title="Paramètres", page_icon="⚙️", layout="wide")
st.title("Paramètres & Statut")

# ---------------------------------------------------------------------------
# Statut des connexions
# ---------------------------------------------------------------------------
st.subheader("Statut des connexions")

_STATUS_CACHE_KEY = "_settings_health"

col_check, _ = st.columns([1, 3])
with col_check:
    if st.button("🔄 Vérifier les connexions", use_container_width=True):
        with st.spinner("Tests en cours…"):
            st.session_state[_STATUS_CACHE_KEY] = run_all_checks()

statuses: list[HealthStatus] | None = st.session_state.get(_STATUS_CACHE_KEY)

if statuses:
    cols = st.columns(len(statuses))
    for status, col in zip(statuses, cols):
        with col:
            icon = "✅" if status.ok else "❌"
            st.metric(
                label=f"{icon} {status.name}",
                value="OK" if status.ok else "Erreur",
                delta=f"{status.latency_ms:.0f} ms" if status.latency_ms else None,
                delta_color="off",
            )
            if not status.ok:
                st.error(status.message, icon="⚠️")
            else:
                st.caption(status.message)
else:
    st.info("Cliquez sur **Vérifier les connexions** pour tester les services.")

st.divider()

# ---------------------------------------------------------------------------
# Gestion du cache
# ---------------------------------------------------------------------------
st.subheader("Cache de données")
st.caption(
    "Les requêtes base de données sont mises en cache 5 minutes (TTL). "
    "Videz le cache si les données affichées semblent obsolètes."
)

col_cache1, col_cache2 = st.columns([1, 3])
with col_cache1:
    if st.button("🗑️ Vider le cache", use_container_width=True):
        invalidate_cache()
        if _STATUS_CACHE_KEY in st.session_state:
            del st.session_state[_STATUS_CACHE_KEY]
        st.toast("Cache vidé — les prochaines requêtes iront directement en base.", icon="✅")

st.divider()

# ---------------------------------------------------------------------------
# Configuration requise
# ---------------------------------------------------------------------------
st.subheader("Variables d'environnement requises")
st.caption("À configurer dans `.streamlit/secrets.toml` (local) ou dans Streamlit Cloud > Settings > Secrets.")

st.code(
    """# .streamlit/secrets.toml
SUPABASE_URL  = "https://<project>.supabase.co"
SUPABASE_KEY  = "<anon-or-service-role-key>"
DB_URL        = "postgresql://postgres:<pwd>@db.<project>.supabase.co:5432/postgres"

STRIPE_SECRET_KEY     = "sk_live_..."
STRIPE_WEBHOOK_SECRET = "whsec_..."

GOCARDLESS_SECRET_ID  = "<id>"
GOCARDLESS_SECRET_KEY = "<key>"
GOCARDLESS_ENV        = "live"
""",
    language="toml",
)

st.divider()

# ---------------------------------------------------------------------------
# À propos
# ---------------------------------------------------------------------------
st.subheader("À propos")
st.markdown(
    """
| | |
|---|---|
| **Application** | Compta Pro & Perso |
| **Version** | 0.1.0 |
| **Python** | ≥ 3.11 |
| **Stack** | Streamlit · Polars · Supabase · GoCardless · Stripe |
| **Démarrage** | `streamlit run app/main.py` |
| **Tests** | `pytest tests/` |
| **Lint** | `ruff check src/ tests/` |
"""
)
