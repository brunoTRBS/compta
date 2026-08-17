"""Formulaire compact d'ajout de transaction, intégré directement sur les pages
d'activité pour ajouter et visualiser au même endroit (pas de détour par Saisie)."""

from datetime import date

import polars as pl
import streamlit as st

from src.config import TransactionSource
from src.services.db_reader import invalidate_cache, read_accounts, read_categories
from src.services.supabase import insert_transaction


def render_quick_entry_form(business_id: str, key_prefix: str) -> None:
    """Affiche un formulaire compact de saisie manuelle pour une activité donnée.

    Args:
        business_id: activité concernée (phi_rising / booth_in_lyon / personal).
        key_prefix: préfixe unique pour les clés de widgets (évite les conflits
            si le composant est utilisé sur plusieurs pages).
    """
    accounts_df = read_accounts(owner=business_id)
    accounts = accounts_df.sort("name").to_dicts() if not accounts_df.is_empty() else []
    account_options = {f"{a['name']} ({a.get('institution', '?')})": a["id"] for a in accounts}

    cats_df = read_categories(business_id=business_id)

    with st.expander("➕ Ajouter une transaction", expanded=False):
        if not account_options:
            st.info("Aucun compte configuré pour cette activité.")
            return

        col_account, col_type = st.columns(2)
        if len(account_options) > 1:
            account_label = col_account.selectbox(
                "Compte", list(account_options.keys()), key=f"{key_prefix}_qe_account"
            )
        else:
            account_label = next(iter(account_options))
            col_account.caption(f"Compte : {account_label}")

        tx_type = col_type.radio(
            "Type", ["Dépense", "Revenu"], horizontal=True, key=f"{key_prefix}_qe_type"
        )
        direction = "expense" if tx_type == "Dépense" else "income"

        filtered_cats = (
            sorted(cats_df.filter(pl.col("direction") == direction)["name"].to_list())
            if not cats_df.is_empty() else []
        )

        with st.form(f"{key_prefix}_qe_form", clear_on_submit=True):
            col_date, col_amount = st.columns(2)
            tx_date = col_date.date_input("Date", value=date.today(), key=f"{key_prefix}_qe_date")
            tx_amount = col_amount.number_input(
                "Montant (€)", min_value=0.0, step=0.01, format="%.2f", key=f"{key_prefix}_qe_amount"
            )
            tx_label = st.text_input("Libellé", max_chars=200, key=f"{key_prefix}_qe_label")
            tx_category = st.selectbox(
                "Catégorie", ["— Laisser vide —"] + filtered_cats, key=f"{key_prefix}_qe_category"
            )
            submitted = st.form_submit_button("Ajouter", width='stretch')

        if submitted:
            if not tx_label.strip():
                st.error("Le libellé est obligatoire.")
            else:
                signed_amount = float(tx_amount) if direction == "income" else -float(tx_amount)
                payload: dict = {
                    "date": tx_date.isoformat(),
                    "amount": signed_amount,
                    "label": tx_label.strip(),
                    "source": str(TransactionSource.MANUAL),
                    "business_id": business_id,
                    "account_id": account_options.get(account_label),
                    "category": tx_category if tx_category != "— Laisser vide —" else None,
                    "notes": None,
                }
                try:
                    insert_transaction(payload)
                    invalidate_cache()
                    st.toast(f"Transaction « {tx_label.strip()} » ajoutée ✅", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Erreur lors de l'ajout : {exc}")
