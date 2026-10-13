"""Page À traiter — opérations importées à classer, règles apprises, contrôle des comptes."""

import polars as pl
import streamlit as st

from app.components.auth import require_auth
from app.components.reconciliation_section import render_reconciliation_section
from src.config import BusinessId
from src.logic.categorizer import apply_rules
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
    all_df = read_transactions(include_household=True, include_transfers=True)
    accounts = fetch_accounts()
except Exception as exc:
    st.error(f"Impossible de charger les données : {exc}")
    st.stop()

account_names = {a["id"]: a["name"] for a in accounts}
pending_df = pending_transactions(all_df)
n_review = all_df.filter(pl.col("needs_review")).height if not all_df.is_empty() else 0

# ---------------------------------------------------------------------------
# Opérations à vérifier (page Sync)
# ---------------------------------------------------------------------------
if n_review:
    st.warning(
        f"{n_review} opération(s) du compte commun ou virement(s) à vérifier sur la page Sync."
    )
    st.page_link("pages/7_Sync.py", label="Aller à la page Sync", icon="🔄")

# ---------------------------------------------------------------------------
# Opérations à classer
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
    suggestions = category_suggestions_from_history(all_df)

    for business_id, business_label in _BUSINESS_LABELS.items():
        biz_pending = pending_df.filter(pl.col("business_id") == business_id)
        if biz_pending.is_empty():
            continue
        categories = read_categories(business_id=business_id)

        for direction, direction_label in _DIRECTIONS.items():
            rows_df = biz_pending.filter(
                pl.col("amount") < 0 if direction == "expense" else pl.col("amount") > 0
            )
            if rows_df.is_empty():
                continue
            allowed = (
                sorted(categories.filter(pl.col("direction") == direction)["name"].to_list())
                if not categories.is_empty() else []
            )
            rows = rows_df.sort("date", descending=True).to_dicts()
            suggested = [suggest_category(r, suggestions, allowed) for r in rows]

            key = f"inbox_{business_id}_{direction}"
            st.markdown(f"**{business_label} — {direction_label}** ({len(rows)})")
            editor_df = pl.DataFrame({
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
            }, schema_overrides={"Catégorie": pl.Utf8})
            edited = st.data_editor(
                editor_df.to_pandas(),
                hide_index=True,
                width="stretch",
                disabled=["id", "Date", "Compte", "Libellé banque", "Montant", "Catégorie banque", "✨"],
                column_config={
                    "id": None,
                    "Montant": st.column_config.NumberColumn(format="%.2f €"),
                    "Catégorie": st.column_config.SelectboxColumn(options=allowed),
                    "Règle": st.column_config.CheckboxColumn(help="Classer automatiquement les prochaines"),
                    "Motif": st.column_config.TextColumn(help="Texte recherché dans le libellé"),
                },
                key=key,
            )

            if st.button("Enregistrer", key=f"{key}_save", type="primary"):
                originals = {r["id"]: r for r in rows}
                saved_ids: set[str] = set()
                new_rules: list[dict] = []
                try:
                    for row in edited.to_dict("records"):
                        category = row["Catégorie"] if isinstance(row["Catégorie"], str) else None
                        label = (row["Libellé"] or "").strip()
                        updates = {}
                        if category:
                            updates["category"] = category
                        if label and label != originals[row["id"]]["label"]:
                            updates["label"] = label
                        if updates:
                            update_transaction(row["id"], updates)
                            saved_ids.add(row["id"])
                        motif = (row["Motif"] or "").strip()
                        if row["Règle"] and category and motif:
                            new_rules.append(build_rule(motif, category, business_id))

                    for rule in new_rules:
                        insert_categorization_rule(rule)

                    # Les nouvelles règles classent aussitôt les autres opérations en attente
                    n_auto = 0
                    if new_rules:
                        rest = pending_df.filter(~pl.col("id").is_in(list(saved_ids)))
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

st.divider()

# ---------------------------------------------------------------------------
# Contrôle des comptes
# ---------------------------------------------------------------------------
render_reconciliation_section(accounts)
