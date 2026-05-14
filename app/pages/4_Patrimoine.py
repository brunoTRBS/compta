"""Page Bilan Patrimonial — soldes, évolution, mise à jour manuelle."""

import plotly.express as px
import streamlit as st
from datetime import date

from src.logic.patrimoine import (
    aggregate_by_account_type,
    compute_net_worth,
    compute_patrimoine_evolution,
    group_by_owner,
)
from src.services.db_reader import (
    invalidate_cache,
    read_accounts,
    read_patrimoine_evolution,
)
from src.services.supabase import fetch_accounts, update_account_balance

st.set_page_config(page_title="Patrimoine", page_icon="🏦", layout="wide")
st.title("Bilan Patrimonial")

_OWNER_LABELS = {
    "personal": "Perso",
    "phi_rising": "Phi Rising",
    "booth_in_lyon": "Booth in Lyon",
}
_TYPE_LABELS = {
    "current": "Compte courant",
    "savings": "Épargne (Livrets)",
    "revolut": "Revolut",
    "securities": "Titres / PEA",
    "cash": "Espèces",
}

# ---------------------------------------------------------------------------
# Chargement des données
# ---------------------------------------------------------------------------
try:
    accounts_df = read_accounts()
    accounts_raw = fetch_accounts()
except Exception as exc:
    st.error(f"Impossible de charger les comptes : {exc}")
    st.stop()

# ---------------------------------------------------------------------------
# KPIs — Patrimoine global
# ---------------------------------------------------------------------------
net_worth = compute_net_worth(accounts_df)
by_owner = group_by_owner(accounts_df)

st.subheader("Vue globale")
kpi_cols = st.columns(1 + len(by_owner))
kpi_cols[0].metric("Patrimoine net total", f"{net_worth:,.0f} €")
for i, (owner, total) in enumerate(by_owner.items(), start=1):
    kpi_cols[i].metric(_OWNER_LABELS.get(owner, owner), f"{total:,.0f} €")

st.divider()

# ---------------------------------------------------------------------------
# Répartition par type & liste des comptes
# ---------------------------------------------------------------------------
col_left, col_right = st.columns([1, 2])

with col_left:
    by_type = aggregate_by_account_type(accounts_df)
    if not by_type.is_empty():
        fig_pie = px.pie(
            by_type.to_pandas(),
            names="type",
            values="total_balance",
            title="Répartition par type",
            labels={"type": "Type", "total_balance": "Solde (€)"},
            hole=0.4,
        )
        fig_pie.update_traces(
            texttemplate="%{label}<br>%{value:,.0f} €",
            textposition="outside",
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Aucun compte configuré.")

with col_right:
    st.subheader("Détail des comptes")
    if not accounts_df.is_empty():
        import polars as pl

        display_df = (
            accounts_df.select(["name", "institution", "type", "owner", "currency", "balance"])
            .with_columns(
                pl.col("owner").map_elements(lambda o: _OWNER_LABELS.get(o, o), return_dtype=pl.Utf8),
                pl.col("type").map_elements(lambda t: _TYPE_LABELS.get(t, t), return_dtype=pl.Utf8),
            )
            .rename({
                "name": "Compte", "institution": "Banque", "type": "Type",
                "owner": "Périmètre", "currency": "Devise", "balance": "Solde (€)",
            })
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("Aucun compte à afficher.")

st.divider()

# ---------------------------------------------------------------------------
# Évolution du patrimoine
# ---------------------------------------------------------------------------
current_year = date.today().year
st.subheader("Évolution du patrimoine")

col_evo_filter, _ = st.columns([1, 3])
with col_evo_filter:
    year_evo = st.selectbox("Année", [current_year, current_year - 1], key="year_evo")

try:
    history_df = read_patrimoine_evolution(owner="personal", year=year_evo)
    evolution_df = compute_patrimoine_evolution(history_df)
except Exception:
    evolution_df = None

if evolution_df is not None and not evolution_df.is_empty():
    fig_line = px.line(
        evolution_df.to_pandas(),
        x="date",
        y="total_balance",
        title=f"Patrimoine personnel — {year_evo}",
        labels={"date": "Date", "total_balance": "Solde total (€)"},
        markers=True,
    )
    fig_line.update_layout(yaxis_tickformat=",.0f")
    st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info(
        "Pas encore d'historique de soldes. "
        "Utilisez le formulaire ci-dessous pour enregistrer les soldes actuels."
    )

st.divider()

# ---------------------------------------------------------------------------
# Formulaire — mise à jour manuelle d'un solde
# ---------------------------------------------------------------------------
st.subheader("Mettre à jour un solde")

if not accounts_raw:
    st.info("Aucun compte disponible. Ajoutez des comptes dans Supabase d'abord.")
else:
    account_options = {f"{a['name']} ({a.get('institution', '?')})": a["id"] for a in accounts_raw}

    with st.form("update_balance_form", clear_on_submit=True):
        selected_account_label = st.selectbox(
            "Compte", list(account_options.keys()), key="form_account"
        )
        new_balance = st.number_input(
            "Nouveau solde (€)",
            value=0.0,
            step=0.01,
            format="%.2f",
            key="form_balance",
        )
        submit = st.form_submit_button("Enregistrer le solde", use_container_width=True)

    if submit:
        account_id = account_options[selected_account_label]
        try:
            update_account_balance(account_id, new_balance)
            invalidate_cache()
            st.toast(
                f"Solde de « {selected_account_label} » mis à jour : {new_balance:,.2f} €",
                icon="✅",
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Erreur lors de la mise à jour : {exc}")
