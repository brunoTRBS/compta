"""Tableau de bord partagé pour les activités de micro-entreprise."""

from datetime import date

import plotly.express as px
import polars as pl
import streamlit as st

from src.config import BusinessId
from src.logic.revenue import aggregate_monthly, compute_ytd_summary
from src.services.db_reader import invalidate_cache, read_transactions
from src.services.supabase import bulk_update_categories

from app.components.transaction_table import render_transaction_table

_MONTH_LABELS = {
    1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Aoû", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Déc",
}


def render_dashboard(business_id: BusinessId, business_name: str) -> None:
    """Rend le tableau de bord complet pour une activité micro-entreprise.

    Args:
        business_id: Identifiant de l'activité (phi_rising ou booth_in_lyon).
        business_name: Nom affiché dans le titre et les labels.
    """
    # --- Filtres sidebar ---
    with st.sidebar:
        st.subheader("Filtres")
        current_year = date.today().year
        year = st.selectbox(
            "Année",
            [current_year, current_year - 1],
            key=f"year_{business_id}",
        )
        month_options: dict[str, int | None] = {"Tous": None}
        month_options.update({_MONTH_LABELS[m]: m for m in range(1, 13)})
        selected_month_label = st.selectbox(
            "Mois",
            list(month_options.keys()),
            key=f"month_{business_id}",
        )
        selected_month = month_options[selected_month_label]

    # --- Chargement des données ---
    try:
        df = read_transactions(
            business_id=str(business_id),
            year=year,
            month=selected_month,
        )
    except Exception as exc:
        st.error(f"Impossible de charger les transactions : {exc}")
        st.info("Vérifiez que SUPABASE_URL, SUPABASE_KEY et DB_URL sont configurées.")
        return

    summary = compute_ytd_summary(df, business_id, year)

    # --- Alerte dépassement seuil ---
    if summary["is_above_threshold"]:
        st.warning(
            f"⚠️ CA YTD ({summary['ca']:,.0f} €) dépasse le seuil micro-entreprise "
            f"({summary['ca_threshold']:,.0f} €). Consultez un expert-comptable."
        )

    # --- KPIs ---
    period_label = (
        f"{_MONTH_LABELS[selected_month]} {year}" if selected_month else f"YTD {year}"
    )
    st.subheader(f"Résumé {period_label}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("CA encaissé", f"{summary['ca']:,.0f} €")
    col2.metric(
        "Cotisations URSSAF",
        f"{summary['cotisations']:,.0f} €",
        help="Calculées sur le CA total de la période sélectionnée.",
    )
    col3.metric("Charges", f"{summary['expenses']:,.0f} €")
    col4.metric(
        "Marge nette",
        f"{summary['net_margin']:,.0f} €",
        delta=(
            f"{summary['net_margin'] / summary['ca'] * 100:.1f} %"
            if summary["ca"] > 0
            else None
        ),
    )

    st.divider()

    # --- Graphiques ---
    col_left, col_right = st.columns(2)

    with col_left:
        monthly_df = aggregate_monthly(df, year).with_columns(
            pl.col("month").map_elements(
                lambda m: _MONTH_LABELS.get(int(m), str(m)), return_dtype=pl.Utf8
            ).alias("month_label")
        )
        if monthly_df["revenue"].sum() > 0 or monthly_df["expenses"].sum() > 0:
            fig = px.bar(
                monthly_df.to_pandas(),
                x="month_label",
                y=["revenue", "expenses"],
                barmode="group",
                title=f"CA & Charges mensuels {year}",
                labels={"month_label": "Mois", "value": "€", "variable": ""},
                color_discrete_map={"revenue": "#2ecc71", "expenses": "#e74c3c"},
            )
            fig.update_layout(legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Pas encore de données pour le graphique mensuel.")

    with col_right:
        expenses_df = (
            df.filter(pl.col("amount") < 0)
            .with_columns(pl.col("amount").abs().alias("amount_abs"))
            .group_by("category")
            .agg(pl.col("amount_abs").sum().alias("total"))
            .sort("total", descending=True)
        )
        if not expenses_df.is_empty():
            fig2 = px.bar(
                expenses_df.to_pandas(),
                x="total",
                y="category",
                orientation="h",
                title="Répartition des charges",
                labels={"total": "€", "category": "Catégorie"},
                color_discrete_sequence=["#e74c3c"],
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Aucune charge sur la période.")

    st.divider()

    # --- Tableau des transactions ---
    st.subheader("Transactions")
    if df.is_empty():
        st.info("Aucune transaction sur la période sélectionnée.")
        return

    def save_categories(updates: list[dict]) -> None:
        bulk_update_categories(updates)
        invalidate_cache()

    render_transaction_table(df, key=f"table_{business_id}", on_save=save_categories)
