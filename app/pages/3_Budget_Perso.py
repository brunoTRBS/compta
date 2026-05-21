"""Page Budget Personnel — dépenses, épargne, catégorisation."""

import polars as pl
import plotly.express as px
import streamlit as st
from datetime import date

from src.config import BusinessId
from src.logic.budget import breakdown_by_category, compute_budget_summary
from src.logic.categorizer import apply_rules, categorization_stats, get_pending_categorization
from src.logic.revenue import aggregate_monthly
from src.services.db_reader import invalidate_cache, read_categories, read_transactions
from src.services.supabase import bulk_update_categories, fetch_categorization_rules
from app.components.transaction_table import render_transaction_table

st.set_page_config(page_title="Budget Perso", page_icon="💰", layout="wide")
st.title("Budget Personnel")

_MONTH_LABELS = {
    1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Aoû", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Déc",
}
_SAVINGS_RATE_TARGET = 20.0  # % cible

# ---------------------------------------------------------------------------
# Filtres sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("Filtres")
    current_year = date.today().year
    year = st.selectbox("Année", [current_year, current_year - 1], key="year_perso")
    month_options: dict[str, int | None] = {"Tous": None}
    month_options.update({_MONTH_LABELS[m]: m for m in range(1, 13)})
    selected_month_label = st.selectbox("Mois", list(month_options.keys()), key="month_perso")
    selected_month = month_options[selected_month_label]

# ---------------------------------------------------------------------------
# Chargement des données
# ---------------------------------------------------------------------------
try:
    df = read_transactions(
        business_id=str(BusinessId.PERSONAL),
        year=year,
        month=selected_month,
    )
except Exception as exc:
    st.error(f"Impossible de charger les transactions : {exc}")
    st.stop()

summary = compute_budget_summary(df, year, selected_month)

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
period_label = f"{_MONTH_LABELS[selected_month]} {year}" if selected_month else f"YTD {year}"
st.subheader(f"Résumé {period_label}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Revenus", f"{summary['income']:,.0f} €")
col2.metric("Dépenses", f"{summary['expenses']:,.0f} €")
col3.metric(
    "Épargne",
    f"{summary['savings']:,.0f} €",
    delta=f"{summary['savings']:+,.0f} €" if summary["savings"] != 0 else None,
)
col4.metric(
    "Taux d'épargne",
    f"{summary['savings_rate']:.1f} %",
    delta=f"{summary['savings_rate'] - _SAVINGS_RATE_TARGET:+.1f} pts vs {_SAVINGS_RATE_TARGET:.0f} % cible",
    delta_color="normal",
)

if summary["savings_rate"] < _SAVINGS_RATE_TARGET and summary["income"] > 0:
    st.warning(
        f"Taux d'épargne ({summary['savings_rate']:.1f} %) sous la cible de {_SAVINGS_RATE_TARGET:.0f} %."
    )

st.divider()

# ---------------------------------------------------------------------------
# Graphiques
# ---------------------------------------------------------------------------
col_left, col_right = st.columns(2)

with col_left:
    breakdown = breakdown_by_category(df)
    if not breakdown.is_empty():
        fig = px.bar(
            breakdown.head(10).to_pandas(),
            x="total",
            y="category",
            orientation="h",
            title="Répartition des dépenses",
            text="pct",
            labels={"total": "€", "category": "Catégorie"},
            color_discrete_sequence=["#e74c3c"],
        )
        fig.update_traces(texttemplate="%{text:.1f} %", textposition="outside")
        fig.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("Aucune dépense catégorisée sur la période.")

with col_right:
    monthly_df = aggregate_monthly(df, year).with_columns(
        pl.col("month").map_elements(
            lambda m: _MONTH_LABELS.get(int(m), str(m)), return_dtype=pl.Utf8
        ).alias("month_label")
    )
    if monthly_df["expenses"].sum() > 0 or monthly_df["revenue"].sum() > 0:
        fig2 = px.line(
            monthly_df.to_pandas(),
            x="month_label",
            y=["revenue", "expenses"],
            title=f"Revenus & Dépenses — {year}",
            labels={"month_label": "Mois", "value": "€", "variable": ""},
            markers=True,
            color_discrete_map={"revenue": "#2ecc71", "expenses": "#e74c3c"},
        )
        st.plotly_chart(fig2, width='stretch')
    else:
        st.info("Pas encore de données pour le graphique mensuel.")

st.divider()

# ---------------------------------------------------------------------------
# Catégorisation
# ---------------------------------------------------------------------------
st.subheader("Catégorisation")

cat_df = read_categories(business_id=str(BusinessId.PERSONAL))
_categories = sorted(cat_df["name"].to_list())

stats = categorization_stats(df)
sc1, sc2, sc3 = st.columns(3)
sc1.metric("Total transactions", stats["total"])
sc2.metric("Catégorisées", f"{stats['categorized']} ({stats['coverage_pct']:.0f} %)")
sc3.metric("En attente", stats["pending"])

pending = get_pending_categorization(df)

if not pending.is_empty():
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        if st.button("⚡ Appliquer les règles auto", width='stretch'):
            rules = fetch_categorization_rules()
            auto_df = apply_rules(pending, rules)
            updates = [
                {"id": row["id"], "category": row["category"]}
                for row in auto_df.iter_rows(named=True)
                if row.get("category")
            ]
            if updates:
                bulk_update_categories(updates)
                invalidate_cache()
                st.toast(f"{len(updates)} transaction(s) catégorisée(s) automatiquement.", icon="✅")
                st.rerun()
            else:
                st.toast("Aucune règle ne correspond aux transactions en attente.", icon="ℹ️")
    with col_info:
        st.caption(f"{len(pending)} transaction(s) sans catégorie — éditez directement ci-dessous.")

    def _save_pending(updates: list[dict]) -> None:
        bulk_update_categories(updates)
        invalidate_cache()

    render_transaction_table(pending, key="pending_perso", categories=_categories, on_save=_save_pending)
else:
    st.success("✅ Toutes les transactions sont catégorisées.")

st.divider()

# ---------------------------------------------------------------------------
# Tableau complet
# ---------------------------------------------------------------------------
with st.expander("Voir toutes les transactions", expanded=False):
    def _save_all(updates: list[dict]) -> None:
        bulk_update_categories(updates)
        invalidate_cache()

    render_transaction_table(df, key="all_perso", categories=_categories, on_save=_save_all)
