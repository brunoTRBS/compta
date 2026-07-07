"""Composant réutilisable : tableau de transactions éditable."""

from typing import Callable

import polars as pl
import streamlit as st


def render_transaction_table(
    df: pl.DataFrame,
    key: str,
    categories: list[str],
    on_save: Callable[[list[dict]], None] | None = None,
) -> pl.DataFrame:
    """Affiche un st.data_editor sur les transactions avec catégorie éditable.

    Args:
        df: DataFrame de transactions (colonnes attendues : id, date, label, amount, source, category).
        key: Clé unique pour le widget (évite les conflits entre pages).
        categories: Liste des catégories disponibles dans le selectbox.
        on_save: Callback appelé avec la liste des {id, category} modifiés.

    Returns:
        DataFrame avec les modifications appliquées par l'utilisateur.
    """
    display_cols = ["id", "date", "label", "amount", "source", "category", "note"]
    available_cols = [c for c in display_cols if c in df.columns]
    display_df = df.select(available_cols)

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
