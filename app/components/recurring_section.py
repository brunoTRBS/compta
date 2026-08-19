"""Section réutilisable : transactions récurrentes (à valider, créer, gérer).

Peut afficher toutes les récurrences (toutes activités) ou seulement celles
d'une activité donnée (Phi Rising, Booth in Lyon, Budget Perso).
"""

from datetime import date

import polars as pl
import streamlit as st

from src.config import BusinessId, TransactionSource
from src.logic.recurring import default_materialize_date, due_templates
from src.services.db_reader import (
    invalidate_cache,
    read_accounts,
    read_categories,
    read_recurring_transactions,
)
from src.services.supabase import (
    delete_recurring_transaction,
    insert_recurring_transaction,
    materialize_recurring_transactions,
    update_recurring_transaction,
)

_BUSINESS_LABELS = {
    "Phi Rising": str(BusinessId.PHI_RISING),
    "Booth in Lyon": str(BusinessId.BOOTH_IN_LYON),
    "Perso": str(BusinessId.PERSONAL),
}


def render_recurring_section(key_prefix: str, business_id_filter: str | None = None) -> None:
    """Affiche les récurrences dues, un formulaire de création et la liste de gestion.

    Args:
        key_prefix: préfixe unique pour les clés de widgets (une section par page).
        business_id_filter: si fourni, limite tout à cette activité (pas de
            sélecteur d'activité dans le formulaire de création, comptes filtrés).
            Si None, comportement global (toutes activités).
    """
    accounts_df = read_accounts()
    id_to_account_name: dict[str, str] = (
        dict(zip(accounts_df["id"].to_list(), accounts_df["name"].to_list()))
        if not accounts_df.is_empty() else {}
    )
    accounts_by_owner: dict[str, list[dict]] = {
        biz_id: accounts_df.filter(pl.col("owner") == biz_id).sort("name").to_dicts()
        for biz_id in _BUSINESS_LABELS.values()
    } if not accounts_df.is_empty() else {}

    all_cats_df = read_categories()
    cats_by_biz_dir: dict[tuple[str, str], list[str]] = {
        (biz_id, direction): sorted(
            all_cats_df.filter(
                (pl.col("business_id") == biz_id) & (pl.col("direction") == direction)
            )["name"].to_list()
        )
        for biz_id in _BUSINESS_LABELS.values()
        for direction in ["income", "expense"]
    } if not all_cats_df.is_empty() else {}

    try:
        recurring_df = read_recurring_transactions()
    except Exception as exc:
        st.error(f"Impossible de charger les récurrences : {exc}")
        recurring_df = pl.DataFrame()

    if business_id_filter is not None and not recurring_df.is_empty():
        recurring_df = recurring_df.filter(pl.col("business_id") == business_id_filter)

    # --- À valider ce mois-ci ---
    st.markdown("**À valider ce mois-ci**")
    today = date.today()
    due_df = due_templates(recurring_df, today.year, today.month) if not recurring_df.is_empty() else pl.DataFrame()

    if due_df.is_empty():
        st.info("Rien à valider ce mois-ci — tous les modèles actifs sont déjà à jour.")
    else:
        due_display = (
            due_df.with_columns(
                pl.col("account_id").map_elements(id_to_account_name.get, return_dtype=pl.Utf8).alias("compte_nom"),
                pl.col("amount").abs().alias("amount_abs"),
            )
            .select(["id", "label", "compte_nom", "amount_abs", "category", "business_id", "account_id", "day_of_month", "amount"])
            .rename({"amount": "amount_signed"})
            .with_columns(pl.lit(True).alias("Valider"))
        )
        edited_due = st.data_editor(
            due_display,
            key=f"{key_prefix}_due_recurring_editor",
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
            key=f"{key_prefix}_materialize_recurring",
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

    if business_id_filter is None:
        col_biz_r, col_account_r, col_type_r = st.columns(3)
        rec_business_label = col_biz_r.selectbox(
            "Activité", list(_BUSINESS_LABELS.keys()), key=f"{key_prefix}_rec_biz"
        )
        rec_biz_id = _BUSINESS_LABELS[rec_business_label]
    else:
        col_account_r, col_type_r = st.columns(2)
        rec_biz_id = business_id_filter

    rec_biz_accounts = accounts_by_owner.get(rec_biz_id, [])
    rec_account_options = {f"{a['name']} ({a.get('institution', '?')})": a["id"] for a in rec_biz_accounts}
    rec_account_label = col_account_r.selectbox(
        "Compte",
        list(rec_account_options.keys()) or ["— Aucun compte configuré —"],
        key=f"{key_prefix}_rec_account",
    )
    rec_type = col_type_r.radio("Type", ["Dépense", "Revenu"], horizontal=True, key=f"{key_prefix}_rec_type")
    rec_direction = "expense" if rec_type == "Dépense" else "income"
    rec_filtered_cats = cats_by_biz_dir.get((rec_biz_id, rec_direction), [])

    with st.form(f"{key_prefix}_form_new_recurring", clear_on_submit=True):
        col_label_r, col_amount_r, col_day_r = st.columns([2, 1, 1])
        rec_label = col_label_r.text_input("Libellé", max_chars=200, placeholder="Ex : Loyer")
        rec_amount = col_amount_r.number_input("Montant (€)", min_value=0.0, step=0.01, format="%.2f")
        rec_day = col_day_r.number_input("Jour du mois", min_value=1, max_value=31, value=1, step=1)

        rec_category = st.selectbox(
            "Catégorie", ["— Laisser vide —"] + rec_filtered_cats, key=f"{key_prefix}_rec_category_select"
        )
        rec_notes = st.text_area("Notes (optionnel)", height=68, max_chars=500, key=f"{key_prefix}_rec_notes")

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

    # Numéro de version dans la clé du tableau : sans ça, Streamlit peut réappliquer
    # une case cochée à la mauvaise ligne après une suppression (les lignes se décalent).
    rec_version_key = f"{key_prefix}_recurring_manage_version"
    if rec_version_key not in st.session_state:
        st.session_state[rec_version_key] = 0

    rec_undo_key = f"{key_prefix}_recurring_manage_undo"
    if rec_undo_key not in st.session_state:
        st.session_state[rec_undo_key] = []

    if recurring_df.is_empty():
        st.info("Aucune récurrence créée pour le moment.")
    else:
        manage_display = (
            recurring_df.with_columns(
                pl.col("account_id").map_elements(id_to_account_name.get, return_dtype=pl.Utf8).alias("compte_nom"),
                pl.col("amount").abs().alias("amount_abs"),
            )
            .select(["id", "label", "compte_nom", "amount_abs", "category", "day_of_month", "is_active"])
            .with_columns(pl.lit(False).alias("Supprimer"))
        )
        edited_manage = st.data_editor(
            manage_display,
            key=f"{key_prefix}_manage_recurring_editor_v{st.session_state[rec_version_key]}",
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
            if st.button("💾 Enregistrer les statuts actif/inactif", key=f"{key_prefix}_save_rec_status", width='stretch'):
                origin_active = dict(zip(recurring_df["id"].to_list(), recurring_df["is_active"].to_list()))
                changed_count = 0
                for row in edited_manage.iter_rows(named=True):
                    if row["is_active"] != origin_active.get(row["id"]):
                        update_recurring_transaction(row["id"], {"is_active": row["is_active"]})
                        changed_count += 1
                if changed_count:
                    invalidate_cache()
                    st.session_state[rec_version_key] += 1
                    st.toast(f"{changed_count} récurrence(s) mise(s) à jour ✅", icon="✅")
                    st.rerun()
                else:
                    st.toast("Aucun changement détecté.", icon="ℹ️")

        with col_del_rec:
            recurring_to_delete = edited_manage.filter(pl.col("Supprimer"))["id"].to_list()
            if st.button(
                f"🗑️ Supprimer ({len(recurring_to_delete)})",
                key=f"{key_prefix}_confirm_del_rec",
                width='stretch', disabled=not recurring_to_delete,
            ):
                try:
                    _EXCLUDE = ("id",)
                    snapshot = [
                        {k: v for k, v in row.items() if k not in _EXCLUDE}
                        for row in recurring_df.filter(pl.col("id").is_in(recurring_to_delete)).to_dicts()
                    ]
                    for rec_id in recurring_to_delete:
                        delete_recurring_transaction(rec_id)
                    st.session_state[rec_undo_key] = snapshot
                    invalidate_cache()
                    st.session_state[rec_version_key] += 1
                    st.toast(f"{len(recurring_to_delete)} récurrence(s) supprimée(s) 🗑️", icon="🗑️")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        # Le bouton "Annuler" ne s'affiche que juste après une suppression, tant qu'elle
        # n'a pas été remplacée par une autre.
        if st.session_state[rec_undo_key]:
            undo_rec_count = len(st.session_state[rec_undo_key])
            if st.button(
                f"↩️ Annuler la dernière suppression ({undo_rec_count} récurrence(s))",
                key=f"{key_prefix}_undo_recurring",
            ):
                try:
                    for row in st.session_state[rec_undo_key]:
                        insert_recurring_transaction(row)
                    st.session_state[rec_undo_key] = []
                    invalidate_cache()
                    st.session_state[rec_version_key] += 1
                    st.toast(f"{undo_rec_count} récurrence(s) restaurée(s) ✅", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Erreur lors de la restauration : {exc}")
