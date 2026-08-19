"""Section réutilisable : virement entre comptes + liste des virements récents.

Un virement peut traverser 2 activités différentes (ex : Booth in Lyon vers
Perso) — le choix des comptes source/destination n'est donc jamais restreint
à l'activité de la page qui affiche cette section.
"""

from datetime import date

import polars as pl
import streamlit as st

from src.logic.consolidated import pair_transfers
from src.services.db_reader import invalidate_cache, read_accounts, read_transactions
from src.services.supabase import delete_transfer, insert_transaction, insert_transfer


def render_transfer_section(key_prefix: str) -> None:
    """Formulaire de virement + virements récents (suppression immédiate + annulation).

    Args:
        key_prefix: préfixe unique pour les clés de widgets (une section par page).
    """
    accounts_df = read_accounts()
    all_accounts_list = accounts_df.sort("name").to_dicts() if not accounts_df.is_empty() else []

    st.caption(
        "Pour déplacer de l'argent d'un compte à un autre (ex : retirer de l'argent du "
        "compte Booth in Lyon vers le compte perso). N'affecte jamais le CA, les dépenses "
        "ou l'URSSAF — seulement le solde des 2 comptes concernés."
    )

    if len(all_accounts_list) < 2:
        st.info("Il faut au moins 2 comptes configurés pour enregistrer un virement.")
    else:
        transfer_account_options = {
            f"{a['name']} ({a.get('institution', '?')})": a for a in all_accounts_list
        }

        col_from, col_to = st.columns(2)
        transfer_from_label = col_from.selectbox(
            "Compte source (débité)", list(transfer_account_options.keys()), key=f"{key_prefix}_transfer_from"
        )
        transfer_to_choices = [
            label for label in transfer_account_options if label != transfer_from_label
        ]
        transfer_to_label = col_to.selectbox(
            "Compte destination (crédité)", transfer_to_choices, key=f"{key_prefix}_transfer_to"
        )

        with st.form(f"{key_prefix}_form_transfer", clear_on_submit=True):
            col_date, col_amount = st.columns(2)
            transfer_date = col_date.date_input("Date", value=date.today(), key=f"{key_prefix}_transfer_date")
            transfer_amount = col_amount.number_input(
                "Montant (€)", min_value=0.0, step=0.01, format="%.2f", key=f"{key_prefix}_transfer_amount"
            )
            transfer_label = st.text_input(
                "Libellé", value="Virement interne", max_chars=200, key=f"{key_prefix}_transfer_label"
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
        "Année", [date.today().year, date.today().year - 1], key=f"{key_prefix}_transfer_list_year"
    )
    try:
        transfer_year_df = read_transactions(year=transfer_list_year, include_transfers=True)
    except Exception as exc:
        st.error(f"Impossible de charger les virements : {exc}")
        transfer_year_df = pl.DataFrame()

    recent_transfers = (
        pair_transfers(transfer_year_df, accounts_df) if not transfer_year_df.is_empty() else pl.DataFrame()
    )

    # Numéro de version dans la clé du tableau : sans ça, Streamlit peut réappliquer
    # une case cochée à la mauvaise ligne après une suppression (les lignes se décalent).
    version_key = f"{key_prefix}_transfer_version_{transfer_list_year}"
    if version_key not in st.session_state:
        st.session_state[version_key] = 0

    undo_key = f"{key_prefix}_transfer_undo_{transfer_list_year}"
    if undo_key not in st.session_state:
        st.session_state[undo_key] = []

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
            key=f"{key_prefix}_transfers_table_{transfer_list_year}_v{st.session_state[version_key]}",
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
            key=f"{key_prefix}_confirm_del_transfer",
            disabled=not transfers_to_delete,
        ):
            try:
                # Snapshot des 2 écritures de chaque virement coché (pour pouvoir les
                # recréer à l'identique si l'utilisateur annule juste après).
                _EXCLUDE = ("id", "created_at", "is_income")
                snapshot = [
                    {k: v for k, v in row.items() if k not in _EXCLUDE}
                    for row in transfer_year_df.filter(
                        pl.col("transfer_group_id").is_in(transfers_to_delete)
                    ).to_dicts()
                ]
                for transfer_group_id in transfers_to_delete:
                    delete_transfer(transfer_group_id)
                st.session_state[undo_key] = snapshot
                invalidate_cache()
                st.session_state[version_key] += 1
                st.toast(f"{len(transfers_to_delete)} virement(s) supprimé(s).", icon="🗑️")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    # Le bouton "Annuler" ne s'affiche que juste après une suppression, tant qu'elle
    # n'a pas été remplacée par une autre.
    if st.session_state[undo_key]:
        undo_count = len(st.session_state[undo_key])
        if st.button(
            f"↩️ Annuler la dernière suppression ({undo_count} écriture(s))",
            key=f"{key_prefix}_undo_transfer",
        ):
            try:
                for row in st.session_state[undo_key]:
                    # Le snapshot vient directement de Polars : "date" y est un objet
                    # datetime.date, pas un texte. Le client Supabase sérialise le payload
                    # en JSON, qui ne sait pas encoder un date brut (TypeError) — d'où
                    # l'échec systématique de la restauration sans ça.
                    row_date = row.get("date")
                    if hasattr(row_date, "isoformat"):
                        row = {**row, "date": row_date.isoformat()}
                    insert_transaction(row)
                st.session_state[undo_key] = []
                invalidate_cache()
                st.session_state[version_key] += 1
                st.toast(f"{undo_count} écriture(s) restaurée(s) ✅", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(f"Erreur lors de la restauration : {exc}")
