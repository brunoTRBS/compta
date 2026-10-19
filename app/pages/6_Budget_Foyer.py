"""Page Budget Foyer — rentrées et dépenses du compte commun."""

import calendar
from datetime import date

import plotly.express as px
import polars as pl
import streamlit as st

from app.components.auth import require_auth
from src.config import HOUSEHOLD_NON_COMMON_CATEGORIES, JOINT_ACCOUNT_NAME, BusinessId
from src.logic.budget import breakdown_by_category
from src.logic.household_budget import (
    common_expenses,
    contributions,
    exceptional_operations,
    regular_operations,
    spending_by_payer,
    summarize,
)
from src.logic.revenue import _MONTH_LABELS, aggregate_monthly_from_df, pivot_by_category_month
from src.services.db_reader import invalidate_cache, read_statement_balances, read_transactions
from src.services.supabase import bulk_update_transaction_fields, fetch_accounts

st.set_page_config(page_title="Budget Foyer", page_icon="🏠", layout="wide")
require_auth()
st.title("Budget du foyer")
st.caption(
    "Le compte commun : ce que Charlotte et Bruno y mettent, ce qui en sort. "
    "Les achats perso de Charlotte (carte cochée « perso ») n'y figurent pas — ils sont "
    "dans Budget Perso."
)


def _fmt(value: float) -> str:
    return f"{value:,.2f} €".replace(",", " ")


try:
    household_df = read_transactions(business_id=str(BusinessId.HOUSEHOLD))
    joint_account = next((a for a in fetch_accounts() if a["name"] == JOINT_ACCOUNT_NAME), None)
except Exception as exc:
    st.error(f"Impossible de charger les données : {exc}")
    st.stop()

if household_df.is_empty():
    st.info("Aucune opération du compte commun pour l'instant : importe un relevé depuis la page Sync.")
    st.stop()

n_uncategorized = household_df.filter(pl.col("category").is_null()).height
if n_uncategorized:
    st.warning(f"{n_uncategorized} opération(s) du foyer pas encore classée(s).")
    st.page_link("pages/1_A_Traiter.py", label="Les classer dans « À traiter »", icon="📥")

# ---------------------------------------------------------------------------
# Période
# ---------------------------------------------------------------------------
today = date.today()
years = sorted({d.year for d in household_df["date"].to_list()} | {today.year}, reverse=True)
col_y, col_m = st.columns(2)
year = col_y.selectbox("Année", years, key="foyer_year")
month_labels = [_MONTH_LABELS[m] for m in range(1, 13)]
month = month_labels.index(
    col_m.selectbox("Mois", month_labels, index=today.month - 1, key="foyer_month")
) + 1

month_start = date(year, month, 1)
month_end = date(year, month, calendar.monthrange(year, month)[1])
regular = regular_operations(household_df)
month_df = regular.filter(pl.col("date").is_between(month_start, month_end))

# ---------------------------------------------------------------------------
# Résumé du mois
# ---------------------------------------------------------------------------
st.subheader(f"Résumé {_MONTH_LABELS[month]} {year}")
summary = summarize(month_df)

balance_label, balance_value = "Solde du compte", "—"
if joint_account:
    balances = read_statement_balances(joint_account["id"])
    known = balances.filter(pl.col("date") <= month_end) if not balances.is_empty() else balances
    if not known.is_empty():
        last = known.sort("date").row(-1, named=True)
        balance_label = f"Solde au {last['date']:%d/%m}"
        balance_value = _fmt(last["balance"])

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Rentrées", _fmt(summary["income"]))
c2.metric("Dépenses communes", _fmt(summary["common_expenses"]))
c3.metric("Perso & épargne Bruno", _fmt(summary["non_common"]),
          help=" / ".join(HOUSEHOLD_NON_COMMON_CATEGORIES))
c4.metric("Différence", _fmt(summary["difference"]),
          delta=f"{summary['difference']:+,.2f} €" if summary["difference"] else None)
c5.metric(balance_label, balance_value, help="Solde réel relevé au dernier import du mois")

# ---------------------------------------------------------------------------
# Qui met quoi / qui dépense quoi
# ---------------------------------------------------------------------------
col_in, col_out = st.columns(2)
with col_in:
    st.markdown("**Qui met quoi**")
    contrib = contributions(month_df)
    if contrib.is_empty():
        st.caption("Aucune rentrée ce mois-ci.")
    else:
        st.dataframe(
            contrib.rename({"category": "Rentrée", "total": "Montant", "pct": "%"}).to_pandas(),
            hide_index=True, width="stretch",
            column_config={"Montant": st.column_config.NumberColumn(format="%.2f €"),
                           "%": st.column_config.NumberColumn(format="%.1f %%")},
        )
with col_out:
    st.markdown("**Qui a payé les dépenses communes**")
    payers = spending_by_payer(month_df)
    if payers.is_empty():
        st.caption("Aucune dépense commune ce mois-ci.")
    else:
        st.dataframe(
            payers.rename({"payer": "Payé par", "total": "Montant", "count": "Opérations"}).to_pandas(),
            hide_index=True, width="stretch",
            column_config={"Montant": st.column_config.NumberColumn(format="%.2f €")},
        )

st.markdown("**Dépenses communes par catégorie**")
breakdown = breakdown_by_category(common_expenses(month_df))
if breakdown.is_empty():
    st.caption("Aucune dépense commune ce mois-ci.")
else:
    fig = px.pie(breakdown.to_pandas(), values="total", names="category", hole=0.4)
    fig.update_traces(textinfo="percent+label", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Évolution
# ---------------------------------------------------------------------------
st.subheader("Évolution")
year_df = regular.filter(pl.col("date").dt.year() == year)
if year_df.is_empty():
    st.caption("Aucune opération sur l'année.")
else:
    monthly = aggregate_monthly_from_df(year_df)
    fig = px.bar(
        monthly.to_pandas(), x="month_label", y=["revenue", "expenses"], barmode="group",
        labels={"month_label": "", "value": "€", "variable": ""},
    )
    fig.for_each_trace(lambda t: t.update(name={"revenue": "Rentrées", "expenses": "Sorties"}[t.name]))
    st.plotly_chart(fig, use_container_width=True)

    if joint_account:
        balances = read_statement_balances(joint_account["id"])
        if balances.height >= 2:
            st.markdown("**Solde du compte commun**")
            st.line_chart(balances.to_pandas(), x="date", y="balance")

    tab_exp, tab_inc = st.tabs(["Sorties par catégorie et par mois", "Rentrées par catégorie et par mois"])
    for tab, direction in ((tab_exp, "expense"), (tab_inc, "income")):
        with tab:
            pivot = pivot_by_category_month(year_df, direction)
            if pivot.is_empty():
                st.caption("Rien sur l'année.")
            else:
                numeric = [c for c in pivot.columns if c != "category"]
                st.dataframe(
                    pivot.rename({"category": "Catégorie"}).to_pandas(),
                    hide_index=True, width="stretch",
                    column_config={c: st.column_config.NumberColumn(format="%.2f €") for c in numeric},
                )

st.divider()

# ---------------------------------------------------------------------------
# Opérations exceptionnelles
# ---------------------------------------------------------------------------
exceptional = exceptional_operations(household_df).sort("date", descending=True)
st.subheader(f"Opérations exceptionnelles ({exceptional.height})")
st.caption(
    "Hors budget courant (apport, caution, clôture de compte…). Décoche pour remettre une "
    "opération dans le budget."
)
if exceptional.is_empty():
    st.caption("Aucune.")
else:
    exc_rows = exceptional.to_dicts()
    edited = st.data_editor(
        pl.DataFrame({
            "id": [r["id"] for r in exc_rows],
            "Date": [r["date"] for r in exc_rows],
            "Libellé": [r["label"] for r in exc_rows],
            "Catégorie": [r["category"] or "" for r in exc_rows],
            "Montant": [r["amount"] for r in exc_rows],
            "Exceptionnel": [True] * len(exc_rows),
        }).to_pandas(),
        hide_index=True, width="stretch",
        disabled=["id", "Date", "Libellé", "Catégorie", "Montant"],
        column_config={"id": None, "Montant": st.column_config.NumberColumn(format="%.2f €")},
        key="foyer_exceptional",
    )
    if st.button("Enregistrer", key="foyer_exceptional_save"):
        updates = [
            {"id": r["id"], "is_exceptional": False}
            for r in edited.to_dict("records") if not r["Exceptionnel"]
        ]
        try:
            bulk_update_transaction_fields(updates)
            invalidate_cache()
            st.toast(f"{len(updates)} opération(s) remise(s) dans le budget.", icon="✅")
            st.rerun()
        except Exception as exc:
            st.error(f"Erreur : {exc}")
