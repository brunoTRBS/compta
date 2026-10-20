"""Page À classer — la boîte de réception unique : tout ce qui demande un geste après un import."""

import math
from typing import Any

import polars as pl
import streamlit as st

from app.components.auth import require_auth
from app.components.help import page_title
from app.components.reconciliation_section import render_reconciliation_section
from src.config import BusinessId
from src.logic.household_budget import retro_classify
from src.logic.import_pipeline import match_manual_entries
from src.logic.inbox import (
    AFFECTATIONS,
    COL_ACCOUNT,
    COL_AMOUNT,
    COL_BANK_CATEGORY,
    COL_BANK_LABEL,
    COL_CATEGORY,
    COL_COUNTS_FOR,
    COL_DATE,
    COL_FROM,
    COL_LABEL,
    COL_OFF_MONTH,
    COL_PATTERN,
    COL_REASON,
    COL_RULE,
    COL_SUGGESTED,
    COL_TO,
    account_label,
    category_suggestions_from_history,
    inbox_rows,
    inbox_table,
    plan_inbox_changes,
    rule_updates,
    visible_columns,
)
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

st.set_page_config(page_title="À classer", page_icon="📥", layout="wide")
require_auth()
page_title("À classer", "a_traiter")

_MESSAGES_KEY = "_inbox_messages"
_VERSION_KEY = "_inbox_version"
# La participation peut être saisie à la main n'importe quand dans le mois
_PARTICIPATION_MATCH_WINDOW_DAYS = 10

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

categories: dict[str, dict[str, set[str]]] = {}
for cat in categories_df.to_dicts() if not categories_df.is_empty() else []:
    categories.setdefault(cat["business_id"], {}).setdefault(cat["direction"], set()).add(cat["name"])
suggestions = category_suggestions_from_history(all_df)

inbox_df = inbox_rows(all_df)
rows = inbox_df.to_dicts() if not inbox_df.is_empty() else []

# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------
col_a, col_b = st.columns([1, 3])
col_a.metric("À classer", len(rows))
with col_b:
    st.page_link("pages/7_Sync.py", label="Importer un relevé", icon="🔄")

if not rows:
    st.success("Tout est classé. 🎉")
else:
    st.markdown(
        "Pour chaque ligne : choisis **pour qui elle compte** et sa **catégorie**, "
        "puis clique sur **Enregistrer**. Les lignes avec ✨ sont déjà proposées : "
        "tu peux les garder telles quelles."
    )
    details = st.toggle(
        "Plus de détails", key="inbox_details",
        help="Libellé de la banque, mot reconnu, « ne pas compter dans le mois », "
             "et le choix de l'autre compte d'un virement.",
    )

    table = inbox_table(rows, accounts, categories, suggestions)
    shown = visible_columns(table, details)
    all_account_labels = [account_label(a) for a in accounts]
    category_options = sorted({
        name for by_direction in categories.values() for names in by_direction.values() for name in names
    })
    always_locked = [
        "id", COL_REASON, COL_DATE, COL_ACCOUNT, COL_AMOUNT, COL_SUGGESTED, COL_BANK_LABEL,
        COL_BANK_CATEGORY,
    ]
    frame = st.data_editor(
        pl.DataFrame(
            {name: table[name] for name in shown},
            schema_overrides={COL_CATEGORY: pl.Utf8, COL_FROM: pl.Utf8, COL_TO: pl.Utf8},
        ).to_pandas(),
        hide_index=True,
        width="stretch",
        disabled=[name for name in always_locked if name in shown],
        column_config={
            "id": None,
            COL_AMOUNT: st.column_config.NumberColumn(format="%.2f €"),
            COL_COUNTS_FOR: st.column_config.SelectboxColumn(
                options=list(AFFECTATIONS.values()), required=True,
                help="Le budget où cette ligne compte. Par défaut : celui du compte.",
            ),
            COL_CATEGORY: st.column_config.SelectboxColumn(options=category_options),
            COL_RULE: st.column_config.CheckboxColumn(
                help="Les prochaines lignes avec le même mot seront rangées toutes seules."
            ),
            COL_FROM: st.column_config.SelectboxColumn(
                options=all_account_labels, help="Le compte d'où l'argent est parti."
            ),
            COL_TO: st.column_config.SelectboxColumn(
                options=all_account_labels, help="Le compte où l'argent est arrivé."
            ),
            COL_PATTERN: st.column_config.TextColumn(help="Le mot cherché dans le libellé de la banque."),
            COL_OFF_MONTH: st.column_config.CheckboxColumn(
                help="Pour une dépense ou une rentrée hors du quotidien (apport, caution, erreur…) : "
                     "affichée à part dans le budget du foyer."
            ),
        },
        key=f"inbox_v{version}_{int(details)}",
    )

    if st.button("✅ Enregistrer", type="primary", key="inbox_save"):
        edited_records = [{k: _clean(v) for k, v in record.items()} for record in frame.to_dict("records")]
        # Colonnes masquées : on reprend le mot reconnu proposé pour « Pareil la prochaine fois »
        default_patterns = dict(zip(table["id"], table[COL_PATTERN], strict=True))
        for record in edited_records:
            record.setdefault(COL_PATTERN, default_patterns.get(record["id"]))
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
