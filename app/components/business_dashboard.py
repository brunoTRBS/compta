"""Tableau de bord partagé pour les activités de micro-entreprise."""

import calendar
from datetime import date

import plotly.express as px
import polars as pl
import streamlit as st

from src.config import BusinessId
from src.logic.revenue import (
    _MONTH_LABELS,
    aggregate_expenses_by_category,
    aggregate_monthly_from_df,
    aggregate_revenue_by_category,
    compute_ytd_summary,
    pivot_by_category_month,
)
from src.services.db_reader import invalidate_cache, read_categories, read_transactions
from src.services.supabase import bulk_update_categories

from app.components.transaction_table import render_transaction_table

_MONTHS_LIST: list[str] = [_MONTH_LABELS[m] for m in range(1, 13)]
_MONTHS_MAP: dict[str, int] = {v: k for k, v in _MONTH_LABELS.items()}


def render_dashboard(business_id: BusinessId, business_name: str) -> None:
    tab_monthly, tab_global, tab_tx = st.tabs(
        ["📅 Vue mensuelle", "📊 Vue globale", "🏷️ Transactions"]
    )

    with tab_monthly:
        _render_monthly_view(business_id)

    with tab_global:
        _render_global_view(business_id)

    with tab_tx:
        _render_transactions(business_id)


# ---------------------------------------------------------------------------
# Vue mensuelle
# ---------------------------------------------------------------------------

def _render_monthly_view(business_id: BusinessId) -> None:
    today = date.today()
    current_year = today.year

    col_y, col_m = st.columns(2)
    with col_y:
        year: int = st.selectbox(
            "Année",
            [current_year, current_year - 1],
            key=f"mv_year_{business_id}",
        )
    with col_m:
        default_idx = today.month - 1
        month_label: str = st.selectbox(
            "Mois",
            _MONTHS_LIST,
            index=default_idx,
            key=f"mv_month_{business_id}",
        )
    month = _MONTHS_MAP[month_label]

    try:
        df = read_transactions(business_id=str(business_id), year=year, month=month)
    except Exception as exc:
        st.error(f"Impossible de charger les transactions : {exc}")
        return

    period_label = f"{month_label} {year}"

    # --- Bilan ---
    summary = compute_ytd_summary(df, business_id, year)
    benefices = summary["ca"] - summary["cotisations"] - summary["expenses"]

    st.subheader(f"Bilan — {period_label}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CA brut", f"{summary['ca']:,.2f} €")
    c2.metric("URSSAF", f"{summary['cotisations']:,.2f} €")
    c3.metric("Dépenses", f"{summary['expenses']:,.2f} €")
    c4.metric(
        "Bénéfices",
        f"{benefices:,.2f} €",
        delta=f"{benefices / summary['ca'] * 100:.1f} %" if summary["ca"] > 0 else None,
    )

    st.divider()

    # --- Tableau revenus par catégorie ---
    st.subheader("Revenus par catégorie")
    rev_df = aggregate_revenue_by_category(df, business_id)
    if rev_df.is_empty():
        st.info("Aucun revenu sur ce mois.")
    else:
        totals = pl.DataFrame({
            "category": ["Total"],
            "ca_brut": [rev_df["ca_brut"].sum()],
            "urssaf": [rev_df["urssaf"].sum()],
            "ca_net": [rev_df["ca_net"].sum()],
            "pct_ca": [100.0],
        })
        display_rev = pl.concat([rev_df, totals]).rename({
            "category": "Catégorie",
            "ca_brut": "CA Brut (€)",
            "urssaf": "URSSAF (€)",
            "ca_net": "CA Net (€)",
            "pct_ca": "% CA net",
        })
        st.dataframe(
            display_rev.to_pandas(),
            width='stretch',
            hide_index=True,
            column_config={
                "CA Brut (€)": st.column_config.NumberColumn(format="%.2f €"),
                "URSSAF (€)": st.column_config.NumberColumn(format="%.2f €"),
                "CA Net (€)": st.column_config.NumberColumn(format="%.2f €"),
                "% CA net": st.column_config.NumberColumn(format="%.1f %%"),
            },
        )

    st.divider()

    # --- Tableau dépenses par catégorie ---
    st.subheader("Dépenses par catégorie")
    exp_df = aggregate_expenses_by_category(df)
    if exp_df.is_empty():
        st.info("Aucune dépense sur ce mois.")
    else:
        totals_exp = pl.DataFrame({
            "category": ["Total"],
            "total": [exp_df["total"].sum()],
            "pct": [100.0],
        })
        display_exp = pl.concat([exp_df, totals_exp]).rename({
            "category": "Catégorie",
            "total": "Total (€)",
            "pct": "%",
        })
        st.dataframe(
            display_exp.to_pandas(),
            width='stretch',
            hide_index=True,
            column_config={
                "Total (€)": st.column_config.NumberColumn(format="%.2f €"),
                "%": st.column_config.NumberColumn(format="%.1f %%"),
            },
        )


# ---------------------------------------------------------------------------
# Vue globale
# ---------------------------------------------------------------------------

def _render_global_view(business_id: BusinessId) -> None:
    today = date.today()
    current_year = today.year

    period_type: str = st.radio(
        "Période",
        ["Année complète", "Période personnalisée"],
        horizontal=True,
        key=f"gv_period_type_{business_id}",
    )

    if period_type == "Année complète":
        year: int = st.selectbox(
            "Année",
            [current_year, current_year - 1],
            key=f"gv_year_{business_id}",
        )
        date_from = date(year, 1, 1)
        date_to = date(year, 12, 31)
    else:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            sm_label: str = st.selectbox("Mois début", _MONTHS_LIST, key=f"gv_sm_{business_id}")
        with c2:
            sy: int = st.selectbox(
                "Année début", [current_year, current_year - 1], key=f"gv_sy_{business_id}"
            )
        with c3:
            em_label: str = st.selectbox(
                "Mois fin", _MONTHS_LIST, index=len(_MONTHS_LIST) - 1, key=f"gv_em_{business_id}"
            )
        with c4:
            ey: int = st.selectbox(
                "Année fin", [current_year, current_year - 1], key=f"gv_ey_{business_id}"
            )
        sm, em = _MONTHS_MAP[sm_label], _MONTHS_MAP[em_label]
        date_from = date(sy, sm, 1)
        date_to = date(ey, em, calendar.monthrange(ey, em)[1])

    try:
        df = read_transactions(business_id=str(business_id), date_from=date_from, date_to=date_to)
    except Exception as exc:
        st.error(f"Impossible de charger les transactions : {exc}")
        return

    if df.is_empty():
        st.info("Aucune transaction sur la période sélectionnée.")
        return

    summary = compute_ytd_summary(df, business_id, date_from.year)
    if summary["is_above_threshold"] and period_type == "Année complète":
        st.warning(
            f"⚠️ CA ({summary['ca']:,.0f} €) dépasse le seuil micro-entreprise "
            f"({summary['ca_threshold']:,.0f} €). Consultez un expert-comptable."
        )

    # --- Tableau croisé revenus ---
    st.subheader("Revenus par catégorie et par mois")
    rev_pivot = pivot_by_category_month(df, "income")
    if rev_pivot.is_empty():
        st.info("Aucun revenu sur la période.")
    else:
        _show_pivot(rev_pivot)

    st.divider()

    # --- Tableau croisé dépenses ---
    st.subheader("Dépenses par catégorie et par mois")
    exp_pivot = pivot_by_category_month(df, "expense")
    if exp_pivot.is_empty():
        st.info("Aucune dépense sur la période.")
    else:
        _show_pivot(exp_pivot)

    st.divider()

    # --- Graphique évolution ---
    st.subheader("Évolution revenus / dépenses")
    monthly = aggregate_monthly_from_df(df)
    if monthly["revenue"].sum() > 0 or monthly["expenses"].sum() > 0:
        fig = px.line(
            monthly.to_pandas(),
            x="month_label",
            y=["revenue", "expenses"],
            labels={"month_label": "Mois", "value": "€", "variable": ""},
            color_discrete_map={"revenue": "#2ecc71", "expenses": "#e74c3c"},
            markers=True,
        )
        fig.update_layout(legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("Pas de données pour le graphique.")


def _show_pivot(pivot: pl.DataFrame) -> None:
    """Affiche un tableau croisé avec formatage des colonnes numériques."""
    renamed = pivot.rename({"category": "Catégorie"})
    numeric_cols = [c for c in renamed.columns if c != "Catégorie"]
    col_cfg = {c: st.column_config.NumberColumn(format="%.2f €") for c in numeric_cols}
    st.dataframe(
        renamed.to_pandas(),
        width='stretch',
        hide_index=True,
        column_config=col_cfg,
    )


# ---------------------------------------------------------------------------
# Transactions (catégorisation)
# ---------------------------------------------------------------------------

def _render_transactions(business_id: BusinessId) -> None:
    today = date.today()
    current_year = today.year

    col_y, col_m = st.columns(2)
    with col_y:
        year: int = st.selectbox(
            "Année",
            [current_year, current_year - 1],
            key=f"tx_year_{business_id}",
        )
    with col_m:
        month_options: dict[str, int | None] = {"Tous": None}
        month_options.update({_MONTH_LABELS[m]: m for m in range(1, 13)})
        sel_label: str = st.selectbox(
            "Mois",
            list(month_options.keys()),
            key=f"tx_month_{business_id}",
        )
    sel_month = month_options[sel_label]

    try:
        df = read_transactions(business_id=str(business_id), year=year, month=sel_month)
    except Exception as exc:
        st.error(f"Impossible de charger les transactions : {exc}")
        return

    if df.is_empty():
        st.info("Aucune transaction sur la période sélectionnée.")
        return

    def save_categories(updates: list[dict]) -> None:
        bulk_update_categories(updates)
        invalidate_cache()

    cat_df = read_categories(business_id=str(business_id))
    categories = sorted(cat_df["name"].to_list())
    render_transaction_table(
        df, key=f"table_{business_id}", categories=categories, on_save=save_categories
    )
