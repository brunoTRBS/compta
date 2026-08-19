"""Page Budget Personnel — dépenses, épargne, catégorisation."""

from datetime import date

import plotly.express as px
import polars as pl
import streamlit as st

from app.components.auth import require_auth
from app.components.quick_entry import render_quick_entry_form
from src.config import (
    PERSO_OPENING_BALANCE,
    PERSO_OPENING_BALANCE_MONTH,
    PERSO_OPENING_BALANCE_YEAR,
    BusinessId,
)
from src.logic.budget import (
    breakdown_by_category,
    compute_budget_summary,
    compute_cumulative_balance,
)
from src.logic.consolidated import personal_income_from_transfers
from src.logic.revenue import monthly_benefice
from src.services.db_reader import read_accounts, read_transactions

st.set_page_config(page_title="Budget Perso", page_icon="💰", layout="wide")
require_auth()
st.title("Budget Personnel")

render_quick_entry_form(str(BusinessId.PERSONAL), key_prefix="budget_perso")

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
# Mois N-1 (pour l'affichage du libellé uniquement)
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
    # Historique complet : nécessaire pour calculer un vrai solde cumulé
    # (et non juste "mois précédent - mois actuel").
    df_all_personal = read_transactions(business_id=str(BusinessId.PERSONAL))
    # Le bénéfice Phi Rising compte comme un revenu perso (micro-entreprise : pas de
    # séparation légale entre bénéfice pro et patrimoine perso). Booth in Lyon n'est
    # volontairement jamais inclus ici : cet argent est mis de côté, pas disponible.
    phi_all_df = read_transactions(business_id=str(BusinessId.PHI_RISING))
    # Tout l'historique, toutes activités, virements inclus : pour repérer les virements
    # Booth in Lyon/Épargne → Perso à traiter comme un revenu (voir plus bas).
    all_tx_with_transfers = read_transactions(include_transfers=True)
    accounts_df = read_accounts()
except Exception as exc:
    st.error(f"Impossible de charger les transactions : {exc}")
    st.stop()

summary = compute_budget_summary(df, year, selected_month)
phi_monthly = monthly_benefice(phi_all_df, BusinessId.PHI_RISING)

# Virements dont la source est Booth in Lyon ou un compte d'épargne (le Livret) et la
# destination un compte Perso : cet argent devient réellement disponible, donc compté
# comme un revenu perso. Les virements depuis Phi Rising restent exclus (déjà comptés
# via son bénéfice ci-dessus) et les mouvements perso-à-perso restent de simples virements.
transfer_income_all = personal_income_from_transfers(all_tx_with_transfers, accounts_df)
transfer_income_monthly = (
    transfer_income_all.group_by(["year", "month_num"]).agg(pl.col("amount").sum().alias("benefice"))
    if not transfer_income_all.is_empty()
    else pl.DataFrame(schema={"year": pl.Int32, "month_num": pl.Int32, "benefice": pl.Float64})
)
combined_extra_monthly = (
    pl.concat([phi_monthly, transfer_income_monthly], how="diagonal_relaxed")
    .group_by(["year", "month_num"])
    .agg(pl.col("benefice").sum())
)

def _amount_for_month(monthly_df: pl.DataFrame, target_year: int, target_month: int, col: str) -> float:
    row = monthly_df.filter(
        (pl.col("year") == target_year) & (pl.col("month_num") == target_month)
    )
    return float(row[col][0]) if not row.is_empty() else 0.0

def _savings_amount(frame: pl.DataFrame) -> float:
    filtered = frame.filter(
        (pl.col("amount") < 0) & (pl.col("category") == _SAVINGS_CATEGORY)
    )
    return abs(float(filtered["amount"].sum() or 0.0))

phi_benefice_month = _amount_for_month(phi_monthly, year, selected_month, "benefice")
transfer_income_month = _amount_for_month(transfer_income_monthly, year, selected_month, "benefice")
savings = _savings_amount(df)
expenses_excl_savings = summary["expenses"] - savings
adjusted_income = summary["income"] + phi_benefice_month + transfer_income_month
difference = adjusted_income - summary["expenses"]

# Solde d'ouverture : le suivi a commencé en mai 2025, avec un reste réel non nul fin
# avril 2025 — ne s'applique donc qu'à partir du premier mois suivi.
opening = (
    float(PERSO_OPENING_BALANCE)
    if (year, selected_month) >= (PERSO_OPENING_BALANCE_YEAR, PERSO_OPENING_BALANCE_MONTH)
    else 0.0
)
reste_n1 = compute_cumulative_balance(
    df_all_personal, year, selected_month,
    extra_monthly_benefice=combined_extra_monthly, opening_balance=opening,
)
total_fin_mois = reste_n1 + difference

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
period_label = f"{_MONTH_LABELS[selected_month]} {year}"
st.subheader(f"Résumé {period_label}")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Revenus", f"{adjusted_income:,.2f} €")
c1.caption(
    f"dont {phi_benefice_month:,.2f} € bénéfice Phi Rising, "
    f"{transfer_income_month:,.2f} € virements reçus"
)
c2.metric("Dépenses", f"{expenses_excl_savings:,.2f} €")
c3.metric("Épargne", f"{savings:,.2f} €")
c4.metric("Différence", f"{difference:,.2f} €", delta=f"{difference:+,.2f} €" if difference != 0 else None)
c5.metric(
    f"Reste {_MONTH_LABELS[prev_month]} {prev_year}",
    f"{reste_n1:,.2f} €",
)
c6.metric("Total fin du mois", f"{total_fin_mois:,.2f} €")

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
    available_cols = [c for c in ["date", "label", "amount", "category", "note"] if c in df.columns]

    def _show_movements(direction_df: pl.DataFrame, empty_message: str) -> None:
        if direction_df.is_empty():
            st.info(empty_message)
            return
        st.dataframe(
            direction_df.select(available_cols).with_columns(pl.col("amount").abs()),
            use_container_width=True,
            hide_index=True,
            column_config={
                "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                "label": st.column_config.TextColumn("Libellé"),
                "amount": st.column_config.NumberColumn("Montant (€)", format="%.2f €"),
                "category": st.column_config.TextColumn("Catégorie"),
                "note": st.column_config.TextColumn("Note"),
            },
        )

    tab_expenses, tab_income = st.tabs(["↓ Dépenses du mois", "↑ Revenus du mois"])
    with tab_expenses:
        _show_movements(
            df.filter(pl.col("amount") < 0).sort("date", descending=True),
            "Aucune dépense sur la période.",
        )
    with tab_income:
        transfer_income_month_df = transfer_income_all.filter(
            (pl.col("year") == year) & (pl.col("month_num") == selected_month)
        )
        income_extra_rows = transfer_income_month_df.select(["date", "label", "amount"]).with_columns(
            pl.lit("Virement reçu (Booth/Épargne)").alias("category")
        )
        income_rows = pl.concat(
            [
                df.filter(pl.col("amount") > 0).select(
                    [c for c in ["date", "label", "amount", "category"] if c in df.columns]
                ),
                income_extra_rows,
            ],
            how="diagonal_relaxed",
        ).sort("date", descending=True)
        _show_movements(income_rows, "Aucun revenu sur la période.")
