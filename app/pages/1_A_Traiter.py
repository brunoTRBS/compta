"""Page À traiter — la boîte de réception unique : tout ce qui demande un geste après un import."""

import math
from typing import Any

import polars as pl
import streamlit as st

from app.components.auth import require_auth
from app.components.help import page_title
from app.components.reconciliation_section import render_reconciliation_section
from src.config import BusinessId
from src.logic.household import propose_exceptional
from src.logic.household_budget import retro_classify
from src.logic.import_pipeline import match_manual_entries
from src.logic.inbox import (
    AFFECTATIONS,
    TRANSFER,
    account_label,
    category_suggestions_from_history,
    inbox_reason,
    inbox_rows,
    plan_inbox_changes,
    proposed_affectation,
    rule_updates,
    suggest_category,
    suggest_pattern,
)
from src.logic.transfers import default_counterpart
from src.services.db_reader import (
    invalidate_cache,
    read_categories,
    read_manual_candidates,
    read_transactions,
)
from src.services.supabase import (
    bulk_update_transaction_fields,
    bulk_upsert_transactions,
    fetch_accounts,
    fetch_categorization_rules,
    insert_categorization_rule,
    insert_transactions,
    link_transactions_to_bank,
)

st.set_page_config(page_title="À traiter", page_icon="📥", layout="wide")
require_auth()
page_title("À traiter", "a_traiter")

_MESSAGES_KEY = "_inbox_messages"
_VERSION_KEY = "_inbox_version"
# La participation peut être saisie à la main n'importe quand dans le mois
_PARTICIPATION_MATCH_WINDOW_DAYS = 10
_ICONS = {
    TRANSFER: "🔁",
    str(BusinessId.HOUSEHOLD): "🏠",
    str(BusinessId.PERSONAL): "👤",
    str(BusinessId.PHI_RISING): "💼",
    str(BusinessId.BOOTH_IN_LYON): "📸",
}

# Messages laissés par l'enregistrement précédent (la page est rechargée après)
for kind, text in st.session_state.pop(_MESSAGES_KEY, []):
    getattr(st, kind)(text)
version = st.session_state.setdefault(_VERSION_KEY, 0)


def _clean(value: Any) -> Any:
    """Valeur d'une cellule du tableau : None pour une cellule vide (NaN, texte vide)."""
    if value is None or value == "":
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


try:
    all_df = read_transactions(include_transfers=True)
    accounts = fetch_accounts()
    categories_df = read_categories()
except Exception as exc:
    st.error(f"Impossible de charger les données : {exc}")
    st.stop()

account_names = {a["id"]: a["name"] for a in accounts}
categories: dict[str, dict[str, set[str]]] = {}
for cat in categories_df.to_dicts() if not categories_df.is_empty() else []:
    categories.setdefault(cat["business_id"], {}).setdefault(cat["direction"], set()).add(cat["name"])
suggestions = category_suggestions_from_history(all_df)

inbox_df = inbox_rows(all_df)
rows = inbox_df.to_dicts() if not inbox_df.is_empty() else []
n_review = sum(1 for r in rows if r.get("needs_review"))

# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
col_a, col_b, col_c = st.columns([1, 1, 2])
col_a.metric("À traiter", len(rows))
col_b.metric("Dont à vérifier", n_review, help="Ta carte sur le commun, ta participation, virements")
with col_c:
    st.page_link("pages/7_Sync.py", label="Importer un relevé", icon="🔄")

if not rows:
    st.success("Tout est classé. 🎉")
else:
    st.caption(
        "Chaque ligne a une **affectation** (le budget où elle compte) et une **catégorie**. "
        "Corrige ce qui est faux, puis **Enregistrer** : les lignes à vérifier laissées telles "
        "quelles sont validées. ✨ = catégorie suggérée d'après tes choix passés. Coche **Règle** "
        "pour que les prochaines opérations avec ce motif se rangent seules (si tu as changé "
        "l'affectation, la règle la change aussi). Un virement reçu classé « Participation "
        "Charlotte » crée ta dépense « Participation foyer » dans ton budget perso."
    )

    transfer_options = [account_label(a) for a in accounts]
    affectation_labels = list(AFFECTATIONS.values())
    frames: dict[str, Any] = {}

    for key, label in AFFECTATIONS.items():
        block = [r for r in rows if proposed_affectation(r) == key]
        if not block:
            continue
        block.sort(key=lambda r: (not r.get("needs_review"), -r["date"].toordinal()))
        is_household = key == str(BusinessId.HOUSEHOLD)
        is_transfer = key == TRANSFER
        scope_cats = categories.get(key, {})
        category_options = sorted(scope_cats.get("expense", set()) | scope_cats.get("income", set()))

        suggested = []
        for r in block:
            direction = "income" if r["amount"] > 0 else "expense"
            suggested.append(
                suggest_category(r, suggestions, sorted(categories.get(r["business_id"], {}).get(direction, set())))
            )

        counterparts = []
        for r in block:
            account = default_counterpart(r, accounts) if is_transfer else None
            counterparts.append(account_label(account) if account else None)

        columns: dict[str, list[Any]] = {
            "id": [r["id"] for r in block],
            "Type": [inbox_reason(r) for r in block],
            "Date": [r["date"] for r in block],
            "Compte": [account_names.get(r["account_id"], "—") for r in block],
            "Libellé": [r["label"] for r in block],
            "Libellé banque": [r.get("raw_label") or "" for r in block],
            "Montant": [r["amount"] for r in block],
            "Affectation": [label] * len(block),
            "Autre compte": counterparts,
        }
        if not is_transfer:
            columns |= {
                "Catégorie banque": [r.get("bank_category") or "" for r in block],
                "✨": ["✨" if s and not r.get("category") else "" for r, s in zip(block, suggested, strict=True)],
                "Catégorie": [r.get("category") or s for r, s in zip(block, suggested, strict=True)],
            }
            if is_household:
                columns["Exceptionnel"] = [
                    bool(r.get("is_exceptional")) or propose_exceptional(r) for r in block
                ]
            columns |= {"Règle": [False] * len(block), "Motif": [suggest_pattern(r) for r in block]}

        st.markdown(f"#### {_ICONS[key]} {label} ({len(block)})")
        frames[key] = st.data_editor(
            pl.DataFrame(columns, schema_overrides={"Catégorie": pl.Utf8, "Autre compte": pl.Utf8}).to_pandas(),
            hide_index=True,
            width="stretch",
            disabled=["id", "Type", "Date", "Compte", "Libellé banque", "Montant", "Catégorie banque", "✨"],
            column_config={
                "id": None,
                "Montant": st.column_config.NumberColumn(format="%.2f €"),
                "Affectation": st.column_config.SelectboxColumn(options=affectation_labels, required=True),
                "Autre compte": st.column_config.SelectboxColumn(
                    options=transfer_options, help="Pour un virement interne : l'autre compte"
                ),
                "Catégorie": st.column_config.SelectboxColumn(options=category_options),
                "Exceptionnel": st.column_config.CheckboxColumn(
                    help="Hors budget courant (apport, caution, erreur…) : affiché à part"
                ),
                "Règle": st.column_config.CheckboxColumn(help="Ranger les prochaines automatiquement"),
                "Motif": st.column_config.TextColumn(help="Texte recherché dans le libellé"),
            },
            key=f"inbox_{key}_v{version}",
        )

    if st.button("✅ Enregistrer", type="primary", key="inbox_save"):
        edited_records = [
            {k: _clean(v) for k, v in record.items()}
            for frame in frames.values()
            for record in frame.to_dict("records")
        ]
        plan = plan_inbox_changes(rows, edited_records, accounts, categories)
        try:
            insert_transactions(plan.legs)
            bulk_update_transaction_fields(plan.updates)

            n_already_entered = 0
            if plan.participations:
                # Une participation déjà saisie à la main n'est pas recréée : la saisie
                # reçoit juste la référence bancaire.
                candidates = [
                    c for c in read_manual_candidates(
                        str(BusinessId.PERSONAL), plan.participations, _PARTICIPATION_MATCH_WINDOW_DAYS,
                    )
                    if c["amount"] < 0
                ]
                to_insert, links = match_manual_entries(
                    [{**p, "account_id": None} for p in plan.participations],
                    candidates,
                    window_days=_PARTICIPATION_MATCH_WINDOW_DAYS,
                )
                link_transactions_to_bank(links)
                kept = {p["external_id"] for p in to_insert}
                bulk_upsert_transactions([p for p in plan.participations if p["external_id"] in kept])
                n_already_entered = len(links)

            for rule in plan.rules:
                insert_categorization_rule(rule)

            # Les nouvelles règles rangent aussitôt les autres lignes en attente
            n_auto = 0
            if plan.rules:
                saved_ids = {u["id"] for u in plan.updates}
                rest = inbox_df.filter(~pl.col("id").is_in(list(saved_ids)))
                auto = rule_updates(rest, fetch_categorization_rules())
                bulk_update_transaction_fields(auto)
                n_auto = len(auto)

            invalidate_cache()
            summary = (
                f"{len(plan.updates)} ligne(s) enregistrée(s), {len(plan.legs)} virement(s), "
                f"{len(plan.participations)} participation(s) (dont {n_already_entered} déjà saisie(s)), "
                f"{len(plan.rules)} règle(s) créée(s), {n_auto} autre(s) rangée(s) automatiquement."
            )
            st.session_state[_MESSAGES_KEY] = [("warning", e) for e in plan.errors] + [("success", summary)]
            st.session_state[_VERSION_KEY] = version + 1
            st.rerun()
        except Exception as exc:
            st.error(f"Erreur lors de l'enregistrement : {exc}")
            for error in plan.errors:
                st.warning(error)

st.divider()

# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------
with st.expander("🛠️ Outils"):
    st.caption(
        "**Classer l'historique du foyer** applique les règles aux opérations du compte commun "
        "déjà importées, repère les opérations exceptionnelles (gros montants) et annule les "
        "virements rejetés."
    )
    if st.button("⚡ Classer l'historique du foyer", key="household_retro"):
        try:
            household_all = all_df.filter(
                (pl.col("business_id") == str(BusinessId.HOUSEHOLD))
                & ~pl.col("is_transfer").fill_null(False)
            )
            updates = retro_classify(household_all, fetch_categorization_rules())
            bulk_update_transaction_fields(updates)
            invalidate_cache()
            st.session_state[_MESSAGES_KEY] = [
                ("success", f"{len(updates)} opération(s) du foyer mise(s) à jour.")
            ]
            st.session_state[_VERSION_KEY] = version + 1
            st.rerun()
        except Exception as exc:
            st.error(f"Erreur : {exc}")

# ---------------------------------------------------------------------------
# Contrôle des comptes
# ---------------------------------------------------------------------------
render_reconciliation_section(accounts)
