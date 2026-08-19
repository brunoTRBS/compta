"""Page Saisie & Corrections — ajout manuel, file d'attente, édition complète."""

from datetime import date

import polars as pl
import streamlit as st

from app.components.auth import require_auth
from app.components.transaction_table import render_transaction_table
from src.config import BusinessId, TransactionSource
from src.logic.categorizer import apply_rules, categorization_stats, get_pending_categorization
from src.logic.consolidated import pair_transfers
from src.logic.recurring import default_materialize_date, due_templates
from src.services.db_reader import (
    invalidate_cache,
    read_accounts,
    read_categories,
    read_recurring_transactions,
    read_transactions,
)
from src.services.supabase import (
    bulk_update_categories,
    delete_recurring_transaction,
    delete_transaction,
    delete_transfer,
    fetch_categorization_rules,
    insert_recurring_transaction,
    insert_transaction,
    insert_transfer,
    materialize_recurring_transactions,
    update_recurring_transaction,
    update_transaction,
)

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

# Comptes chargés une fois pour toute la page
_accounts_df = read_accounts()
_accounts_by_owner: dict[str, list[dict]] = {
    biz_id: _accounts_df.filter(pl.col("owner") == biz_id).sort("name").to_dicts()
    for biz_id in [str(BusinessId.PHI_RISING), str(BusinessId.BOOTH_IN_LYON), str(BusinessId.PERSONAL)]
} if not _accounts_df.is_empty() else {}
_all_accounts_list: list[dict] = _accounts_df.sort("name").to_dicts() if not _accounts_df.is_empty() else []

tab_new, tab_recurring, tab_transfer, tab_pending, tab_edit = st.tabs(
    ["➕ Nouvelle transaction", "📅 Récurrences", "🔁 Virement entre comptes",
     "⏳ En attente de catégorisation", "✏️ Corriger des transactions"]
)

# ---------------------------------------------------------------------------
# Onglet 1 — Saisie manuelle
# ---------------------------------------------------------------------------
with tab_new:
    st.subheader("Ajouter une transaction manuelle")
    st.caption("Idéal pour les paiements en espèces ou les opérations non importées.")

    # Hors formulaire : réagit immédiatement pour filtrer les catégories et les comptes
    col_biz, col_account, col_type = st.columns(3)
    tx_business_label = col_biz.selectbox("Activité", list(_BUSINESS_LABELS.keys()), key="new_tx_biz")
    tx_biz_id = _BUSINESS_LABELS[tx_business_label]

    biz_accounts = _accounts_by_owner.get(tx_biz_id, [])
    tx_account_options = {f"{a['name']} ({a.get('institution', '?')})": a["id"] for a in biz_accounts}
    tx_account_label = col_account.selectbox(
        "Compte",
        list(tx_account_options.keys()) or ["— Aucun compte configuré —"],
        key="new_tx_account",
    )

    tx_type = col_type.radio("Type", ["Dépense", "Revenu"], horizontal=True, key="new_tx_type")

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
                "account_id": tx_account_options.get(tx_account_label),
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
# Onglet 2 — Récurrences
# ---------------------------------------------------------------------------
with tab_recurring:
    st.subheader("Transactions récurrentes")
    st.caption(
        "Définis un modèle une fois (loyer, abonnement, salaire...), "
        "puis valide-le chaque mois en un clic au lieu de tout retaper."
    )

    try:
        recurring_df = read_recurring_transactions()
    except Exception as exc:
        st.error(f"Impossible de charger les récurrences : {exc}")
        recurring_df = pl.DataFrame()

    _id_to_account_name: dict[str, str] = (
        dict(zip(_accounts_df["id"].to_list(), _accounts_df["name"].to_list()))
        if not _accounts_df.is_empty() else {}
    )

    # --- À valider ce mois-ci ---
    st.markdown("**À valider ce mois-ci**")
    today = date.today()
    due_df = due_templates(recurring_df, today.year, today.month) if not recurring_df.is_empty() else pl.DataFrame()

    if due_df.is_empty():
        st.info("Rien à valider ce mois-ci — tous les modèles actifs sont déjà à jour.")
    else:
        due_display = (
            due_df.with_columns(
                pl.col("account_id").map_elements(_id_to_account_name.get, return_dtype=pl.Utf8).alias("compte_nom"),
                pl.col("amount").abs().alias("amount_abs"),
            )
            .select(["id", "label", "compte_nom", "amount_abs", "category", "business_id", "account_id", "day_of_month", "amount"])
            .rename({"amount": "amount_signed"})
            .with_columns(pl.lit(True).alias("Valider"))
        )
        edited_due = st.data_editor(
            due_display,
            key="due_recurring_editor",
            width='stretch',
            hide_index=True,
            disabled=["id", "label", "compte_nom", "category", "business_id", "account_id", "day_of_month", "amount_signed"],
            column_config={
                "id": None,
                "business_id": None,
                "account_id": None,
                "day_of_month": None,
                "amount_signed": None,
                "label": st.column_config.TextColumn("Libellé"),
                "compte_nom": st.column_config.TextColumn("Compte"),
                "amount_abs": st.column_config.NumberColumn("Montant (€)", format="%.2f €"),
                "category": st.column_config.TextColumn("Catégorie"),
                "Valider": st.column_config.CheckboxColumn("Valider"),
            },
        )
        if not isinstance(edited_due, pl.DataFrame):
            edited_due = pl.from_pandas(edited_due)

        to_materialize = edited_due.filter(pl.col("Valider"))
        if st.button(
            f"✅ Ajouter les {to_materialize.shape[0]} transaction(s) validée(s)",
            type="primary", disabled=to_materialize.is_empty(),
        ):
            materializations = []
            for row in to_materialize.iter_rows(named=True):
                sign = 1.0 if row["amount_signed"] > 0 else -1.0
                final_amount = abs(float(row["amount_abs"])) * sign
                tx_date = default_materialize_date(int(row["day_of_month"]), today.year, today.month)
                materializations.append({
                    "recurring_id": row["id"],
                    "year": today.year,
                    "month": today.month,
                    "transaction": {
                        "date": tx_date.isoformat(),
                        "amount": final_amount,
                        "label": row["label"],
                        "source": str(TransactionSource.MANUAL),
                        "business_id": row["business_id"],
                        "account_id": row["account_id"],
                        "category": row["category"],
                        "notes": "Généré depuis une récurrence",
                    },
                })
            try:
                materialize_recurring_transactions(materializations)
                invalidate_cache()
                st.toast(f"{len(materializations)} transaction(s) ajoutée(s) ✅", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(f"Erreur lors de l'ajout : {exc}")

    st.divider()

    # --- Créer une récurrence ---
    st.markdown("**Créer une récurrence**")
    col_biz_r, col_account_r, col_type_r = st.columns(3)
    rec_business_label = col_biz_r.selectbox("Activité", list(_BUSINESS_LABELS.keys()), key="rec_biz")
    rec_biz_id = _BUSINESS_LABELS[rec_business_label]

    rec_biz_accounts = _accounts_by_owner.get(rec_biz_id, [])
    rec_account_options = {f"{a['name']} ({a.get('institution', '?')})": a["id"] for a in rec_biz_accounts}
    rec_account_label = col_account_r.selectbox(
        "Compte",
        list(rec_account_options.keys()) or ["— Aucun compte configuré —"],
        key="rec_account",
    )
    rec_type = col_type_r.radio("Type", ["Dépense", "Revenu"], horizontal=True, key="rec_type")
    rec_direction = "expense" if rec_type == "Dépense" else "income"
    rec_filtered_cats = _cats_by_biz_dir.get((rec_biz_id, rec_direction), [])

    with st.form("form_new_recurring", clear_on_submit=True):
        col_label_r, col_amount_r, col_day_r = st.columns([2, 1, 1])
        rec_label = col_label_r.text_input("Libellé", max_chars=200, placeholder="Ex : Loyer")
        rec_amount = col_amount_r.number_input("Montant (€)", min_value=0.0, step=0.01, format="%.2f")
        rec_day = col_day_r.number_input("Jour du mois", min_value=1, max_value=31, value=1, step=1)

        rec_category = st.selectbox("Catégorie", ["— Laisser vide —"] + rec_filtered_cats, key="rec_category_select")
        rec_notes = st.text_area("Notes (optionnel)", height=68, max_chars=500, key="rec_notes")

        submitted_rec = st.form_submit_button("Créer la récurrence", width='stretch')

    if submitted_rec:
        if not rec_label.strip():
            st.error("Le libellé est obligatoire.")
        else:
            signed = float(rec_amount) if rec_direction == "income" else -float(rec_amount)
            rec_payload: dict = {
                "label": rec_label.strip(),
                "amount": signed,
                "category": rec_category if rec_category != "— Laisser vide —" else None,
                "business_id": rec_biz_id,
                "account_id": rec_account_options.get(rec_account_label),
                "day_of_month": int(rec_day),
                "notes": rec_notes.strip() or None,
            }
            try:
                insert_recurring_transaction(rec_payload)
                invalidate_cache()
                st.toast(f"Récurrence « {rec_label.strip()} » créée ✅", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(f"Erreur lors de la création : {exc}")

    st.divider()

    # --- Gérer les récurrences existantes ---
    st.markdown("**Mes récurrences**")
    if recurring_df.is_empty():
        st.info("Aucune récurrence créée pour le moment.")
    else:
        manage_display = (
            recurring_df.with_columns(
                pl.col("account_id").map_elements(_id_to_account_name.get, return_dtype=pl.Utf8).alias("compte_nom"),
                pl.col("amount").abs().alias("amount_abs"),
            )
            .select(["id", "label", "compte_nom", "amount_abs", "category", "day_of_month", "is_active"])
            .with_columns(pl.lit(False).alias("Supprimer"))
        )
        edited_manage = st.data_editor(
            manage_display,
            key="manage_recurring_editor",
            width='stretch',
            hide_index=True,
            disabled=["id", "label", "compte_nom", "amount_abs", "category", "day_of_month"],
            column_config={
                "id": None,
                "label": st.column_config.TextColumn("Libellé"),
                "compte_nom": st.column_config.TextColumn("Compte"),
                "amount_abs": st.column_config.NumberColumn("Montant (€)", format="%.2f €"),
                "category": st.column_config.TextColumn("Catégorie"),
                "day_of_month": st.column_config.NumberColumn("Jour du mois"),
                "is_active": st.column_config.CheckboxColumn("Actif"),
                "Supprimer": st.column_config.CheckboxColumn("🗑️ Supprimer"),
            },
        )
        if not isinstance(edited_manage, pl.DataFrame):
            edited_manage = pl.from_pandas(edited_manage)

        col_save_rec, col_del_rec = st.columns(2)
        with col_save_rec:
            if st.button("💾 Enregistrer les statuts actif/inactif", width='stretch'):
                origin_active = dict(zip(recurring_df["id"].to_list(), recurring_df["is_active"].to_list()))
                changed_count = 0
                for row in edited_manage.iter_rows(named=True):
                    if row["is_active"] != origin_active.get(row["id"]):
                        update_recurring_transaction(row["id"], {"is_active": row["is_active"]})
                        changed_count += 1
                if changed_count:
                    invalidate_cache()
                    st.toast(f"{changed_count} récurrence(s) mise(s) à jour ✅", icon="✅")
                    st.rerun()
                else:
                    st.toast("Aucun changement détecté.", icon="ℹ️")

        with col_del_rec:
            recurring_to_delete = edited_manage.filter(pl.col("Supprimer"))["id"].to_list()
            if st.button(
                f"🗑️ Supprimer ({len(recurring_to_delete)})",
                width='stretch', disabled=not recurring_to_delete,
            ):
                try:
                    for rec_id in recurring_to_delete:
                        delete_recurring_transaction(rec_id)
                    invalidate_cache()
                    st.toast(f"{len(recurring_to_delete)} récurrence(s) supprimée(s) 🗑️", icon="🗑️")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

# ---------------------------------------------------------------------------
# Onglet 3 — Virement entre comptes
# ---------------------------------------------------------------------------
with tab_transfer:
    st.subheader("Virement entre deux comptes")
    st.caption(
        "Pour déplacer de l'argent d'un compte à un autre (ex : retirer de l'argent du "
        "compte Booth in Lyon vers le compte perso). N'affecte jamais le CA, les dépenses "
        "ou l'URSSAF — seulement le solde des 2 comptes concernés."
    )

    if len(_all_accounts_list) < 2:
        st.info("Il faut au moins 2 comptes configurés pour enregistrer un virement.")
    else:
        transfer_account_options = {
            f"{a['name']} ({a.get('institution', '?')})": a for a in _all_accounts_list
        }

        col_from, col_to = st.columns(2)
        transfer_from_label = col_from.selectbox(
            "Compte source (débité)", list(transfer_account_options.keys()), key="transfer_from"
        )
        transfer_to_choices = [
            label for label in transfer_account_options if label != transfer_from_label
        ]
        transfer_to_label = col_to.selectbox(
            "Compte destination (crédité)", transfer_to_choices, key="transfer_to"
        )

        with st.form("form_transfer", clear_on_submit=True):
            col_date, col_amount = st.columns(2)
            transfer_date = col_date.date_input("Date", value=date.today(), key="transfer_date")
            transfer_amount = col_amount.number_input(
                "Montant (€)", min_value=0.0, step=0.01, format="%.2f", key="transfer_amount"
            )
            transfer_label = st.text_input(
                "Libellé", value="Virement interne", max_chars=200, key="transfer_label"
            )
            submitted_transfer = st.form_submit_button("Enregistrer le virement", width='stretch')

        if submitted_transfer:
            if transfer_amount <= 0:
                st.error("Le montant doit être positif.")
            else:
                from_account = transfer_account_options[transfer_from_label]
                to_account = transfer_account_options[transfer_to_label]
                try:
                    insert_transfer(
                        from_account_id=from_account["id"],
                        to_account_id=to_account["id"],
                        from_business_id=from_account["owner"],
                        to_business_id=to_account["owner"],
                        amount=float(transfer_amount),
                        date=transfer_date.isoformat(),
                        label=transfer_label.strip() or "Virement interne",
                    )
                    invalidate_cache()
                    st.toast(
                        f"Virement de {transfer_amount:.2f} € : "
                        f"{transfer_from_label} → {transfer_to_label} ✅",
                        icon="✅",
                    )
                except Exception as exc:
                    st.error(f"Erreur lors de l'enregistrement : {exc}")

    st.divider()
    st.subheader("Virements récents")

    transfer_list_year = st.selectbox(
        "Année", [date.today().year, date.today().year - 1], key="transfer_list_year"
    )
    try:
        transfer_year_df = read_transactions(year=transfer_list_year, include_transfers=True)
    except Exception as exc:
        st.error(f"Impossible de charger les virements : {exc}")
        transfer_year_df = pl.DataFrame()

    recent_transfers = (
        pair_transfers(transfer_year_df, _accounts_df) if not transfer_year_df.is_empty() else pl.DataFrame()
    )

    if recent_transfers.is_empty():
        st.info("Aucun virement enregistré sur cette période.")
    else:
        transfers_display = (
            recent_transfers.select(
                ["transfer_group_id", "date", "label", "from_account", "to_account", "amount"]
            )
            .with_columns(pl.lit(False).alias("Supprimer"))
        )
        edited_transfers = st.data_editor(
            transfers_display,
            key=f"transfers_table_{transfer_list_year}",
            width='stretch',
            hide_index=True,
            disabled=["transfer_group_id", "date", "label", "from_account", "to_account", "amount"],
            column_config={
                "transfer_group_id": None,
                "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                "label": st.column_config.TextColumn("Libellé"),
                "from_account": st.column_config.TextColumn("De"),
                "to_account": st.column_config.TextColumn("Vers"),
                "amount": st.column_config.NumberColumn("Montant (€)", format="%.2f €"),
                "Supprimer": st.column_config.CheckboxColumn("🗑️ Supprimer"),
            },
        )
        if not isinstance(edited_transfers, pl.DataFrame):
            edited_transfers = pl.from_pandas(edited_transfers)

        transfers_to_delete = edited_transfers.filter(pl.col("Supprimer"))["transfer_group_id"].to_list()
        if st.button(
            f"🗑️ Supprimer le(s) virement(s) coché(s) ({len(transfers_to_delete)})",
            disabled=not transfers_to_delete,
        ):
            try:
                for transfer_group_id in transfers_to_delete:
                    delete_transfer(transfer_group_id)
                invalidate_cache()
                st.toast(f"{len(transfers_to_delete)} virement(s) supprimé(s).", icon="🗑️")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

# ---------------------------------------------------------------------------
# Onglet 4 — File des transactions en attente
# ---------------------------------------------------------------------------
with tab_pending:
    st.subheader("Transactions sans catégorie")

    col_biz_p, col_year_p = st.columns(2)
    pending_biz_label = col_biz_p.selectbox(
        "Activité",
        ["Toutes"] + list(_BUSINESS_LABELS.keys()),
        key="pending_biz",
    )
    pending_year = col_year_p.selectbox(
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
# Onglet 5 — Correction complète
# ---------------------------------------------------------------------------
with tab_edit:
    st.subheader("Éditer des transactions existantes")
    st.caption("Modifiez le libellé, le montant, la date ou la catégorie directement dans le tableau.")

    col_biz_e, col_year_e = st.columns(2)
    edit_biz_label = col_biz_e.selectbox(
        "Activité",
        list(_BUSINESS_LABELS.keys()),
        key="edit_biz",
    )
    edit_year = col_year_e.selectbox(
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
        # Comptes possibles pour cette activité (ex : Perso a 3 comptes réels)
        biz_accounts_df = _accounts_df.filter(pl.col("owner") == edit_biz_id) if not _accounts_df.is_empty() else pl.DataFrame()
        _id_to_name: dict[str, str] = (
            dict(zip(biz_accounts_df["id"].to_list(), biz_accounts_df["name"].to_list()))
            if not biz_accounts_df.is_empty() else {}
        )
        _name_to_id: dict[str, str] = {v: k for k, v in _id_to_name.items()}
        _account_name_options = sorted(_id_to_name.values())

        # Stocker le snapshot d'origine pour détecter les changements
        origin_key = f"edit_origin_{edit_biz_id}_{edit_year}"
        if origin_key not in st.session_state:
            st.session_state[origin_key] = df_edit.to_dicts()

        display_cols = [c for c in ["id", "date", "label", "amount", "category", "notes"]
                        if c in df_edit.columns]

        def _editable_direction_table(direction_df: pl.DataFrame, direction: str, editor_key: str) -> pl.DataFrame:
            """Éditeur pour un seul sens ; montant affiché en positif, re-signé au retour."""
            if direction_df.is_empty():
                st.info(
                    "Aucun revenu sur cette période." if direction == "income"
                    else "Aucune dépense sur cette période."
                )
                return direction_df.select(display_cols + ["account_id"])

            with_account_name = direction_df.with_columns(
                pl.col("account_id").map_elements(_id_to_name.get, return_dtype=pl.Utf8).alias("compte")
            )
            display_df = (
                with_account_name.select(display_cols + ["compte"])
                .with_columns(pl.col("amount").abs())
            )
            cats = _cats_by_biz_dir.get((edit_biz_id, direction)) or _cats_by_biz.get(
                edit_biz_id, _all_category_names
            )

            edited_dir = st.data_editor(
                display_df,
                key=editor_key,
                width='stretch',
                hide_index=True,
                disabled=["id"],
                column_config={
                    "id": None,
                    "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                    "label": st.column_config.TextColumn("Libellé", width="large"),
                    "amount": st.column_config.NumberColumn("Montant (€)", format="%.2f €"),
                    "category": st.column_config.SelectboxColumn(
                        "Catégorie", options=cats, required=False,
                    ),
                    "compte": st.column_config.SelectboxColumn(
                        "Compte", options=_account_name_options, required=False,
                    ),
                    "notes": st.column_config.TextColumn("Notes"),
                },
            )
            if not isinstance(edited_dir, pl.DataFrame):
                edited_dir = pl.from_pandas(edited_dir)

            edited_dir = edited_dir.with_columns(
                pl.col("compte").map_elements(_name_to_id.get, return_dtype=pl.Utf8).alias("account_id")
            ).drop("compte")

            sign = 1.0 if direction == "income" else -1.0
            return edited_dir.with_columns((pl.col("amount").abs() * sign).alias("amount"))

        tab_income_e, tab_expense_e = st.tabs(["↑ Revenus", "↓ Dépenses"])
        with tab_income_e:
            edited_income = _editable_direction_table(
                df_edit.filter(pl.col("amount") > 0), "income", f"editor_income_{edit_biz_id}_{edit_year}"
            )
        with tab_expense_e:
            edited_expense = _editable_direction_table(
                df_edit.filter(pl.col("amount") < 0), "expense", f"editor_expense_{edit_biz_id}_{edit_year}"
            )

        edited = pl.concat([edited_income, edited_expense], how="diagonal_relaxed")

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
                del_options = {
                    f"{'↑' if row['amount'] > 0 else '↓'} {row['date']} — {row['label']} — "
                    f"{abs(row['amount']):.2f} €": row["id"]
                    for row in df_edit.sort("date", descending=True).to_dicts()
                }
                del_label = st.selectbox(
                    "Transaction à supprimer", list(del_options.keys()), key="del_select"
                )
                if st.button("Confirmer la suppression", key="confirm_del", type="secondary"):
                    try:
                        delete_transaction(del_options[del_label])
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
