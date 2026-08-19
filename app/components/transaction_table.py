"""Composant réutilisable : tableau de transactions éditable."""

from datetime import date
from typing import Callable

import polars as pl
import streamlit as st

from src.config import TransactionSource
from src.services.db_reader import invalidate_cache
from src.services.supabase import delete_transaction, insert_transaction, update_transaction


def render_transaction_table(
    df: pl.DataFrame,
    key: str,
    categories: list[str],
    on_save: Callable[[list[dict]], None] | None = None,
) -> pl.DataFrame:
    """Affiche les transactions séparées en deux onglets (Revenus / Dépenses).

    Le montant est toujours affiché en valeur positive : le sens (entrée ou
    sortie) est porté par l'onglet, plus besoin de lire le signe.

    Args:
        df: DataFrame de transactions (colonnes attendues : id, date, label, amount, source, category).
        key: Clé unique pour le widget (évite les conflits entre pages).
        categories: Liste des catégories disponibles dans le selectbox.
        on_save: Callback appelé avec la liste des {id, category} modifiés.

    Returns:
        DataFrame avec les modifications appliquées par l'utilisateur (revenus + dépenses).
    """
    tab_income, tab_expense = st.tabs(["↑ Revenus", "↓ Dépenses"])

    with tab_income:
        edited_income = _render_direction_table(
            df.filter(pl.col("amount") > 0), key=f"{key}_income", categories=categories
        )
    with tab_expense:
        edited_expense = _render_direction_table(
            df.filter(pl.col("amount") < 0), key=f"{key}_expense", categories=categories
        )

    edited = pl.concat([edited_income, edited_expense], how="diagonal_relaxed")

    if on_save is not None and st.button("Sauvegarder les catégories", key=f"{key}_save"):
        updates = [
            {"id": row["id"], "category": row["category"]}
            for row in edited.iter_rows(named=True)
            if row.get("id") and row.get("category")
        ]
        if updates:
            on_save(updates)
            st.toast("Catégories sauvegardées !", icon="✅")
        else:
            st.toast("Aucune catégorie à sauvegarder.", icon="ℹ️")

    return edited


def _render_direction_table(df: pl.DataFrame, key: str, categories: list[str]) -> pl.DataFrame:
    """Affiche un st.data_editor pour un seul sens (revenus ou dépenses).

    Le montant est affiché en valeur absolue ; l'appelant sait déjà, via l'onglet,
    s'il s'agit d'un revenu ou d'une dépense.
    """
    if df.is_empty():
        st.info("Aucune transaction sur cette période.")
        return df

    display_cols = ["id", "date", "label", "amount", "source", "category", "note"]
    available_cols = [c for c in display_cols if c in df.columns]
    display_df = df.select(available_cols).with_columns(pl.col("amount").abs())

    edited = st.data_editor(
        display_df,
        key=key,
        width='stretch',
        hide_index=True,
        disabled=[c for c in available_cols if c != "category"],
        column_config={
            "id": None,
            "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
            "label": st.column_config.TextColumn("Libellé", width="large"),
            "amount": st.column_config.NumberColumn("Montant (€)", format="%.2f €"),
            "source": st.column_config.TextColumn("Source", width="small"),
            "category": st.column_config.SelectboxColumn(
                "Catégorie",
                options=categories,
                required=False,
                width="medium",
            ),
            "note": st.column_config.TextColumn("Note", width="medium"),
        },
    )

    # Convertir en Polars si Streamlit a retourné un DataFrame pandas
    if not isinstance(edited, pl.DataFrame):
        edited = pl.from_pandas(edited)

    return edited


def render_editable_transactions(
    df: pl.DataFrame,
    business_id: str,
    key: str,
    categories_by_direction: dict[str, list[str]],
    account_id: str | None = None,
    account_options: dict[str, str] | None = None,
) -> None:
    """Tableau Revenus/Dépenses éditable, avec ajout de ligne directe.

    Le bouton "➕ Ajouter une transaction" insère une ligne vide en tête du
    tableau (le plus récent étant affiché en premier), remplie sur place.
    La suppression se fait via une case "🗑️ Supprimer" par ligne (pas le "−"
    natif du tableau, désactivé ici). Un seul bouton "Enregistrer" par
    tableau persiste tout — nouvelles lignes (insert), lignes modifiées
    (update), lignes cochées à supprimer (delete).

    Args:
        df: transactions de la période (colonnes id, date, label, amount, category,
            et account_id si account_options est fourni).
        business_id: activité fixe appliquée à toute nouvelle ligne créée ici.
        key: préfixe unique pour les clés de widgets.
        categories_by_direction: {"income": [...], "expense": [...]}.
        account_id: compte fixe pour les nouvelles lignes (page à 1 seul compte).
        account_options: {libellé affiché: id} si plusieurs comptes possibles —
            affiche une colonne Compte éditable. Mutuellement exclusif avec account_id.
    """
    tab_income, tab_expense = st.tabs(["↑ Revenus", "↓ Dépenses"])
    with tab_income:
        _render_editable_direction(
            df.filter(pl.col("amount") > 0), "income", business_id, f"{key}_income",
            categories_by_direction.get("income", []), account_id, account_options,
        )
    with tab_expense:
        _render_editable_direction(
            df.filter(pl.col("amount") < 0), "expense", business_id, f"{key}_expense",
            categories_by_direction.get("expense", []), account_id, account_options,
        )


def _render_editable_direction(
    direction_df: pl.DataFrame,
    direction: str,
    business_id: str,
    key: str,
    categories: list[str],
    account_id: str | None,
    account_options: dict[str, str] | None,
) -> None:
    origin_key = f"{key}_origin"
    if origin_key not in st.session_state:
        st.session_state[origin_key] = direction_df.to_dicts()

    pending_key = f"{key}_pending_new"
    if pending_key not in st.session_state:
        st.session_state[pending_key] = []

    # Le data_editor mémorise ses propres modifications (ajouts/suppressions) sous
    # sa clé, indépendamment des données qu'on lui repasse à chaque rerun. Un
    # numéro de version dans la clé force un widget entièrement neuf après chaque
    # enregistrement — plus fiable qu'un del st.session_state après coup.
    version_key = f"{key}_version"
    if version_key not in st.session_state:
        st.session_state[version_key] = 0

    # Ajout piloté par un bouton (pas le "+" natif, qui ajoute toujours en bas et
    # perturbe le suivi des lignes existantes) : la nouvelle ligne vide s'insère
    # en tête, remplie sur place, tri du plus récent au plus ancien respecté.
    if st.button("➕ Ajouter une transaction", key=f"{key}_add_row"):
        blank_row = {"id": None, "date": date.today(), "label": "", "amount": 0.0, "category": None}
        if account_options:
            blank_row["compte"] = None
        st.session_state[pending_key].insert(0, blank_row)
        # Une nouvelle ligne en tête décale la position de toutes les lignes
        # existantes. Le data_editor mémorise ses modifications (dont les cases
        # "Supprimer" cochées) par position sous sa clé : sans ce changement de
        # version, ces marques se retrouveraient réappliquées aux mauvaises
        # lignes après le décalage (ex. une suppression en attente semble
        # "annulée" tandis qu'une autre ligne se coche à sa place).
        st.session_state[version_key] += 1

    display_cols = [c for c in ["id", "date", "label", "amount", "category"] if c in direction_df.columns]
    working = direction_df.select(display_cols).with_columns(pl.col("amount").abs())

    if account_options:
        id_to_account_name = {v: k for k, v in account_options.items()}
        account_ids = direction_df["account_id"].to_list() if "account_id" in direction_df.columns else []
        working = working.with_columns(
            pl.Series("compte", [id_to_account_name.get(a) for a in account_ids])
        )

    if st.session_state[pending_key]:
        pending_df = pl.DataFrame(st.session_state[pending_key], schema=working.schema)
        working = pl.concat([pending_df, working], how="diagonal_relaxed")

    working = working.with_columns(pl.lit(False).alias("Supprimer"))

    column_config: dict = {
        "id": None,
        "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
        "label": st.column_config.TextColumn("Libellé", width="large"),
        "amount": st.column_config.NumberColumn("Montant (€)", format="%.2f €", min_value=0.0),
        "category": st.column_config.SelectboxColumn("Catégorie", options=categories, required=False),
        "Supprimer": st.column_config.CheckboxColumn("🗑️ Supprimer"),
    }
    if account_options:
        column_config["compte"] = st.column_config.SelectboxColumn(
            "Compte", options=list(account_options.keys()), required=False
        )

    edited = st.data_editor(
        working,
        key=f"{key}_editor_v{st.session_state[version_key]}",
        width='stretch',
        hide_index=True,
        num_rows="fixed",
        disabled=["id"],
        column_config=column_config,
    )
    if not isinstance(edited, pl.DataFrame):
        edited = pl.from_pandas(edited)

    # La suppression est immédiate (case cochée = transaction supprimée tout de
    # suite), pas différée jusqu'au bouton "Enregistrer" : ça évite de dépendre
    # du suivi par position du data_editor (fragile dès que les lignes bougent,
    # ex. ajout d'une nouvelle ligne) pour une action destructive.
    to_delete_now = [
        row["id"] for row in edited.iter_rows(named=True)
        if row.get("id") and row.get("Supprimer")
    ]
    if to_delete_now:
        try:
            for row_id in to_delete_now:
                delete_transaction(row_id)
            invalidate_cache()
            del st.session_state[origin_key]
            st.session_state[version_key] += 1
            st.toast(f"{len(to_delete_now)} transaction(s) supprimée(s) ✅", icon="✅")
            st.rerun()
        except Exception as exc:
            st.error(f"Erreur lors de la suppression : {exc}")
        return

    if not st.button("💾 Enregistrer", key=f"{key}_save", width='stretch'):
        return

    origin_map = {row["id"]: row for row in st.session_state[origin_key] if row.get("id")}
    sign = 1.0 if direction == "income" else -1.0

    new_rows: list[dict] = []
    updates: list[tuple[str, dict]] = []

    for row in edited.iter_rows(named=True):
        row_id = row.get("id")
        row_date = row.get("date")
        row_date_iso = row_date.isoformat() if hasattr(row_date, "isoformat") else row_date

        if row_id is None:
            # Nouvelle ligne (ajoutée via le bouton) — ignorée tant qu'elle n'est pas complète.
            if not row.get("label") or not row_date_iso or not row.get("amount"):
                continue
            acc = account_options.get(row.get("compte")) if account_options else account_id
            new_rows.append({
                "date": row_date_iso,
                "amount": abs(float(row["amount"])) * sign,
                "label": row["label"],
                "source": str(TransactionSource.MANUAL),
                "business_id": business_id,
                "account_id": acc,
                "category": row.get("category"),
                "notes": None,
            })
        else:
            orig = origin_map.get(row_id, {})
            diff: dict = {}
            if row.get("label") != orig.get("label"):
                diff["label"] = row.get("label")
            if row.get("category") != orig.get("category"):
                diff["category"] = row.get("category")
            new_amount = abs(float(row["amount"])) * sign
            if abs(new_amount - float(orig.get("amount", 0) or 0)) > 0.001:
                diff["amount"] = new_amount
            if str(row_date_iso) != str(orig.get("date")):
                diff["date"] = row_date_iso
            if account_options:
                new_acc = account_options.get(row.get("compte"))
                if new_acc != orig.get("account_id"):
                    diff["account_id"] = new_acc
            if diff:
                updates.append((row_id, diff))

    try:
        for payload in new_rows:
            insert_transaction(payload)
        for row_id, diff in updates:
            update_transaction(row_id, diff)
        invalidate_cache()
        del st.session_state[origin_key]
        st.session_state[pending_key] = []
        st.session_state[version_key] += 1
        st.toast(
            f"{len(new_rows)} ajoutée(s), {len(updates)} modifiée(s) ✅",
            icon="✅",
        )
        st.rerun()
    except Exception as exc:
        st.error(f"Erreur lors de l'enregistrement : {exc}")
