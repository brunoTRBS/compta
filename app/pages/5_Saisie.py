"""Page Saisie & Corrections — ajout manuel, file d'attente, édition complète."""

from datetime import date

import polars as pl
import streamlit as st

from src.config import BusinessId, TransactionSource
from src.logic.categorizer import apply_rules, categorization_stats, get_pending_categorization
from src.services.db_reader import invalidate_cache, read_categories, read_transactions
from src.services.supabase import (
    bulk_update_categories,
    delete_transaction,
    fetch_categorization_rules,
    insert_transaction,
    update_transaction,
)
from app.components.auth import require_auth
from app.components.transaction_table import render_transaction_table

st.set_page_config(page_title="Saisie & Corrections", page_icon="✏️", layout="wide")
require_auth()
st.title("Saisie & Corrections")

_BUSINESS_LABELS = {
    "Phi Rising": str(BusinessId.PHI_RISING),
    "Booth in Lyon": str(BusinessId.BOOTH_IN_LYON),
    "Perso": str(BusinessId.PERSONAL),
}

# Catégories chargées une fois pour toute la page
_all_cats_df = read_categories()
_all_category_names = sorted(_all_cats_df["name"].to_list()) if not _all_cats_df.is_empty() else []
_cats_by_biz: dict[str, list[str]] = {
    biz_id: sorted(
        _all_cats_df.filter(pl.col("business_id") == biz_id)["name"].to_list()
    )
    for biz_id in [str(BusinessId.PHI_RISING), str(BusinessId.BOOTH_IN_LYON), str(BusinessId.PERSONAL)]
}
_cats_by_biz_dir: dict[tuple[str, str], list[str]] = {
    (biz_id, direction): sorted(
        _all_cats_df.filter(
            (pl.col("business_id") == biz_id) & (pl.col("direction") == direction)
        )["name"].to_list()
    )
    for biz_id in [str(BusinessId.PHI_RISING), str(BusinessId.BOOTH_IN_LYON), str(BusinessId.PERSONAL)]
    for direction in ["income", "expense"]
} if not _all_cats_df.is_empty() else {}

tab_new, tab_pending, tab_edit = st.tabs(
    ["➕ Nouvelle transaction", "⏳ En attente de catégorisation", "✏️ Corriger des transactions"]
)

# ---------------------------------------------------------------------------
# Onglet 1 — Saisie manuelle
# ---------------------------------------------------------------------------
with tab_new:
    st.subheader("Ajouter une transaction manuelle")
    st.caption("Idéal pour les paiements en espèces ou les opérations non importées.")

    # Hors formulaire : réagit immédiatement pour filtrer les catégories
    col_biz, col_type = st.columns(2)
    tx_business_label = col_biz.selectbox("Activité", list(_BUSINESS_LABELS.keys()), key="new_tx_biz")
    tx_type = col_type.radio("Type", ["Dépense", "Revenu"], horizontal=True, key="new_tx_type")

    tx_biz_id = _BUSINESS_LABELS[tx_business_label]
    tx_direction = "expense" if tx_type == "Dépense" else "income"
    filtered_cats = _cats_by_biz_dir.get((tx_biz_id, tx_direction), [])

    with st.form("form_new_transaction", clear_on_submit=True):
        col_date, col_amount = st.columns(2)
        tx_date = col_date.date_input("Date", value=date.today())
        tx_amount = col_amount.number_input(
            "Montant (€)",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            help="Saisissez toujours un montant positif.",
        )

        tx_label = st.text_input("Libellé", max_chars=200, placeholder="Ex : Courses marché")

        tx_category = st.selectbox(
            "Catégorie",
            ["— Laisser vide —"] + filtered_cats,
        )
        tx_notes = st.text_area("Notes (optionnel)", height=68, max_chars=500)

        submitted = st.form_submit_button("Ajouter la transaction", width='stretch')

    if submitted:
        if not tx_label.strip():
            st.error("Le libellé est obligatoire.")
        else:
            signed_amount = float(tx_amount) if tx_direction == "income" else -float(tx_amount)
            payload: dict = {
                "date": tx_date.isoformat(),
                "amount": signed_amount,
                "label": tx_label.strip(),
                "source": str(TransactionSource.MANUAL),
                "business_id": tx_biz_id,
                "category": tx_category if tx_category != "— Laisser vide —" else None,
                "notes": tx_notes.strip() or None,
            }
            try:
                insert_transaction(payload)
                invalidate_cache()
                st.toast(f"Transaction « {tx_label.strip()} » ajoutée ✅", icon="✅")
            except Exception as exc:
                st.error(f"Erreur lors de l'ajout : {exc}")

# ---------------------------------------------------------------------------
# Onglet 2 — File des transactions en attente
# ---------------------------------------------------------------------------
with tab_pending:
    st.subheader("Transactions sans catégorie")

    # Sélecteur d'activité pour limiter le volume
    with st.sidebar:
        st.subheader("Filtres — En attente")
        pending_biz_label = st.selectbox(
            "Activité",
            ["Toutes"] + list(_BUSINESS_LABELS.keys()),
            key="pending_biz",
        )
        pending_year = st.selectbox(
            "Année",
            [date.today().year, date.today().year - 1],
            key="pending_year",
        )

    pending_biz_id = _BUSINESS_LABELS.get(pending_biz_label)

    try:
        df_all = read_transactions(business_id=pending_biz_id, year=pending_year)
    except Exception as exc:
        st.error(f"Impossible de charger les transactions : {exc}")
        df_all = pl.DataFrame()

    if not df_all.is_empty():
        stats = categorization_stats(df_all)
        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("Transactions total", stats["total"])
        sc2.metric("Couverture", f"{stats['coverage_pct']:.0f} %")
        sc3.metric("En attente", stats["pending"])

        pending_df = get_pending_categorization(df_all)

        if not pending_df.is_empty():
            col_auto, col_info = st.columns([1, 3])
            with col_auto:
                if st.button("⚡ Catégoriser automatiquement", width='stretch'):
                    rules = fetch_categorization_rules()
                    auto_df = apply_rules(pending_df, rules)
                    updates = [
                        {"id": row["id"], "category": row["category"]}
                        for row in auto_df.iter_rows(named=True)
                        if row.get("category")
                    ]
                    if updates:
                        bulk_update_categories(updates)
                        invalidate_cache()
                        st.toast(f"{len(updates)} transaction(s) catégorisée(s).", icon="✅")
                        st.rerun()
                    else:
                        st.toast("Aucune règle ne correspond.", icon="ℹ️")
            with col_info:
                st.caption(
                    f"{len(pending_df)} transaction(s) à catégoriser — "
                    "éditez la colonne Catégorie puis cliquez Sauvegarder."
                )

            def _save_pending(updates: list[dict]) -> None:
                bulk_update_categories(updates)
                invalidate_cache()

            pending_cats = _cats_by_biz.get(pending_biz_id or "", _all_category_names)
            render_transaction_table(pending_df, key="pending_queue", categories=pending_cats, on_save=_save_pending)
        else:
            st.success("✅ Toutes les transactions sont catégorisées.")
    else:
        st.info("Aucune transaction trouvée pour cette période.")

# ---------------------------------------------------------------------------
# Onglet 3 — Correction complète
# ---------------------------------------------------------------------------
with tab_edit:
    st.subheader("Éditer des transactions existantes")
    st.caption("Modifiez le libellé, le montant, la date ou la catégorie directement dans le tableau.")

    with st.sidebar:
        st.subheader("Filtres — Correction")
        edit_biz_label = st.selectbox(
            "Activité",
            list(_BUSINESS_LABELS.keys()),
            key="edit_biz",
        )
        edit_year = st.selectbox(
            "Année",
            [date.today().year, date.today().year - 1],
            key="edit_year",
        )

    edit_biz_id = _BUSINESS_LABELS[edit_biz_label]

    try:
        df_edit = read_transactions(business_id=edit_biz_id, year=edit_year)
    except Exception as exc:
        st.error(f"Impossible de charger les transactions : {exc}")
        df_edit = pl.DataFrame()

    if df_edit.is_empty():
        st.info("Aucune transaction sur cette période.")
    else:
        # Stocker le snapshot d'origine pour détecter les changements
        origin_key = f"edit_origin_{edit_biz_id}_{edit_year}"
        if origin_key not in st.session_state:
            st.session_state[origin_key] = df_edit.to_dicts()

        display_cols = [c for c in ["id", "date", "label", "amount", "category", "notes"]
                        if c in df_edit.columns]
        display_df = df_edit.select(display_cols)

        edited = st.data_editor(
            display_df,
            key=f"editor_{edit_biz_id}_{edit_year}",
            width='stretch',
            hide_index=True,
            disabled=["id"],
            column_config={
                "id": None,
                "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                "label": st.column_config.TextColumn("Libellé", width="large"),
                "amount": st.column_config.NumberColumn("Montant (€)", format="%.2f €"),
                "category": st.column_config.SelectboxColumn(
                    "Catégorie",
                    options=_cats_by_biz.get(edit_biz_id, _all_category_names),
                    required=False,
                ),
                "notes": st.column_config.TextColumn("Notes"),
            },
        )

        if not isinstance(edited, pl.DataFrame):
            edited = pl.from_pandas(edited)

        col_save, col_del, col_reset = st.columns([2, 1, 1])

        with col_save:
            if st.button("💾 Sauvegarder les modifications", width='stretch', type="primary"):
                origin_map = {row["id"]: row for row in st.session_state[origin_key]}
                changed = []
                for row in edited.iter_rows(named=True):
                    tx_id = row.get("id")
                    if not tx_id:
                        continue
                    orig = origin_map.get(tx_id, {})
                    diff = {
                        k: v for k, v in row.items()
                        if k != "id" and str(v) != str(orig.get(k))
                    }
                    if diff:
                        changed.append((tx_id, diff))

                if changed:
                    for tx_id, diff in changed:
                        # Convertir les dates en ISO string
                        if "date" in diff and hasattr(diff["date"], "isoformat"):
                            diff["date"] = diff["date"].isoformat()
                        update_transaction(tx_id, diff)
                    invalidate_cache()
                    del st.session_state[origin_key]
                    st.toast(f"{len(changed)} transaction(s) mise(s) à jour ✅", icon="✅")
                    st.rerun()
                else:
                    st.toast("Aucune modification détectée.", icon="ℹ️")

        with col_del:
            st.write("")
            with st.expander("🗑️ Supprimer"):
                del_id = st.text_input("ID à supprimer", key="del_id", placeholder="uuid...")
                if st.button("Confirmer la suppression", key="confirm_del", type="secondary"):
                    if del_id.strip():
                        try:
                            delete_transaction(del_id.strip())
                            invalidate_cache()
                            if origin_key in st.session_state:
                                del st.session_state[origin_key]
                            st.toast("Transaction supprimée.", icon="🗑️")
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

        with col_reset:
            st.write("")
            if st.button("↩️ Annuler les modifications", width='stretch'):
                if origin_key in st.session_state:
                    del st.session_state[origin_key]
                st.rerun()
