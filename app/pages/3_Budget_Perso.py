"""Page Budget Personnel — dépenses, épargne, catégorisation."""

import polars as pl
import plotly.express as px
import streamlit as st
from datetime import date

from src.config import BusinessId
from src.logic.budget import breakdown_by_category, compute_budget_summary
from app.components.auth import require_auth
from src.services.db_reader import read_transactions

st.set_page_config(page_title="Budget Perso", page_icon="💰", layout="wide")
require_auth()
st.title("Budget Personnel")

_MONTH_LABELS = {
    1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Aoû", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Déc",
}
_SAVINGS_CATEGORY = "Épargne"

# ---------------------------------------------------------------------------
# Filtres sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("Filtres")
    current_year = date.today().year
    current_month = date.today().month
    year = st.selectbox("Année", [current_year, current_year - 1], key="year_perso")
    month_labels = list(_MONTH_LABELS.values())
    default_month_idx = current_month - 1
    selected_month_label = st.selectbox(
        "Mois", month_labels, index=default_month_idx, key="month_perso"
    )
    selected_month = month_labels.index(selected_month_label) + 1

# ---------------------------------------------------------------------------
# Mois N-1
# ---------------------------------------------------------------------------
prev_month = selected_month - 1 if selected_month > 1 else 12
prev_year = year if selected_month > 1 else year - 1

# ---------------------------------------------------------------------------
# Chargement des données
# ---------------------------------------------------------------------------
try:
    df = read_transactions(
        business_id=str(BusinessId.PERSONAL),
        year=year,
        month=selected_month,
    )
    df_prev = read_transactions(
        business_id=str(BusinessId.PERSONAL),
        year=prev_year,
        month=prev_month,
    )
except Exception as exc:
    st.error(f"Impossible de charger les transactions : {exc}")
    st.stop()

summary = compute_budget_summary(df, year, selected_month)
summary_prev = compute_budget_summary(df_prev, prev_year, prev_month)

def _savings_amount(frame: pl.DataFrame) -> float:
    filtered = frame.filter(
        (pl.col("amount") < 0) & (pl.col("category") == _SAVINGS_CATEGORY)
    )
    return abs(float(filtered["amount"].sum() or 0.0))

savings = _savings_amount(df)
expenses_excl_savings = summary["expenses"] - savings
difference = summary["savings"]
reste_n1 = summary_prev["savings"]
total_fin_mois = reste_n1 + difference

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
period_label = f"{_MONTH_LABELS[selected_month]} {year}"
st.subheader(f"Résumé {period_label}")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Revenus", f"{summary['income']:,.0f} €")
c2.metric("Dépenses", f"{expenses_excl_savings:,.0f} €")
c3.metric("Épargne", f"{savings:,.0f} €")
c4.metric("Différence", f"{difference:,.0f} €", delta=f"{difference:+,.0f} €" if difference != 0 else None)
c5.metric(
    f"Reste {_MONTH_LABELS[prev_month]} {prev_year}",
    f"{reste_n1:,.0f} €",
)
c6.metric("Total fin du mois", f"{total_fin_mois:,.0f} €")

st.divider()

# ---------------------------------------------------------------------------
# Graphique + liste des dépenses
# ---------------------------------------------------------------------------
col_chart, col_table = st.columns([1, 2])

with col_chart:
    breakdown = breakdown_by_category(df)
    if not breakdown.is_empty():
        fig = px.pie(
            breakdown.head(10).to_pandas(),
            values="total",
            names="category",
            title="Répartition des dépenses",
            hole=0.4,
        )
        fig.update_traces(textinfo="percent+label", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucune dépense catégorisée sur la période.")

with col_table:
    st.subheader("Dépenses du mois")
    expenses_df = (
        df.filter(pl.col("amount") < 0)
        .select(["date", "label", "amount", "category"])
        .sort("date", descending=True)
    )
    if not expenses_df.is_empty():
        st.dataframe(
            expenses_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                "label": st.column_config.TextColumn("Libellé"),
                "amount": st.column_config.NumberColumn("Montant (€)", format="%.2f €"),
                "category": st.column_config.TextColumn("Catégorie"),
            },
        )
    else:
        st.info("Aucune dépense sur la période.")
