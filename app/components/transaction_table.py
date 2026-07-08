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
