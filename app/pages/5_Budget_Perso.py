"""Page Budget Personnel — transactions, récurrences, virements, vues mensuelle/globale."""

import calendar
from datetime import date

import plotly.express as px
import polars as pl
import streamlit as st

from app.components.auth import require_auth
from app.components.recurring_section import render_recurring_section
from app.components.transaction_table import render_editable_transactions
from app.components.transfer_section import render_transfer_section
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
from src.logic.categorizer import apply_rules, categorization_stats, get_pending_categorization
from src.logic.consolidated import personal_income_from_transfers, personal_savings_transfers
from src.logic.revenue import (
    _MONTH_LABELS,
    aggregate_monthly_from_df,
    monthly_benefice,
    pivot_by_category_month,
)
from src.services.db_reader import (
    invalidate_cache,
    read_accounts,
    read_categories,
    read_transactions,
)
from src.services.supabase import bulk_update_categories, fetch_categorization_rules

st.set_page_config(page_title="Budget Perso", page_icon="💰", layout="wide")
require_auth()
st.title("Budget Personnel")

_SAVINGS_CATEGORY = "Épargne"
_MONTHS_LIST: list[str] = [_MONTH_LABELS[m] for m in range(1, 13)]
_MONTHS_MAP: dict[str, int] = {v: k for k, v in _MONTH_LABELS.items()}


def _show_pivot(pivot: pl.DataFrame) -> None:
    """Affiche un tableau croisé avec formatage des colonnes numériques."""
    renamed = pivot.rename({"category": "Catégorie"})
    numeric_cols = [c for c in renamed.columns if c != "Catégorie"]
    col_cfg = {c: st.column_config.NumberColumn(format="%.2f €") for c in numeric_cols}
    st.dataframe(renamed.to_pandas(), width='stretch', hide_index=True, column_config=col_cfg)


tab_tx, tab_recurring, tab_transfer, tab_monthly, tab_global = st.tabs(
    ["🏷️ Transactions", "📅 Récurrences", "🔁 Virement", "📅 Vue mensuelle", "📊 Vue globale"]
)

# ---------------------------------------------------------------------------
# Onglet Transactions
# ---------------------------------------------------------------------------
with tab_tx:
    today = date.today()
    current_year = today.year

    col_y, col_m = st.columns(2)
    with col_y:
        tx_year: int = st.selectbox("Année", [current_year, current_year - 1], key="perso_tx_year")
    with col_m:
        tx_month_options: dict[str, int | None] = {"Tous": None}
        tx_month_options.update({_MONTH_LABELS[m]: m for m in range(1, 13)})
        # Le mois en cours par défaut (position today.month dans la liste,
        # puisque "Tous" occupe l'index 0) ; "Tous" reste sélectionnable.
        tx_default_month_idx = today.month if tx_year == current_year else 0
        tx_sel_label: str = st.selectbox(
            "Mois", list(tx_month_options.keys()), index=tx_default_month_idx, key="perso_tx_month"
        )
    tx_sel_month = tx_month_options[tx_sel_label]

    try:
        tx_df = read_transactions(business_id=str(BusinessId.PERSONAL), year=tx_year, month=tx_sel_month)
    except Exception as exc:
        st.error(f"Impossible de charger les transactions : {exc}")
        tx_df = pl.DataFrame()

    perso_accounts_df = read_accounts(owner=str(BusinessId.PERSONAL))
    perso_account_options = {
        f"{a['name']} ({a.get('institution', '?')})": a["id"]
        for a in (perso_accounts_df.sort("name").to_dicts() if not perso_accounts_df.is_empty() else [])
    }

    cat_df = read_categories(business_id=str(BusinessId.PERSONAL))
    tx_categories_by_direction = {
        "income": sorted(cat_df.filter(pl.col("direction") == "income")["name"].to_list())
        if not cat_df.is_empty() else [],
        "expense": sorted(cat_df.filter(pl.col("direction") == "expense")["name"].to_list())
        if not cat_df.is_empty() else [],
    }

    if not tx_df.is_empty():
        stats = categorization_stats(tx_df)
        if stats["pending"] > 0:
            col_stat, col_auto = st.columns([3, 1])
            with col_stat:
                st.caption(
                    f"{stats['pending']} transaction(s) sans catégorie sur {stats['total']} "
                    f"({stats['coverage_pct']:.0f} % couvert)."
                )
            with col_auto:
                if st.button("⚡ Catégoriser auto", key="perso_auto_cat", width='stretch'):
                    rules = fetch_categorization_rules()
                    pending_df = get_pending_categorization(tx_df)
                    auto_df = apply_rules(pending_df, rules)
                    updates = [
                        {"id": row["id"], "category": row["category"]}
                        for row in auto_df.iter_rows(named=True)
                        if row.get("category")
                    ]
                    if updates:
                        bulk_update_categories(updates)
                        invalidate_cache()
                        st.toast(f"{len(updates)} transaction(s) catégorisée(s) ✅", icon="✅")
                        st.rerun()
                    else:
                        st.toast("Aucune règle ne correspond.", icon="ℹ️")

    render_editable_transactions(
        tx_df,
        business_id=str(BusinessId.PERSONAL),
        key="perso_tx",
        categories_by_direction=tx_categories_by_direction,
        account_options=perso_account_options,
    )

# ---------------------------------------------------------------------------
# Onglet Récurrences
# ---------------------------------------------------------------------------
with tab_recurring:
    st.caption(
        "Définis un modèle une fois (loyer, abonnement, salaire...), "
        "puis valide-le chaque mois en un clic au lieu de tout retaper."
    )
    render_recurring_section(key_prefix="budget_perso", business_id_filter=str(BusinessId.PERSONAL))

# ---------------------------------------------------------------------------
# Onglet Virement
# ---------------------------------------------------------------------------
with tab_transfer:
    render_transfer_section(key_prefix="budget_perso")

# ---------------------------------------------------------------------------
# Onglet Vue mensuelle
# ---------------------------------------------------------------------------
with tab_monthly:
    with st.sidebar:
        st.subheader("Filtres — Vue mensuelle")
        current_year_m = date.today().year
        current_month_m = date.today().month
        year = st.selectbox("Année", [current_year_m, current_year_m - 1], key="year_perso")
        month_labels = list(_MONTH_LABELS.values())
        default_month_idx = current_month_m - 1
        selected_month_label = st.selectbox(
            "Mois", month_labels, index=default_month_idx, key="month_perso"
        )
        selected_month = month_labels.index(selected_month_label) + 1

    # Mois N-1 (pour l'affichage du libellé uniquement)
    prev_month = selected_month - 1 if selected_month > 1 else 12
    prev_year = year if selected_month > 1 else year - 1

    try:
        df = read_transactions(
            business_id=str(BusinessId.PERSONAL), year=year, month=selected_month,
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
    # Virements Compte perso/commun → Livret épargne : un simple mouvement interne (ne
    # change pas le patrimoine total, voir personal_savings_transfers), mais qui rend cet
    # argent indisponible pour le reste — il doit donc réduire le solde cumulé "Reste"/
    # "Total fin du mois" exactement comme une dépense, tout en restant affiché à part
    # dans la ligne "Épargne" plutôt que dans "Dépenses".
    savings_transfer_all = personal_savings_transfers(all_tx_with_transfers, accounts_df)
    savings_transfer_monthly = (
        savings_transfer_all.group_by(["year", "month_num"]).agg(pl.col("amount").sum().alias("montant"))
        if not savings_transfer_all.is_empty()
        else pl.DataFrame(schema={"year": pl.Int32, "month_num": pl.Int32, "montant": pl.Float64})
    )
    savings_transfer_as_negative_benefice = savings_transfer_monthly.select(
        "year", "month_num", (-pl.col("montant")).alias("benefice")
    )
    combined_extra_monthly = (
        pl.concat(
            [phi_monthly, transfer_income_monthly, savings_transfer_as_negative_benefice],
            how="diagonal_relaxed",
        )
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
    savings_category_month = _savings_amount(df)
    savings_transfer_month = _amount_for_month(savings_transfer_monthly, year, selected_month, "montant")
    # Seule la part "catégorie Épargne" (une dépense normale) est déjà comptée dans
    # summary["expenses"] : on ne retranche qu'elle, pas la part "virement" qui n'y
    # a jamais été incluse (les virements sont exclus de summary par construction).
    savings = savings_category_month + savings_transfer_month
    expenses_excl_savings = summary["expenses"] - savings_category_month
    adjusted_income = summary["income"] + phi_benefice_month + transfer_income_month
    # savings_transfer_month réduit la différence (argent parti sur le Livret, donc plus
    # disponible) sans être compté dans "Dépenses" (déjà affiché séparément ci-dessus).
    difference = adjusted_income - summary["expenses"] - savings_transfer_month

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
    c3.caption(f"dont {savings_transfer_month:,.2f} € viré vers le Livret")
    c4.metric("Différence", f"{difference:,.2f} €", delta=f"{difference:+,.2f} €" if difference != 0 else None)
    c5.metric(
        f"Reste {_MONTH_LABELS[prev_month]} {prev_year}",
        f"{reste_n1:,.2f} €",
    )
    c6.metric("Total fin du mois", f"{total_fin_mois:,.2f} €")

    st.divider()

    st.subheader("Répartition des dépenses")
    breakdown = breakdown_by_category(df)
    if not breakdown.is_empty():
        fig = px.pie(
            breakdown.head(10).to_pandas(),
            values="total",
            names="category",
            hole=0.4,
        )
        fig.update_traces(textinfo="percent+label", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucune dépense catégorisée sur la période.")

# ---------------------------------------------------------------------------
# Onglet Vue globale
# ---------------------------------------------------------------------------
with tab_global:
    current_year_g = date.today().year

    period_type: str = st.radio(
        "Période", ["Année complète", "Période personnalisée"], horizontal=True, key="perso_gv_period_type",
    )

    if period_type == "Année complète":
        year_g: int = st.selectbox("Année", [current_year_g, current_year_g - 1], key="perso_gv_year")
        date_from = date(year_g, 1, 1)
        date_to = date(year_g, 12, 31)
    else:
        c1g, c2g, c3g, c4g = st.columns(4)
        with c1g:
            sm_label: str = st.selectbox("Mois début", _MONTHS_LIST, key="perso_gv_sm")
        with c2g:
            sy: int = st.selectbox("Année début", [current_year_g, current_year_g - 1], key="perso_gv_sy")
        with c3g:
            em_label: str = st.selectbox(
                "Mois fin", _MONTHS_LIST, index=len(_MONTHS_LIST) - 1, key="perso_gv_em"
            )
        with c4g:
            ey: int = st.selectbox("Année fin", [current_year_g, current_year_g - 1], key="perso_gv_ey")
        sm, em = _MONTHS_MAP[sm_label], _MONTHS_MAP[em_label]
        date_from = date(sy, sm, 1)
        date_to = date(ey, em, calendar.monthrange(ey, em)[1])

    try:
        df_g = read_transactions(business_id=str(BusinessId.PERSONAL), date_from=date_from, date_to=date_to)
    except Exception as exc:
        st.error(f"Impossible de charger les transactions : {exc}")
        df_g = pl.DataFrame()

    if df_g.is_empty():
        st.info("Aucune transaction sur la période sélectionnée.")
    else:
        st.subheader("Dépenses par catégorie et par mois")
        exp_pivot = pivot_by_category_month(df_g, "expense")
        if exp_pivot.is_empty():
            st.info("Aucune dépense sur la période.")
        else:
            _show_pivot(exp_pivot)

        st.divider()

        st.subheader("Revenus par catégorie et par mois")
        rev_pivot = pivot_by_category_month(df_g, "income")
        if rev_pivot.is_empty():
            st.info("Aucun revenu sur la période.")
        else:
            _show_pivot(rev_pivot)

        st.divider()

        st.subheader("Évolution revenus / dépenses")
        monthly_g = aggregate_monthly_from_df(df_g)
        if monthly_g["revenue"].sum() > 0 or monthly_g["expenses"].sum() > 0:
            fig_g = px.line(
                monthly_g.to_pandas(),
                x="month_label",
                y=["revenue", "expenses"],
                labels={"month_label": "Mois", "value": "€", "variable": ""},
                color_discrete_map={"revenue": "#2ecc71", "expenses": "#e74c3c"},
                markers=True,
            )
            fig_g.update_layout(legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig_g, width='stretch')
        else:
            st.info("Pas de données pour le graphique.")
