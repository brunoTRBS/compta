"""Page À traiter — opérations importées à classer, règles apprises, contrôle des comptes."""

from typing import Any

import polars as pl
import streamlit as st

from app.components.auth import require_auth
from app.components.reconciliation_section import render_reconciliation_section
from src.config import BusinessId
from src.logic.categorizer import apply_rules
from src.logic.household import propose_exceptional
from src.logic.household_budget import retro_classify
from src.logic.inbox import (
    build_rule,
    category_suggestions_from_history,
    pending_transactions,
    suggest_category,
    suggest_pattern,
)
from src.services.db_reader import invalidate_cache, read_categories, read_transactions
from src.services.supabase import (
    bulk_update_categories,
    bulk_update_transaction_fields,
    fetch_accounts,
    fetch_categorization_rules,
    insert_categorization_rule,
    update_transaction,
)

st.set_page_config(page_title="À traiter", page_icon="📥", layout="wide")
require_auth()
st.title("À traiter")

_BUSINESS_LABELS = {
    str(BusinessId.PERSONAL): "Perso",
    str(BusinessId.PHI_RISING): "Phi Rising",
    str(BusinessId.BOOTH_IN_LYON): "Booth in Lyon",
}
_DIRECTIONS = {"expense": "Dépenses", "income": "Revenus"}

try:
    all_df = read_transactions(include_transfers=True)
    accounts = fetch_accounts()
except Exception as exc:
    st.error(f"Impossible de charger les données : {exc}")
    st.stop()

account_names = {a["id"]: a["name"] for a in accounts}
pending_df = pending_transactions(all_df)
household_pending_df = pending_transactions(all_df, household=True)
n_review = all_df.filter(pl.col("needs_review")).height if not all_df.is_empty() else 0
suggestions = category_suggestions_from_history(all_df)


def _render_block(
    rows_df: pl.DataFrame,
    pending_pool: pl.DataFrame,
    business_id: str,
    direction: str,
    title: str,
) -> None:
    """Tableau de classement d'un groupe d'opérations (une activité, un sens)."""
    household = business_id == str(BusinessId.HOUSEHOLD)
    categories = read_categories(business_id=business_id)
    allowed = (
        sorted(categories.filter(pl.col("direction") == direction)["name"].to_list())
        if not categories.is_empty() else []
    )
    rows = rows_df.sort("date", descending=True).to_dicts()
    suggested = [suggest_category(r, suggestions, allowed) for r in rows]

    key = f"inbox_{business_id}_{direction}"
    st.markdown(f"**{title}** ({len(rows)})")
    columns: dict[str, list[Any]] = {
        "id": [r["id"] for r in rows],
        "Date": [r["date"] for r in rows],
        "Compte": [account_names.get(r["account_id"], "—") for r in rows],
        "Libellé": [r["label"] for r in rows],
        "Libellé banque": [r.get("raw_label") or "" for r in rows],
        "Montant": [abs(r["amount"]) for r in rows],
        "Catégorie banque": [r.get("bank_category") or "" for r in rows],
        "✨": ["✨" if s else "" for s in suggested],
        "Catégorie": suggested,
        "Règle": [False] * len(rows),
        "Motif": [suggest_pattern(r) for r in rows],
    }
    if household:
        columns["Exceptionnel"] = [bool(r.get("is_exceptional")) or propose_exceptional(r) for r in rows]
    editor_df = pl.DataFrame(columns, schema_overrides={"Catégorie": pl.Utf8})
    edited = st.data_editor(
        editor_df.to_pandas(),
        hide_index=True,
        width="stretch",
        disabled=["id", "Date", "Compte", "Libellé banque", "Montant", "Catégorie banque", "✨"],
        column_config={
            "id": None,
            "Compte": None if household else st.column_config.TextColumn(),
            "Montant": st.column_config.NumberColumn(format="%.2f €"),
            "Catégorie": st.column_config.SelectboxColumn(options=allowed),
            "Règle": st.column_config.CheckboxColumn(help="Classer automatiquement les prochaines"),
            "Motif": st.column_config.TextColumn(help="Texte recherché dans le libellé"),
            "Exceptionnel": st.column_config.CheckboxColumn(
                help="Hors budget courant (apport, caution…) : affiché à part"
            ),
        },
        key=key,
    )

    if not st.button("Enregistrer", key=f"{key}_save", type="primary"):
        return

    originals = {r["id"]: r for r in rows}
    saved_ids: set[str] = set()
    new_rules: list[dict] = []
    try:
        for row in edited.to_dict("records"):
            original = originals[row["id"]]
            category = row["Catégorie"] if isinstance(row["Catégorie"], str) else None
            label = (row["Libellé"] or "").strip()
            updates: dict[str, Any] = {}
            if category:
                updates["category"] = category
            if label and label != original["label"]:
                updates["label"] = label
            if household and bool(row["Exceptionnel"]) != bool(original.get("is_exceptional")):
                updates["is_exceptional"] = bool(row["Exceptionnel"])
            if updates:
                update_transaction(row["id"], updates)
                saved_ids.add(row["id"])
            motif = (row["Motif"] or "").strip()
            if row["Règle"] and category and motif:
                new_rules.append(build_rule(motif, category, business_id, direction))

        for rule in new_rules:
            insert_categorization_rule(rule)

        # Les nouvelles règles classent aussitôt les autres opérations en attente
        n_auto = 0
        if new_rules:
            rest = pending_pool.filter(~pl.col("id").is_in(list(saved_ids)))
            if not rest.is_empty():
                auto_df = apply_rules(rest, fetch_categorization_rules())
                auto = [
                    {"id": r["id"], "category": r["category"]}
                    for r in auto_df.iter_rows(named=True) if r.get("category")
                ]
                bulk_update_categories(auto)
                n_auto = len(auto)

        invalidate_cache()
        st.toast(
            f"{len(saved_ids)} opération(s) enregistrée(s), {len(new_rules)} règle(s) "
            f"créée(s), {n_auto} autre(s) classée(s) automatiquement.",
            icon="✅",
        )
        st.rerun()
    except Exception as exc:
        st.error(f"Erreur lors de l'enregistrement : {exc}")


# ---------------------------------------------------------------------------
# Opérations à vérifier (page Sync)
# ---------------------------------------------------------------------------
if n_review:
    st.warning(
        f"{n_review} opération(s) du compte commun ou virement(s) à vérifier sur la page Sync."
    )
    st.page_link("pages/7_Sync.py", label="Aller à la page Sync", icon="🔄")

# ---------------------------------------------------------------------------
# Budget perso et activités pro
# ---------------------------------------------------------------------------
st.subheader(f"🏷️ {pending_df.height} opération(s) à classer")

if pending_df.is_empty():
    st.success("Tout est classé. 🎉")
else:
    st.caption(
        "Choisis la catégorie ; ✨ = suggestion d'après tes choix passés, à vérifier. "
        "Coche **Règle** pour que les prochaines opérations avec ce motif se classent seules "
        "(le motif est modifiable : garde la partie qui identifie le commerçant). "
        "Tu peux aussi renommer un libellé peu clair."
    )
    for business_id, business_label in _BUSINESS_LABELS.items():
        biz_pending = pending_df.filter(pl.col("business_id") == business_id)
        for direction, direction_label in _DIRECTIONS.items():
            rows_df = biz_pending.filter(
                pl.col("amount") < 0 if direction == "expense" else pl.col("amount") > 0
            )
            if not rows_df.is_empty():
                _render_block(
                    rows_df, pending_df, business_id, direction,
                    f"{business_label} — {direction_label}",
                )

st.divider()

# ---------------------------------------------------------------------------
# Foyer (compte commun)
# ---------------------------------------------------------------------------
st.subheader(f"🏠 Foyer — {household_pending_df.height} opération(s) à classer")
st.caption(
    "Opérations du compte commun, avec les catégories du foyer. Leurs règles ne "
    "s'appliquent qu'au foyer, jamais à ton budget perso. Coche **Exceptionnel** pour "
    "sortir une opération du budget courant (apport, caution…)."
)

if st.button("⚡ Classer l'historique du foyer", key="household_retro",
             help="Applique les règles du foyer, repère les opérations exceptionnelles "
                  "et les virements rejetés parmi les opérations déjà importées."):
    try:
        household_all = all_df.filter(
            (pl.col("business_id") == str(BusinessId.HOUSEHOLD))
            & ~pl.col("is_transfer").fill_null(False)
        )
        updates = retro_classify(household_all, fetch_categorization_rules())
        bulk_update_transaction_fields(updates)
        invalidate_cache()
        st.toast(f"{len(updates)} opération(s) du foyer mise(s) à jour.", icon="✅")
        st.rerun()
    except Exception as exc:
        st.error(f"Erreur : {exc}")

if household_pending_df.is_empty():
    st.success("Tout le foyer est classé. 🎉")
else:
    for direction, direction_label in _DIRECTIONS.items():
        rows_df = household_pending_df.filter(
            pl.col("amount") < 0 if direction == "expense" else pl.col("amount") > 0
        )
        if not rows_df.is_empty():
            _render_block(
                rows_df, household_pending_df, str(BusinessId.HOUSEHOLD),
                direction, f"Foyer — {direction_label}",
            )

st.divider()

# ---------------------------------------------------------------------------
# Contrôle des comptes
# ---------------------------------------------------------------------------
render_reconciliation_section(accounts)
