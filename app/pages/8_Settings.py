"""Page Paramètres — gestion des catégories, statut des connexions, cache."""

import streamlit as st

from app.components.auth import require_auth
from src.services.db_reader import invalidate_cache
from src.services.supabase import delete_category, fetch_categories, insert_category
from src.utils.health import HealthStatus, run_all_checks

st.set_page_config(page_title="Paramètres", page_icon="⚙️", layout="wide")
require_auth()
st.title("Paramètres & Statut")

# ---------------------------------------------------------------------------
# Gestion des catégories
# ---------------------------------------------------------------------------
st.subheader("Gestion des catégories")
st.caption("Créez, consultez et supprimez les catégories disponibles par activité.")

_BUSINESSES = {
    "Phi Rising": "phi_rising",
    "Booth in Lyon": "booth_in_lyon",
    "Perso": "personal",
}

tab_phi, tab_booth, tab_perso = st.tabs(list(_BUSINESSES.keys()))

for tab, (label, biz_id) in zip([tab_phi, tab_booth, tab_perso], _BUSINESSES.items()):
    with tab:
        cats = fetch_categories(business_id=biz_id)
        expenses = [c for c in cats if c["direction"] == "expense"]
        incomes = [c for c in cats if c["direction"] == "income"]

        col_exp, col_inc = st.columns(2)

        with col_exp:
            st.markdown("**Dépenses**")
            if expenses:
                for cat in expenses:
                    c_name, c_del = st.columns([5, 1])
                    c_name.write(cat["name"])
                    if c_del.button("✕", key=f"del_{cat['id']}", help="Supprimer"):
                        delete_category(cat["id"])
                        invalidate_cache()
                        st.rerun()
            else:
                st.caption("Aucune catégorie de dépense.")

        with col_inc:
            st.markdown("**Revenus**")
            if incomes:
                for cat in incomes:
                    c_name, c_del = st.columns([5, 1])
                    c_name.write(cat["name"])
                    if c_del.button("✕", key=f"del_{cat['id']}", help="Supprimer"):
                        delete_category(cat["id"])
                        invalidate_cache()
                        st.rerun()
            else:
                st.caption("Aucune catégorie de revenu.")

        st.markdown("---")
        st.markdown("**Nouvelle catégorie**")

        with st.form(key=f"form_cat_{biz_id}", clear_on_submit=True):
            col_name, col_dir, col_submit = st.columns([4, 2, 1])
            new_name = col_name.text_input(
                "Nom",
                placeholder="Nom de la catégorie",
                label_visibility="collapsed",
                key=f"cat_name_{biz_id}",
            )
            new_direction = col_dir.selectbox(
                "Direction",
                options=["expense", "income"],
                format_func=lambda x: "Dépense" if x == "expense" else "Revenu",
                label_visibility="collapsed",
                key=f"cat_dir_{biz_id}",
            )
            submitted = col_submit.form_submit_button("Ajouter", width='stretch')

        if submitted:
            if not new_name.strip():
                st.error("Le nom de la catégorie ne peut pas être vide.")
            else:
                try:
                    insert_category(biz_id, new_name.strip(), new_direction)
                    invalidate_cache()
                    st.toast(f"Catégorie « {new_name.strip()} » ajoutée.", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Erreur : {exc}")

st.divider()

# ---------------------------------------------------------------------------
# Statut des connexions
# ---------------------------------------------------------------------------
st.subheader("Statut des connexions")

_STATUS_CACHE_KEY = "_settings_health"

col_check, _ = st.columns([1, 3])
with col_check:
    if st.button("🔄 Vérifier les connexions", width='stretch'):
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
    if st.button("🗑️ Vider le cache", width='stretch'):
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
