"""Page Transactions — toutes les opérations : rechercher, corriger, déplacer d'un budget à l'autre."""

from datetime import date
from typing import Any

import polars as pl
import streamlit as st

from app.components.auth import require_auth
from app.components.help import page_title, section_title
from src.logic.categories import SCOPE_LABELS
from src.logic.transactions_explorer import (
    NO_CATEGORY,
    PERIODS,
    filter_transactions,
    period_bounds,
    plan_bulk,
    plan_delete,
    plan_edits,
    totals,
)
from src.services.db_reader import invalidate_cache, read_categories, read_transactions
from src.services.supabase import (
    bulk_update_transaction_fields,
    delete_transactions,
    delete_transfer,
    fetch_accounts,
)

st.set_page_config(page_title="Transactions", page_icon="🔎", layout="wide")
require_auth()
page_title("Transactions", "transactions")
st.caption(
    "Toutes tes opérations, tous budgets confondus. Cherche, corrige un libellé ou une catégorie, "
    "déplace une opération d'un budget à l'autre, ou applique un changement à plusieurs lignes d'un coup."
)

_MESSAGES_KEY = "_transactions_messages"
_VERSION_KEY = "_transactions_version"
_MAX_ROWS = 300
_BUDGET_BY_LABEL = {label: key for key, label in SCOPE_LABELS.items()}
_UNCHANGED = "(inchangé)"

for kind, text in st.session_state.pop(_MESSAGES_KEY, []):
    getattr(st, kind)(text)
version = st.session_state.setdefault(_VERSION_KEY, 0)


def _flash(messages: list[tuple[str, str]]) -> None:
    """Garde des messages pour après le rechargement de la page, et remet les tableaux à zéro."""
    st.session_state[_MESSAGES_KEY] = messages
    st.session_state[_VERSION_KEY] = version + 1
    invalidate_cache()
    st.rerun()


def _clean(value: Any) -> Any:
    if value is None or value == "" or (isinstance(value, float) and value != value):
        return None
    return value


try:
    all_df = read_transactions(include_transfers=True)
    accounts = fetch_accounts()
    categories_df = read_categories()
except Exception as exc:
    st.error(f"Impossible de charger les données : {exc}")
    st.stop()

if all_df.is_empty():
    st.info("Aucune opération pour l'instant : importe un relevé depuis la page Sync.")
    st.stop()

account_names = {a["id"]: a["name"] for a in accounts}
categories: dict[str, dict[str, set[str]]] = {}
for cat in categories_df.to_dicts() if not categories_df.is_empty() else []:
    categories.setdefault(cat["business_id"], {}).setdefault(cat["direction"], set()).add(cat["name"])
category_names = sorted(categories_df["name"].unique().to_list()) if not categories_df.is_empty() else []

# ---------------------------------------------------------------------------
# Filtres
# ---------------------------------------------------------------------------
col_period, col_budget, col_account = st.columns([2, 3, 3])
period = col_period.selectbox("Période", PERIODS, index=0, key="tx_period")
custom_range = None
if period == "Choisir…":
    picked = col_period.date_input("Du … au", value=(date.today().replace(day=1), date.today()), key="tx_range")
    if isinstance(picked, tuple) and len(picked) == 2:
        custom_range = picked
date_from, date_to = period_bounds(period, date.today(), custom_range)
budgets = col_budget.multiselect(
    "Budgets", list(SCOPE_LABELS), default=list(SCOPE_LABELS), format_func=SCOPE_LABELS.get, key="tx_budgets"
)
account_ids = col_account.multiselect(
    "Comptes", list(account_names), default=[], format_func=account_names.get,
    placeholder="Tous les comptes", key="tx_accounts",
)

col_text, col_dir, col_cat, col_min = st.columns([3, 2, 3, 2])
text = col_text.text_input("Recherche", placeholder="libellé, commerçant… (sans accents ni majuscules)", key="tx_text")
direction_label = col_dir.selectbox("Sens", ["Tous", "Dépenses", "Revenus"], key="tx_direction")
chosen_categories = col_cat.multiselect(
    "Catégories", [NO_CATEGORY, *category_names], default=[], placeholder="Toutes", key="tx_categories"
)
min_amount = col_min.number_input("Montant min (€)", min_value=0.0, value=0.0, step=10.0, key="tx_min")

col_t1, col_t2, col_t3 = st.columns(3)
only_review = col_t1.toggle("À vérifier seulement", key="tx_review")
only_exceptional = col_t2.toggle("Exceptionnelles seulement", key="tx_exceptional")
include_transfers = col_t3.toggle("Inclure les virements internes", key="tx_transfers")

filtered = filter_transactions(
    all_df,
    date_from=date_from,
    date_to=date_to,
    businesses=budgets,
    account_ids=account_ids,
    categories=chosen_categories,
    text=text,
    direction={"Dépenses": "expense", "Revenus": "income"}.get(direction_label),
    min_amount=min_amount,
    only_review=only_review,
    only_exceptional=only_exceptional,
    include_transfers=include_transfers,
)

summary = totals(filtered)
col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Opérations", summary["count"])
col_m2.metric("Rentrées", f"{summary['income']:,.2f} €".replace(",", " "))
col_m3.metric("Dépenses", f"{summary['expenses']:,.2f} €".replace(",", " "))

if filtered.is_empty():
    st.info("Aucune opération ne correspond à ces filtres.")
    st.stop()

shown = filtered.head(_MAX_ROWS)
if filtered.height > _MAX_ROWS:
    st.caption(f"Les {_MAX_ROWS} plus récentes sur {filtered.height} sont affichées : affine les filtres pour voir les autres.")
rows = shown.to_dicts()

st.download_button(
    "⬇️ Exporter la recherche (CSV)",
    data=filtered.select(["date", "label", "raw_label", "amount", "business_id", "category", "account_id"])
    .write_csv().encode("utf-8"),
    file_name=f"transactions-{date.today().isoformat()}.csv",
    mime="text/csv",
    key="tx_export",
)

# ---------------------------------------------------------------------------
# Tableau
# ---------------------------------------------------------------------------
def _status(row: dict[str, Any]) -> str:
    if row.get("is_transfer"):
        return "🔁"
    return "🔎" if row.get("needs_review") else ""


editor_df = pl.DataFrame({
    "id": [r["id"] for r in rows],
    "Sél.": [False] * len(rows),
    "": [_status(r) for r in rows],
    "Date": [r["date"] for r in rows],
    "Compte": [account_names.get(r["account_id"], "—") for r in rows],
    "Libellé": [r["label"] for r in rows],
    "Montant": [r["amount"] for r in rows],
    "Budget": [SCOPE_LABELS.get(r["business_id"], r["business_id"]) for r in rows],
    "Catégorie": [r.get("category") or "" for r in rows],
    "Exceptionnel": [bool(r.get("is_exceptional")) for r in rows],
})
edited = st.data_editor(
    editor_df.to_pandas(),
    hide_index=True,
    width="stretch",
    disabled=["id", "", "Date", "Compte", "Montant"],
    column_config={
        "id": None,
        "Sél.": st.column_config.CheckboxColumn(help="Coche des lignes pour leur appliquer une action groupée"),
        "": st.column_config.TextColumn(width="small", help="🔁 virement interne · 🔎 à vérifier"),
        "Montant": st.column_config.NumberColumn(format="%.2f €"),
        "Budget": st.column_config.SelectboxColumn(options=list(SCOPE_LABELS.values()), required=True),
        "Catégorie": st.column_config.SelectboxColumn(options=["", *category_names]),
        "Exceptionnel": st.column_config.CheckboxColumn(),
    },
    key=f"tx_editor_v{version}",
)
records = [{k: _clean(v) for k, v in rec.items()} for rec in edited.to_dict("records")]

if st.button("💾 Enregistrer les modifications", type="primary", key="tx_save"):
    for rec in records:
        rec["Budget"] = _BUDGET_BY_LABEL.get(rec["Budget"])
    plan = plan_edits(rows, records, categories)
    try:
        bulk_update_transaction_fields(plan.updates)
        _flash([("warning", e) for e in plan.errors] + [("success", f"{len(plan.updates)} opération(s) modifiée(s).")])
    except Exception as exc:
        st.error(f"Erreur : {exc}")

# ---------------------------------------------------------------------------
# Actions sur la sélection
# ---------------------------------------------------------------------------
selected_ids = [rec["id"] for rec in records if rec.get("Sél.")]
selected_rows = [r for r in rows if r["id"] in set(selected_ids)]

st.divider()
section_title(f"Actions sur la sélection ({len(selected_rows)})", "transactions_actions")
st.caption("Coche des lignes dans la colonne « Sél. » du tableau, puis choisis ce qu'il faut leur appliquer. "
           "Enregistre d'abord tes modifications de cellules : elles ne sont pas incluses.")

if not selected_rows:
    st.info("Aucune ligne sélectionnée.")
else:
    col_b, col_c, col_e = st.columns(3)
    bulk_budget = col_b.selectbox("Budget", [_UNCHANGED, *SCOPE_LABELS.values()], key="tx_bulk_budget")
    bulk_category = col_c.selectbox("Catégorie", [_UNCHANGED, *category_names], key="tx_bulk_category")
    bulk_exceptional = col_e.selectbox("Exceptionnel", [_UNCHANGED, "Oui", "Non"], key="tx_bulk_exceptional")

    if st.button(f"Appliquer aux {len(selected_rows)} ligne(s)", key="tx_bulk_apply"):
        plan = plan_bulk(
            selected_rows,
            categories,
            business_id=_BUDGET_BY_LABEL.get(bulk_budget),
            category=None if bulk_category == _UNCHANGED else bulk_category,
            exceptional={"Oui": True, "Non": False}.get(bulk_exceptional),
        )
        try:
            bulk_update_transaction_fields(plan.updates)
            _flash([("warning", e) for e in plan.errors] + [
                ("success", f"{len(plan.updates)} opération(s) modifiée(s) sur {len(selected_rows)} sélectionnée(s).")
            ])
        except Exception as exc:
            st.error(f"Erreur : {exc}")

    st.markdown("**Supprimer la sélection**")
    ids, groups, n_imported = plan_delete(selected_rows)
    if n_imported:
        st.warning(
            f"{n_imported} de ces opérations viennent d'un relevé : elles **réapparaîtront** si tu "
            "dépose de nouveau le même relevé, et le contrôle de solde signalera un écart. "
            "Pour les sortir des budgets sans les supprimer, coche plutôt « Exceptionnel »."
        )
    if groups:
        st.caption(f"{len(groups)} virement(s) interne(s) : leurs deux écritures seront supprimées.")
    if st.checkbox(f"Je confirme la suppression de ces {len(selected_rows)} ligne(s)", key="tx_confirm_delete"):
        if st.button("🗑️ Supprimer définitivement", key="tx_delete"):
            try:
                delete_transactions(ids)
                for group_id in groups:
                    delete_transfer(group_id)
                _flash([("success", f"{len(selected_rows)} opération(s) supprimée(s).")])
            except Exception as exc:
                st.error(f"Erreur : {exc}")
