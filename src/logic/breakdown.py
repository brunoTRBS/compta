"""Répartition des dépenses : par groupe de catégories, avec variation d'un mois à l'autre.

Sert aux pages Budget Perso, Budget Foyer et activités pro. La vue d'ensemble « Perso + Foyer »
additionne les dépenses perso et les dépenses communes du foyer en comptant une seule fois ta
participation : elle est à la fois ta dépense « Loyer » et ce qui paie le foyer.
"""

from typing import Any

import polars as pl

from src.config import PARTICIPATION_CATEGORY
from src.logic.household_budget import common_expenses, regular_operations

UNCLASSIFIED = "non classé"
OTHER_GROUP = "Autres"

# Une couleur fixe par groupe : les 7 premières teintes de la palette catégorielle de
# référence, dans l'ordre, validées (écart daltonien et contraste) en mode clair comme sombre.
# La couleur suit le groupe, jamais son rang. Tout le reste (hors dépenses communes,
# activité pro, non classé) va dans « Autres », en gris.
GROUP_COLORS: dict[str, tuple[str, str]] = {  # groupe -> (clair, sombre)
    "Logement": ("#2a78d6", "#3987e5"),
    "Alimentation": ("#eb6834", "#d95926"),
    "Transport": ("#1baf7a", "#199e70"),
    "Loisirs": ("#eda100", "#c98500"),
    "Santé": ("#e87ba4", "#d55181"),
    "Vie courante": ("#008300", "#008300"),
    "Épargne": ("#6250d6", "#9085e9"),
}
OTHER_COLOR = ("#a6a59f", "#6b6a64")
# Barres par catégorie (activités pro) : une seule teinte, l'ordre est porté par la longueur
SINGLE_COLOR = ("#2a78d6", "#3987e5")


def category_group_map(categories: list[dict[str, Any]], direction: str = "expense") -> dict[str, str]:
    """{nom de catégorie: groupe} pour un sens, d'après la table categories."""
    groups: dict[str, str] = {}
    for cat in categories:
        if cat.get("direction") == direction and cat.get("group_name"):
            groups.setdefault(cat["name"], cat["group_name"])
    return groups


def display_group(category: str, group_map: dict[str, str]) -> str:
    """Groupe affiché : le groupe coloré de la catégorie, sinon « Autres »."""
    group = group_map.get(category)
    return group if group in GROUP_COLORS else OTHER_GROUP


def color_of(group: str, dark: bool = False) -> str:
    colors = GROUP_COLORS.get(group, OTHER_COLOR)
    return colors[1] if dark else colors[0]


def _expenses_by_category(df: pl.DataFrame | None) -> dict[str, float]:
    if df is None or df.is_empty():
        return {}
    grouped = (
        df.filter(pl.col("amount") < 0)
        .with_columns(pl.col("category").fill_null(UNCLASSIFIED), pl.col("amount").abs())
        .group_by("category")
        .agg(pl.col("amount").sum())
    )
    return {row["category"]: float(row["amount"]) for row in grouped.to_dicts()}


def spending_table(
    current: pl.DataFrame,
    previous: pl.DataFrame | None,
    group_map: dict[str, str],
) -> pl.DataFrame:
    """Une ligne par catégorie de dépense.

    Colonnes : group, category, total, pct, previous, delta, delta_pct (None si la
    catégorie n'avait aucune dépense la période précédente). Triée par montant décroissant.
    """
    now = _expenses_by_category(current)
    before = _expenses_by_category(previous)
    schema = {
        "group": pl.Utf8, "category": pl.Utf8, "total": pl.Float64, "pct": pl.Float64,
        "previous": pl.Float64, "delta": pl.Float64, "delta_pct": pl.Float64,
    }
    if not now:
        return pl.DataFrame(schema=schema)

    grand_total = sum(now.values())
    rows = []
    for category, total in now.items():
        prev = before.get(category, 0.0)
        rows.append({
            "group": display_group(category, group_map),
            "category": category,
            "total": round(total, 2),
            "pct": round(total / grand_total * 100, 1) if grand_total else 0.0,
            "previous": round(prev, 2),
            "delta": round(total - prev, 2),
            "delta_pct": round((total - prev) / prev * 100, 1) if prev else None,
        })
    return pl.DataFrame(rows, schema=schema).sort("total", descending=True)


def by_group(table: pl.DataFrame) -> pl.DataFrame:
    """Une ligne par groupe : group, total, pct, previous, delta, delta_pct."""
    if table.is_empty():
        return pl.DataFrame(schema={
            "group": pl.Utf8, "total": pl.Float64, "pct": pl.Float64,
            "previous": pl.Float64, "delta": pl.Float64, "delta_pct": pl.Float64,
        })
    grouped = table.group_by("group").agg(
        pl.col("total").sum(), pl.col("pct").sum().round(1), pl.col("previous").sum(),
    )
    return grouped.with_columns(
        (pl.col("total") - pl.col("previous")).round(2).alias("delta"),
        pl.when(pl.col("previous") > 0)
        .then(((pl.col("total") - pl.col("previous")) / pl.col("previous") * 100).round(1))
        .otherwise(None)
        .alias("delta_pct"),
    ).sort("total", descending=True)


def format_delta(delta: float | None, delta_pct: float | None) -> str:
    """« ▲ +120 € (+12 %) », « ▼ −40 € (−8 %) » ou « — » : des flèches, sans connotation
    bon/mauvais (une dépense qui monte n'est pas forcément un problème)."""
    if delta is None or abs(delta) < 0.5:
        return "—"
    arrow, sign = ("▲", "+") if delta > 0 else ("▼", "−")
    amount = f"{sign}{abs(delta):,.0f} €".replace(",", " ")
    if delta_pct is None:
        return f"{arrow} {amount} (nouveau)"
    return f"{arrow} {amount} ({sign}{abs(delta_pct):.0f} %)"


def household_overview(perso_df: pl.DataFrame, foyer_df: pl.DataFrame) -> pl.DataFrame:
    """Dépenses du couple : tes dépenses perso + les dépenses communes du foyer.

    Ta participation (catégorie « Loyer » du budget perso) n'est comptée qu'une fois : elle
    est retirée du perso pour les mois où le foyer a ses propres dépenses (prêt, charges…).
    Les achats perso et l'épargne de Bruno, et les opérations exceptionnelles, sont exclus.

    Returns:
        DataFrame (date, amount, category) de dépenses et rentrées, prêt pour spending_table.
    """
    columns = ["date", "amount", "category"]
    foyer = common_expenses(regular_operations(foyer_df)) if not foyer_df.is_empty() else foyer_df
    foyer_months = (
        set(zip(foyer["date"].dt.year().to_list(), foyer["date"].dt.month().to_list(), strict=True))
        if not foyer.is_empty() else set()
    )

    perso = perso_df
    if not perso.is_empty() and foyer_months:
        keys = list(zip(perso["date"].dt.year().to_list(), perso["date"].dt.month().to_list(), strict=True))
        in_foyer_month = pl.Series([key in foyer_months for key in keys])
        perso = perso.filter(~((pl.col("category") == PARTICIPATION_CATEGORY) & in_foyer_month))

    frames = [f.select(columns) for f in (perso, foyer) if not f.is_empty()]
    if not frames:
        return pl.DataFrame(schema={"date": pl.Date, "amount": pl.Float64, "category": pl.Utf8})
    return pl.concat(frames, how="diagonal_relaxed")
