"""Page Vue consolidée — flux des 3 activités + détail par compte réel."""

from datetime import date

import plotly.express as px
import polars as pl
import streamlit as st

from app.components.auth import require_auth
from src.config import BusinessId
from src.logic.budget import compute_budget_summary
from src.logic.consolidated import flows_per_account, pair_transfers
from src.logic.revenue import _MONTH_LABELS, aggregate_monthly_from_df
from src.services.db_reader import read_accounts, read_transactions

st.set_page_config(page_title="Vue consolidée", page_icon="🧮", layout="wide")
require_auth()
st.title("Vue consolidée")
st.caption("Perso, Phi Rising et Booth in Lyon sur une même vue — flux du mois et détail par compte réel.")

_BUSINESS_LABELS: dict[str, str] = {
    "Perso": str(BusinessId.PERSONAL),
    "Phi Rising": str(BusinessId.PHI_RISING),
    "Booth in Lyon": str(BusinessId.BOOTH_IN_LYON),
}
_MONTHS_LIST: list[str] = [_MONTH_LABELS[m] for m in range(1, 13)]
_MONTHS_MAP: dict[str, int] = {v: k for k, v in _MONTH_LABELS.items()}

# ---------------------------------------------------------------------------
# Filtres sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("Filtres")
    current_year = date.today().year
    current_month = date.today().month
    year = st.selectbox("Année", [current_year, current_year - 1], key="year_consolidee")
    default_month_idx = current_month - 1
    selected_month_label = st.selectbox(
        "Mois", _MONTHS_LIST, index=default_month_idx, key="month_consolidee"
    )
    selected_month = _MONTHS_MAP[selected_month_label]

period_label = f"{selected_month_label} {year}"

# ---------------------------------------------------------------------------
# KPIs par activité (revenus/dépenses/solde, virements exclus)
# ---------------------------------------------------------------------------
st.subheader(f"Résumé — {period_label}")

summaries: dict[str, dict] = {}
for label, biz_id in _BUSINESS_LABELS.items():
    try:
        df_month = read_transactions(business_id=biz_id, year=year, month=selected_month)
    except Exception as exc:
        st.error(f"Impossible de charger les transactions ({label}) : {exc}")
        df_month = pl.DataFrame()
    summaries[label] = compute_budget_summary(df_month, year, selected_month)

cols = st.columns(len(_BUSINESS_LABELS) + 1)
total_income = sum(s["income"] for s in summaries.values())
total_expenses = sum(s["expenses"] for s in summaries.values())

for col, (label, summary) in zip(cols, summaries.items()):
    with col:
        st.markdown(f"**{label}**")
        st.metric("Revenus", f"{summary['income']:,.2f} €")
        st.metric("Dépenses", f"{summary['expenses']:,.2f} €")
        st.metric("Solde", f"{summary['savings']:,.2f} €")

with cols[-1]:
    st.markdown("**Total**")
    st.metric("Revenus", f"{total_income:,.2f} €")
    st.metric("Dépenses", f"{total_expenses:,.2f} €")
    st.metric("Solde", f"{total_income - total_expenses:,.2f} €")

st.divider()

# ---------------------------------------------------------------------------
# Évolution combinée sur l'année
# ---------------------------------------------------------------------------
st.subheader(f"Évolution — {year}")

monthly_frames = []
for label, biz_id in _BUSINESS_LABELS.items():
    try:
        df_year = read_transactions(business_id=biz_id, year=year)
    except Exception:
        continue
    if df_year.is_empty():
        continue
    monthly = aggregate_monthly_from_df(df_year).with_columns(pl.lit(label).alias("activité"))
    monthly_frames.append(monthly)

if monthly_frames:
    combined = pl.concat(monthly_frames, how="diagonal_relaxed")
    fig = px.line(
        combined.to_pandas(),
        x="month_label",
        y="net",
        color="activité",
        markers=True,
        labels={"month_label": "Mois", "net": "Solde net (€)", "activité": ""},
    )
    fig.update_layout(legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, width='stretch')
else:
    st.info("Pas de données sur cette année.")

st.divider()

# ---------------------------------------------------------------------------
# Détail par compte réel + mouvements internes
# ---------------------------------------------------------------------------
st.subheader(f"Détail par compte — {period_label}")

try:
    accounts_df = read_accounts()
except Exception as exc:
    st.error(f"Impossible de charger les comptes : {exc}")
    accounts_df = pl.DataFrame()

period_frames = []
for biz_id in _BUSINESS_LABELS.values():
    try:
        df_biz = read_transactions(
            business_id=biz_id, year=year, month=selected_month, include_transfers=True
        )
    except Exception:
        continue
    if not df_biz.is_empty():
        period_frames.append(df_biz)

period_df = pl.concat(period_frames, how="diagonal_relaxed") if period_frames else pl.DataFrame()

col_accounts, col_transfers = st.columns([3, 2])

with col_accounts:
    st.markdown("**Comptes**")
    if accounts_df.is_empty():
        st.info("Aucun compte configuré.")
    else:
        flows = flows_per_account(period_df, accounts_df)
        display_flows = (
            flows.select(["name", "institution", "type", "balance", "flux"])
            .rename({
                "name": "Compte", "institution": "Banque", "type": "Type",
                "balance": "Solde actuel (€)", "flux": f"Flux {selected_month_label} (€)",
            })
        )
        st.dataframe(
            display_flows,
            width='stretch',
            hide_index=True,
            column_config={
                "Solde actuel (€)": st.column_config.NumberColumn(format="%.2f €"),
                f"Flux {selected_month_label} (€)": st.column_config.NumberColumn(format="%.2f €"),
            },
        )

with col_transfers:
    st.markdown("**🔁 Mouvements internes du mois**")
    transfers = pair_transfers(period_df, accounts_df) if not period_df.is_empty() else pl.DataFrame()
    if transfers.is_empty():
        st.info("Aucun virement enregistré sur cette période.")
    else:
        st.dataframe(
            transfers.select(["date", "label", "from_account", "to_account", "amount"]).rename({
                "date": "Date", "label": "Libellé", "from_account": "De",
                "to_account": "Vers", "amount": "Montant (€)",
            }),
            width='stretch',
            hide_index=True,
            column_config={
                "Date": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Montant (€)": st.column_config.NumberColumn(format="%.2f €"),
            },
        )
