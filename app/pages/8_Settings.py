"""Page Paramètres — catégories partagées, sauvegarde, statut des connexions, cache."""

from datetime import date

import polars as pl
import streamlit as st

from app.components.auth import require_auth
from app.components.help import page_title, section_title, tab_help
from src.logic.categories import (
    DEFAULT_GROUPS,
    GROUPS,
    NO_GROUP,
    SCOPE_LABELS,
    SHARED_SCOPES,
    SUGGESTED_RENAMES,
    diff_matrix,
    matrix_rows,
    validate_rename,
)
from src.services.db_reader import invalidate_cache
from src.services.supabase import (
    count_category_usage,
    delete_categories,
    fetch_all_transactions,
    fetch_categories,
    insert_categories,
    rename_or_merge_category,
    set_category_group,
)
from src.utils.health import HealthStatus, run_all_checks

st.set_page_config(page_title="Paramètres", page_icon="⚙️", layout="wide")
require_auth()
page_title("Paramètres", "settings")

# ---------------------------------------------------------------------------
# Catégories partagées
# ---------------------------------------------------------------------------
section_title("Catégories", "settings_categories")
st.caption(
    "Une liste commune à Mon budget, au foyer et aux activités pro, pour pouvoir comparer. "
    "Chaque catégorie est rangée dans un groupe (Logement, Alimentation…) : les graphiques "
    "montrent l'essentiel par groupe et le détail par catégorie."
)

try:
    all_categories = fetch_categories()
except Exception as exc:
    st.error(f"Impossible de charger les catégories : {exc}")
    all_categories = []

_DIRECTION_LABELS = {"expense": "Dépenses", "income": "Revenus"}
_SCOPE_COLUMNS = {scope: label for scope, label in SCOPE_LABELS.items()}
_known_groups = {c.get("group_name") for c in all_categories if c.get("group_name")}
_group_options = [NO_GROUP, *GROUPS, *sorted(_known_groups - set(GROUPS))]

tab_list, tab_cleanup, tab_rename = st.tabs(
    ["📋 Liste", "🧹 Remise en ordre", "✏️ Renommer / fusionner"]
)

# --- Liste : une ligne par catégorie, une case par budget ---------------------
with tab_list:
    tab_help("settings_liste")
    st.caption(
        "Coche les budgets où la catégorie est proposée. Décocher ne touche pas aux "
        "opérations déjà classées. Pour changer un nom, utilise l'onglet « Renommer / fusionner »."
    )
    for direction, direction_label in _DIRECTION_LABELS.items():
        rows = matrix_rows(all_categories, direction)
        st.markdown(f"**{direction_label}** ({len(rows)})")
        if not rows:
            st.caption("Aucune catégorie.")
            continue
        editor_df = pl.DataFrame({
            "Catégorie": [r["name"] for r in rows],
            "Groupe": [r["group"] for r in rows],
            **{label: [r[scope] for r in rows] for scope, label in _SCOPE_COLUMNS.items()},
        })
        edited = st.data_editor(
            editor_df.to_pandas(),
            hide_index=True,
            width="stretch",
            disabled=["Catégorie"],
            column_config={
                "Groupe": st.column_config.SelectboxColumn(options=_group_options, required=True),
                **{label: st.column_config.CheckboxColumn() for label in _SCOPE_COLUMNS.values()},
            },
            key=f"cat_matrix_{direction}",
        )
        if st.button("Enregistrer", key=f"cat_matrix_save_{direction}"):
            edited_rows = [
                {"name": r["Catégorie"], "group": r["Groupe"],
                 **{scope: bool(r[label]) for scope, label in _SCOPE_COLUMNS.items()}}
                for r in edited.to_dict("records")
            ]
            to_create, to_delete, group_changes = diff_matrix(all_categories, edited_rows, direction)
            try:
                insert_categories(to_create)
                delete_categories(to_delete)
                for name, group in group_changes.items():
                    set_category_group(name, None if group == NO_GROUP else group, direction)
                invalidate_cache()
                st.toast(
                    f"{len(to_create)} ajout(s), {len(to_delete)} retrait(s), "
                    f"{len(group_changes)} groupe(s) modifié(s).",
                    icon="✅",
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Erreur : {exc}")

    st.markdown("---")
    st.markdown("**Nouvelle catégorie**")
    with st.form("form_new_category", clear_on_submit=True):
        col_name, col_dir, col_group = st.columns([3, 2, 3])
        new_name = col_name.text_input("Nom", placeholder="Nom de la catégorie")
        new_direction = col_dir.selectbox(
            "Sens", list(_DIRECTION_LABELS), format_func=_DIRECTION_LABELS.get
        )
        new_group = col_group.selectbox("Groupe", _group_options)
        new_scopes = st.multiselect(
            "Budgets", list(SCOPE_LABELS), default=list(SHARED_SCOPES),
            format_func=SCOPE_LABELS.get,
        )
        if st.form_submit_button("Ajouter"):
            if not new_name.strip() or not new_scopes:
                st.error("Il faut un nom et au moins un budget.")
            else:
                try:
                    insert_categories([
                        {"business_id": scope, "name": new_name.strip(), "direction": new_direction,
                         "group_name": None if new_group == NO_GROUP else new_group}
                        for scope in new_scopes
                    ])
                    invalidate_cache()
                    st.toast(f"Catégorie « {new_name.strip()} » ajoutée.", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Erreur (la catégorie existe peut-être déjà) : {exc}")

# --- Remise en ordre : renommages proposés pour l'historique -----------------
with tab_cleanup:
    tab_help("settings_cleanup")
    st.caption(
        "Renommages proposés pour aligner ton historique de Mon budget et du foyer sur la liste commune. "
        "Chacun met à jour d'un coup toutes les opérations et règles concernées."
    )
    existing_shared = {
        c["name"] for c in all_categories if c["business_id"] in SHARED_SCOPES
    }
    suggestions = []
    for old, new in SUGGESTED_RENAMES:
        if old not in existing_shared:
            continue
        try:
            suggestions.append((old, new, count_category_usage(old, list(SHARED_SCOPES))))
        except Exception as exc:
            st.error(f"Impossible de compter « {old} » : {exc}")

    if not suggestions:
        st.success("Rien à remettre en ordre : l'historique suit déjà la liste commune. 🎉")
    else:
        chosen = [
            (old, new)
            for old, new, count in suggestions
            if st.checkbox(
                f"**{old}** → **{new}**  ({count} opération(s))", value=True, key=f"cleanup_{old}"
            )
        ]
        if st.button("Appliquer", type="primary", key="cleanup_apply") and chosen:
            try:
                total = 0
                for old, new in chosen:
                    total += rename_or_merge_category(old, new, list(SHARED_SCOPES))
                    if new in DEFAULT_GROUPS:
                        set_category_group(new, DEFAULT_GROUPS[new], "expense")
                invalidate_cache()
                st.toast(f"{len(chosen)} catégorie(s) remise(s) en ordre ({total} opérations).", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(f"Erreur : {exc}")

# --- Renommer / fusionner -----------------------------------------------------
with tab_rename:
    tab_help("settings_rename")
    st.caption(
        "Renomme une catégorie pour tout l'historique. Si le nouveau nom existe déjà, les deux "
        "catégories sont **fusionnées**. Les catégories dont dépendent des calculs "
        "(Épargne, BNC, BIC, ND, Évenement Privé, Stripe) sont protégées."
    )
    names = sorted({c["name"] for c in all_categories})
    if not names:
        st.info("Aucune catégorie.")
    else:
        col_old, col_new = st.columns(2)
        old_name = col_old.selectbox("Catégorie à renommer", names, key="rename_old")
        new_rename = col_new.text_input("Nouveau nom", key="rename_new")
        where = sorted({c["business_id"] for c in all_categories if c["name"] == old_name})
        scopes = st.multiselect(
            "Budgets concernés", where, default=where, format_func=lambda s: SCOPE_LABELS.get(s, s),
            key="rename_scopes",
        )
        error = validate_rename(old_name, new_rename) if new_rename else None
        if error:
            st.warning(error)
        elif new_rename and scopes:
            try:
                st.info(f"{count_category_usage(old_name, scopes)} opération(s) seront modifiées.")
            except Exception as exc:
                st.error(f"Impossible de compter les opérations : {exc}")
        if st.button("Renommer / fusionner", key="rename_apply", disabled=bool(error) or not new_rename or not scopes):
            try:
                moved = rename_or_merge_category(old_name, new_rename.strip(), scopes)
                invalidate_cache()
                st.toast(f"« {old_name} » → « {new_rename.strip()} » ({moved} opérations).", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(f"Erreur : {exc}")

st.divider()

# ---------------------------------------------------------------------------
# Sauvegarde
# ---------------------------------------------------------------------------
section_title("Sauvegarde", "settings_sauvegarde")
st.caption(
    "Télécharge une copie de toutes tes opérations (CSV). À faire avant un gros changement, "
    "par exemple une remise en ordre des catégories. Range le fichier quelque part : tu n'as "
    "rien d'autre à en faire, il ne sert qu'en cas de problème."
)
_BACKUP_KEY = "_backup_csv"
if st.button("Préparer la sauvegarde", key="backup_prepare"):
    with st.spinner("Lecture de toutes les opérations…"):
        try:
            backup_rows = fetch_all_transactions()
            st.session_state[_BACKUP_KEY] = (
                pl.DataFrame(backup_rows, infer_schema_length=None).write_csv().encode("utf-8"),
                len(backup_rows),
            )
        except Exception as exc:
            st.error(f"Impossible de lire les opérations : {exc}")
if _BACKUP_KEY in st.session_state:
    backup_csv, backup_count = st.session_state[_BACKUP_KEY]
    st.download_button(
        f"⬇️ Télécharger ({backup_count} opérations)",
        data=backup_csv,
        file_name=f"sauvegarde-transactions-{date.today().isoformat()}.csv",
        mime="text/csv",
        key="backup_download",
    )

st.divider()

# ---------------------------------------------------------------------------
# Statut des connexions
# ---------------------------------------------------------------------------
section_title("Statut des connexions", "settings_statut")

_STATUS_CACHE_KEY = "_settings_health"

col_check, _ = st.columns([1, 3])
with col_check:
    if st.button("🔄 Vérifier les connexions", width='stretch'):
        with st.spinner("Tests en cours…"):
            st.session_state[_STATUS_CACHE_KEY] = run_all_checks()

statuses: list[HealthStatus] | None = st.session_state.get(_STATUS_CACHE_KEY)

if statuses:
    cols = st.columns(len(statuses))
    for status, col in zip(statuses, cols):
        with col:
            icon = "✅" if status.ok else "❌"
            st.metric(
                label=f"{icon} {status.name}",
                value="OK" if status.ok else "Erreur",
                delta=f"{status.latency_ms:.0f} ms" if status.latency_ms else None,
                delta_color="off",
            )
            if not status.ok:
                st.error(status.message, icon="⚠️")
            else:
                st.caption(status.message)
else:
    st.info("Cliquez sur **Vérifier les connexions** pour tester les services.")

st.divider()

# ---------------------------------------------------------------------------
# Gestion du cache
# ---------------------------------------------------------------------------
section_title("Cache de données", "settings_cache")
st.caption(
    "Les requêtes base de données sont mises en cache 5 minutes (TTL). "
    "Videz le cache si les données affichées semblent obsolètes."
)

col_cache1, col_cache2 = st.columns([1, 3])
with col_cache1:
    if st.button("🗑️ Vider le cache", width='stretch'):
        invalidate_cache()
        if _STATUS_CACHE_KEY in st.session_state:
            del st.session_state[_STATUS_CACHE_KEY]
        st.toast("Cache vidé — les prochaines requêtes iront directement en base.", icon="✅")

st.divider()

# ---------------------------------------------------------------------------
# Configuration requise
# ---------------------------------------------------------------------------
st.subheader("Variables d'environnement requises")
st.caption("À configurer dans `.streamlit/secrets.toml` (local) ou dans Streamlit Cloud > Settings > Secrets.")

st.code(
    """# .streamlit/secrets.toml
SUPABASE_URL  = "https://<project>.supabase.co"
SUPABASE_KEY  = "<anon-or-service-role-key>"
DB_URL        = "postgresql://postgres:<pwd>@db.<project>.supabase.co:5432/postgres"

STRIPE_SECRET_KEY     = "sk_live_..."
STRIPE_WEBHOOK_SECRET = "whsec_..."
""",
    language="toml",
)

st.divider()

# ---------------------------------------------------------------------------
# À propos
# ---------------------------------------------------------------------------
st.subheader("À propos")
st.markdown(
    """
| | |
|---|---|
| **Application** | Compta Pro & Perso |
| **Version** | 0.1.0 |
| **Python** | ≥ 3.11 |
| **Stack** | Streamlit · Polars · Supabase · Stripe |
| **Démarrage** | `streamlit run app/main.py` |
| **Tests** | `pytest tests/` |
| **Lint** | `ruff check src/ tests/` |
"""
)
