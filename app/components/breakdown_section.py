"""Section réutilisable : où part l'argent — barres par groupe, détail par catégorie, variation."""

import plotly.graph_objects as go
import polars as pl
import streamlit as st

from src.logic.breakdown import (
    SINGLE_COLOR,
    by_group,
    category_group_map,
    color_of,
    format_delta,
    spending_table,
)
from src.services.db_reader import read_categories

_ALL_GROUPS = "Tous les groupes"


def _is_dark() -> bool:
    """Thème sombre de Streamlit (clair si l'information n'est pas disponible)."""
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


def _eur(value: float) -> str:
    return f"{value:,.0f} €".replace(",", " ")


def _bar_chart(labels: list[str], totals: list[float], pcts: list[float], colors: list[str],
               deltas: list[str]) -> go.Figure:
    """Barres horizontales fines, la plus grande en haut ; montant et part au bout de chaque barre."""
    fig = go.Figure(go.Bar(
        x=totals,
        y=labels,
        orientation="h",
        marker={"color": colors},
        text=[f"{_eur(t)} · {p:.0f} %" for t, p in zip(totals, pcts, strict=True)],
        textposition="outside",
        cliponaxis=False,
        customdata=list(zip(pcts, deltas, strict=True)),
        hovertemplate="<b>%{y}</b><br>%{x:,.0f} € (%{customdata[0]:.1f} %)<br>"
                      "vs période précédente : %{customdata[1]}<extra></extra>",
    ))
    fig.update_layout(
        height=44 * len(labels) + 50,
        margin={"l": 8, "r": 110, "t": 8, "b": 8},
        bargap=0.55,
        showlegend=False,
        xaxis={"visible": False},
        # automargin : la marge gauche s'agrandit pour montrer les noms (sinon ils sont rognés)
        yaxis={"autorange": "reversed", "title": None, "automargin": True, "ticksuffix": "  "},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def render_spending_breakdown(
    current: pl.DataFrame,
    previous: pl.DataFrame | None,
    key: str,
    by: str = "group",
    empty_message: str = "Aucune dépense sur la période.",
) -> None:
    """Affiche la répartition des dépenses.

    Args:
        current: opérations de la période (colonnes amount, category ; les dépenses sont
            les montants négatifs).
        previous: opérations de la période précédente, pour la variation (None = sans).
        key: préfixe unique des widgets.
        by: "group" (barres par groupe de catégories, détail au choix) ou "category"
            (barres par catégorie, pour les activités pro qui n'ont qu'un groupe).
    """
    group_map = category_group_map(_categories())
    table = spending_table(current, previous, group_map)
    if table.is_empty():
        st.info(empty_message)
        return

    dark = _is_dark()
    total = float(table["total"].sum())
    previous_total = float(table["previous"].sum())
    # Sans dépense la période précédente (début des données), une variation n'aurait aucun
    # sens : chaque ligne serait « nouvelle ». On ne l'affiche pas.
    has_previous = previous is not None and previous_total > 0
    if has_previous:
        st.caption(
            f"Total : **{_eur(total)}** · {format_delta(total - previous_total, (total - previous_total) / previous_total * 100)} "
            "par rapport à la période précédente"
        )
    else:
        st.caption(f"Total : **{_eur(total)}**")

    if by == "group":
        groups = by_group(table)
        labels = groups["group"].to_list()
        colors = [color_of(g, dark) for g in labels]
        chart_totals, chart_pcts = groups["total"].to_list(), groups["pct"].to_list()
        deltas = [
            format_delta(d, p) if has_previous else "—"
            for d, p in zip(groups["delta"].to_list(), groups["delta_pct"].to_list(), strict=True)
        ]
        chosen = st.selectbox("Détail d'un groupe", [_ALL_GROUPS, *labels], key=f"{key}_group")
        detail = table if chosen == _ALL_GROUPS else table.filter(pl.col("group") == chosen)
    else:
        labels = table["category"].to_list()
        colors = [SINGLE_COLOR[1 if dark else 0]] * len(labels)
        chart_totals, chart_pcts = table["total"].to_list(), table["pct"].to_list()
        deltas = [
            format_delta(d, p) if has_previous else "—"
            for d, p in zip(table["delta"].to_list(), table["delta_pct"].to_list(), strict=True)
        ]
        detail = table

    st.plotly_chart(
        _bar_chart(labels, chart_totals, chart_pcts, colors, deltas), width="stretch",
        key=f"{key}_chart",
    )

    # Le tableau complète le graphique : toutes les catégories, avec la variation
    shown = detail.with_columns(
        pl.struct(["delta", "delta_pct"]).map_elements(
            lambda s: format_delta(s["delta"], s["delta_pct"]), return_dtype=pl.Utf8
        ).alias("variation")
    )
    columns = ["group", "category", "total", "pct", "previous", "variation"]
    renames = {"group": "Groupe", "category": "Catégorie", "total": "Montant", "pct": "Part",
               "previous": "Période précédente", "variation": "Variation"}
    if by != "group":
        columns.remove("group")
    if not has_previous:
        columns = [c for c in columns if c not in ("previous", "variation")]
    st.dataframe(
        shown.select(columns).rename({c: renames[c] for c in columns}).to_pandas(),
        hide_index=True,
        width="stretch",
        column_config={
            "Montant": st.column_config.NumberColumn(format="%.2f €"),
            "Part": st.column_config.ProgressColumn(format="%.0f %%", min_value=0, max_value=100),
            "Période précédente": st.column_config.NumberColumn(format="%.2f €"),
        },
    )


def _categories() -> list[dict]:
    """Catégories (avec leur groupe) ; liste vide si la lecture échoue : tout va dans « Autres »."""
    try:
        frame = read_categories()
        return frame.to_dicts() if not frame.is_empty() else []
    except Exception:
        return []
