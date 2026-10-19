"""Page Règles — voir, corriger et tester les règles qui rangent automatiquement les opérations."""

import polars as pl
import streamlit as st

from app.components.auth import require_auth
from app.components.help import page_title, section_title
from src.logic.inbox import USER_RULE_PRIORITY, build_rule, inbox_rows, rule_updates
from src.logic.rules import (
    BUDGET_LABELS,
    DIRECTION_LABELS,
    TARGET_LABELS,
    diff_rules,
    rule_stats,
    sort_rules,
    which_rule,
)
from src.services.db_reader import invalidate_cache, read_categories, read_transactions
from src.services.supabase import (
    bulk_update_transaction_fields,
    delete_categorization_rule,
    fetch_all_categorization_rules,
    insert_categorization_rule,
    update_categorization_rule,
)

st.set_page_config(page_title="Règles", page_icon="🧭", layout="wide")
require_auth()
page_title("Règles", "regles")
st.caption(
    "Une règle range automatiquement les opérations importées dont le libellé contient son "
    "**motif** : elle donne une catégorie et, si tu le précises, un autre budget. Quand plusieurs "
    "règles s'appliquent, **la plus prioritaire gagne** (priorité haute = appliquée en premier). "
    "Les règles créées depuis « À traiter » ont la priorité 200."
)

_MESSAGES_KEY = "_rules_messages"
for kind, text in st.session_state.pop(_MESSAGES_KEY, []):
    getattr(st, kind)(text)
version = st.session_state.setdefault("_rules_version", 0)

try:
    rules = sort_rules(fetch_all_categorization_rules())
    transactions_df = read_transactions(include_transfers=True)
    categories_df = read_categories()
except Exception as exc:
    st.error(f"Impossible de charger les règles : {exc}")
    st.stop()

category_names = sorted(categories_df["name"].unique().to_list()) if not categories_df.is_empty() else []
transactions = transactions_df.to_dicts() if not transactions_df.is_empty() else []
stats = rule_stats(rules, transactions)

# ---------------------------------------------------------------------------
# Tableau des règles
# ---------------------------------------------------------------------------
n_active = sum(1 for r in rules if r.get("is_active", True))
n_shadowed = sum(
    1 for r in rules
    if r.get("is_active", True) and stats[r["id"]]["matches"] and not stats[r["id"]]["wins"]
)
col_a, col_b, col_c = st.columns(3)
col_a.metric("Règles", len(rules), help=f"{n_active} active(s)")
col_b.metric("Masquées", n_shadowed, help="Actives, avec des correspondances, mais toujours battues par une règle plus prioritaire")
col_c.metric("Jamais utilisées", sum(1 for r in rules if not stats[r["id"]]["matches"]))

if not rules:
    st.info("Aucune règle pour l'instant : elles se créent depuis la page « À traiter » (case Règle).")
else:
    st.subheader("Mes règles")
    editor_df = pl.DataFrame({
        "id": [r["id"] for r in rules],
        "Motif": [r["pattern"] for r in rules],
        "Budget visé": [BUDGET_LABELS.get(r.get("business_id"), "?") for r in rules],
        "Sens": [DIRECTION_LABELS.get(r.get("direction"), "Les deux") for r in rules],
        "Catégorie": [r["category"] for r in rules],
        "Ranger dans": [TARGET_LABELS.get(r.get("target_business_id"), "Reste dans son budget") for r in rules],
        "Priorité": [int(r.get("priority") or 0) for r in rules],
        "Actif": [bool(r.get("is_active", True)) for r in rules],
        "Opérations": [stats[r["id"]]["matches"] for r in rules],
        "Appliquée à": [stats[r["id"]]["wins"] for r in rules],
        "Supprimer": [False] * len(rules),
    })
    edited = st.data_editor(
        editor_df.to_pandas(),
        hide_index=True,
        width="stretch",
        disabled=["id", "Opérations", "Appliquée à"],
        column_config={
            "id": None,
            "Budget visé": st.column_config.SelectboxColumn(options=list(BUDGET_LABELS.values()), required=True),
            "Sens": st.column_config.SelectboxColumn(options=list(DIRECTION_LABELS.values()), required=True),
            "Catégorie": st.column_config.SelectboxColumn(options=category_names, required=True),
            "Ranger dans": st.column_config.SelectboxColumn(options=list(TARGET_LABELS.values()), required=True),
            "Priorité": st.column_config.NumberColumn(step=1, format="%d"),
            "Opérations": st.column_config.NumberColumn(
                help="Opérations dont le libellé contient le motif (toutes périodes)"
            ),
            "Appliquée à": st.column_config.NumberColumn(
                help="Opérations pour lesquelles cette règle est la gagnante. 0 avec des "
                     "opérations à gauche : une règle plus prioritaire la masque."
            ),
        },
        key=f"rules_editor_v{version}",
    )
    if st.button("Enregistrer les modifications", type="primary", key="rules_save"):
        updates, deletes, errors = diff_rules(rules, edited.to_dict("records"))
        try:
            for rule_id, fields in updates.items():
                update_categorization_rule(rule_id, fields)
            for rule_id in deletes:
                delete_categorization_rule(rule_id)
            st.session_state[_MESSAGES_KEY] = [("warning", e) for e in errors] + [
                ("success", f"{len(updates)} règle(s) modifiée(s), {len(deletes)} supprimée(s).")
            ]
            st.session_state["_rules_version"] = version + 1
            st.rerun()
        except Exception as exc:
            st.error(f"Erreur : {exc}")

st.divider()

# ---------------------------------------------------------------------------
# Tester un libellé
# ---------------------------------------------------------------------------
section_title("Tester un libellé", "regles_test")
st.caption("Colle un libellé de ton relevé pour voir quelle règle le rangerait, et comment.")
col_label, col_budget, col_amount = st.columns([3, 1, 1])
test_text = col_label.text_input("Libellé", placeholder="PAIEMENT CB 0810 LYON DELIVEROO CARTE 3935", key="rules_test_label")
test_budget = col_budget.selectbox("Budget de la ligne", ["Foyer", "Perso", "Phi Rising", "Booth in Lyon"], key="rules_test_budget")
test_sign = col_amount.selectbox("Sens", ["Dépense", "Revenu"], key="rules_test_sign")
if test_text:
    business = {"Foyer": "household", "Perso": "personal", "Phi Rising": "phi_rising",
                "Booth in Lyon": "booth_in_lyon"}[test_budget]
    winner = which_rule(rules, test_text, business, 1.0 if test_sign == "Revenu" else -1.0)
    if winner is None:
        st.info("Aucune règle ne range ce libellé : il arriverait dans « À traiter ».")
    else:
        target = TARGET_LABELS.get(winner.get("target_business_id"))
        st.success(
            f"Règle **« {winner['pattern']} »** (priorité {winner.get('priority')}) → catégorie "
            f"**{winner['category']}**" + (f", budget **{target}**." if winner.get("target_business_id") else ".")
        )

st.divider()

# ---------------------------------------------------------------------------
# Nouvelle règle
# ---------------------------------------------------------------------------
st.subheader("Nouvelle règle")
with st.form("rules_new", clear_on_submit=True):
    col_p, col_c = st.columns(2)
    new_pattern = col_p.text_input("Motif", placeholder="DELIVEROO")
    new_category = col_c.selectbox("Catégorie", category_names, index=None, placeholder="Choisir…")
    col_b, col_d, col_t, col_pr = st.columns(4)
    new_budget = col_b.selectbox("Budget visé", list(BUDGET_LABELS.values()), index=1)
    new_direction = col_d.selectbox("Sens", list(DIRECTION_LABELS.values()), index=1)
    new_target = col_t.selectbox("Ranger dans", list(TARGET_LABELS.values()))
    new_priority = col_pr.number_input("Priorité", value=USER_RULE_PRIORITY, step=10)
    if st.form_submit_button("Créer la règle"):
        if not new_pattern.strip() or not new_category:
            st.error("Le motif et la catégorie sont obligatoires.")
        else:
            by_label = {label: key for key, label in BUDGET_LABELS.items()}
            direction_by_label = {label: key for key, label in DIRECTION_LABELS.items()}
            target_by_label = {label: key for key, label in TARGET_LABELS.items()}
            rule = build_rule(
                new_pattern, new_category, by_label[new_budget], direction_by_label[new_direction],
                target_by_label[new_target],
            )
            rule["priority"] = int(new_priority)
            try:
                insert_categorization_rule(rule)
                st.session_state[_MESSAGES_KEY] = [("success", f"Règle « {new_pattern.strip()} » créée.")]
                st.session_state["_rules_version"] = version + 1
                st.rerun()
            except Exception as exc:
                st.error(f"Erreur : {exc}")

st.divider()

# ---------------------------------------------------------------------------
# Appliquer aux opérations non classées
# ---------------------------------------------------------------------------
section_title("Appliquer aux opérations déjà importées", "regles_apply")
st.caption(
    "Les règles s'appliquent automatiquement aux nouveaux imports. Ce bouton les applique aux "
    "opérations **sans catégorie** déjà en base, après un aperçu."
)
active_rules = [r for r in rules if r.get("is_active", True)]
pending = inbox_rows(transactions_df)
pending_uncategorized = (
    pending.filter(pl.col("category").is_null() | (pl.col("category") == "")) if not pending.is_empty() else pending
)
preview = rule_updates(pending_uncategorized, active_rules) if not pending_uncategorized.is_empty() else []
if not preview:
    st.info("Aucune opération en attente ne correspond aux règles actives.")
else:
    labels = {r["id"]: r["label"] for r in pending_uncategorized.to_dicts()}
    st.write(f"**{len(preview)} opération(s)** seraient rangées :")
    st.dataframe(
        pl.DataFrame([
            {"Libellé": labels[u["id"]], "Catégorie": u.get("category", ""),
             "Budget": BUDGET_LABELS.get(u.get("business_id"), "inchangé") if u.get("business_id") else "inchangé"}
            for u in preview
        ]).to_pandas(),
        hide_index=True, width="stretch",
    )
    if st.button(f"Appliquer à ces {len(preview)} opération(s)", key="rules_apply"):
        try:
            bulk_update_transaction_fields(preview)
            invalidate_cache()
            st.session_state[_MESSAGES_KEY] = [("success", f"{len(preview)} opération(s) rangée(s).")]
            st.session_state["_rules_version"] = version + 1
            st.rerun()
        except Exception as exc:
            st.error(f"Erreur : {exc}")
