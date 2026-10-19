"""Catégories partagées entre les budgets (Perso, Foyer, activités pro).

Une catégorie est une ligne (activité, nom, sens) de la table categories ; « partagée »
signifie que le même nom existe pour plusieurs activités, ce qui permet de comparer le
perso et le foyer. Chaque catégorie appartient à un groupe (Logement, Alimentation…)
pour lire les graphiques à deux niveaux : le groupe pour l'essentiel, la catégorie
pour le détail.

Renommer une catégorie vers un nom qui existe déjà la fusionne avec celui-ci.
"""

from typing import Any

# Catégories dont dépendent des calculs : on ne les renomme pas et on ne les fusionne
# pas ailleurs (Épargne → ligne Épargne du budget perso ; BNC/BIC/ND/Évenement Privé →
# taux URSSAF ; Stripe → frais Stripe déduits du CA).
PROTECTED_CATEGORIES = frozenset({"Épargne", "BNC", "BIC", "ND", "Évenement Privé", "Stripe"})

# Activités concernées par la remise en ordre proposée (les pros gardent leurs catégories)
SHARED_SCOPES = ("personal", "household")

SCOPE_LABELS: dict[str, str] = {
    "personal": "Perso",
    "household": "Foyer",
    "phi_rising": "Phi Rising",
    "booth_in_lyon": "Booth in Lyon",
}

# Ordre d'affichage des groupes
GROUPS: tuple[str, ...] = (
    "Logement",
    "Alimentation",
    "Transport",
    "Loisirs",
    "Santé",
    "Vie courante",
    "Épargne",
    "Hors dépenses communes",
    "Revenus",
    "Activité pro",
)
NO_GROUP = "Sans groupe"

# Renommages proposés pour l'historique perso et foyer : (ancien nom, nouveau nom)
SUGGESTED_RENAMES: tuple[tuple[str, str], ...] = (
    ("Médical", "Santé"),
    ("Restau / Soirées", "Restaurants & bars"),
    ("Autres Loisirs", "Sorties & loisirs"),
    ("Voyage", "Voyages"),
    ("Repas", "Repas du midi"),
    ("Autres Obligatoire", "Divers"),
    ("Epargne", "Épargne"),
)

# Groupe des catégories cibles de la remise en ordre (une catégorie créée par un
# renommage reçoit ainsi son groupe tout de suite)
DEFAULT_GROUPS: dict[str, str] = {
    "Santé": "Santé",
    "Restaurants & bars": "Alimentation",
    "Sorties & loisirs": "Loisirs",
    "Voyages": "Loisirs",
    "Repas du midi": "Alimentation",
    "Divers": "Vie courante",
    "Épargne": "Épargne",
}


def validate_rename(old: str, new: str) -> str | None:
    """Message d'erreur si le renommage / la fusion est interdit, sinon None."""
    new = new.strip()
    if not new:
        return "Le nouveau nom ne peut pas être vide."
    if new == old:
        return "Le nouveau nom est identique à l'ancien."
    if old in PROTECTED_CATEGORIES:
        return (
            f"« {old} » ne peut pas être renommée ni fusionnée : des calculs en dépendent "
            "(ligne Épargne, taux URSSAF, frais Stripe)."
        )
    return None


def plan_category_rows(
    old_rows: list[dict[str, Any]],
    new_keys: set[tuple[str, str]],
) -> tuple[list[str], list[str]]:
    """Que faire des lignes de la table categories lors d'un renommage ?

    Args:
        old_rows: lignes {id, business_id, direction} portant l'ancien nom.
        new_keys: {(business_id, direction)} qui existent déjà sous le nouveau nom.

    Returns:
        (ids_à_renommer, ids_à_supprimer) — une ligne dont le nouveau nom existe déjà
        pour la même activité et le même sens est supprimée (fusion).
    """
    to_rename: list[str] = []
    to_delete: list[str] = []
    for row in old_rows:
        if (row["business_id"], row["direction"]) in new_keys:
            to_delete.append(row["id"])
        else:
            to_rename.append(row["id"])
    return to_rename, to_delete


def matrix_rows(categories: list[dict[str, Any]], direction: str) -> list[dict[str, Any]]:
    """Une ligne par nom de catégorie : groupe + présence dans chaque activité.

    Trié par groupe (ordre GROUPS) puis par nom.
    """
    by_name: dict[str, dict[str, Any]] = {}
    for cat in categories:
        if cat["direction"] != direction:
            continue
        row = by_name.setdefault(
            cat["name"],
            {"name": cat["name"], "group": cat.get("group_name") or NO_GROUP,
             **{scope: False for scope in SCOPE_LABELS}},
        )
        if cat["business_id"] in SCOPE_LABELS:
            row[cat["business_id"]] = True
        if cat.get("group_name"):
            row["group"] = cat["group_name"]

    def _order(row: dict[str, Any]) -> tuple[int, str]:
        group = row["group"]
        return (GROUPS.index(group) if group in GROUPS else len(GROUPS), row["name"].lower())

    return sorted(by_name.values(), key=_order)


def diff_matrix(
    current: list[dict[str, Any]],
    edited: list[dict[str, Any]],
    direction: str,
) -> tuple[list[dict[str, Any]], list[str], dict[str, str]]:
    """Différences entre la liste actuelle et la liste modifiée à l'écran.

    Args:
        current: lignes de la table categories (id, business_id, name, direction, group_name).
        edited: lignes de matrix_rows après modification.
        direction: 'expense' ou 'income' (la liste affichée).

    Returns:
        (à_créer, ids_à_supprimer, changements_de_groupe {nom: groupe})
    """
    existing = {
        (c["name"], c["business_id"]): c for c in current if c["direction"] == direction
    }
    current_groups = {c["name"]: c.get("group_name") or NO_GROUP for c in current if c["direction"] == direction}

    to_create: list[dict[str, Any]] = []
    to_delete: list[str] = []
    group_changes: dict[str, str] = {}
    for row in edited:
        group = row["group"] if row["group"] != NO_GROUP else None
        if row["group"] != current_groups.get(row["name"], NO_GROUP):
            group_changes[row["name"]] = row["group"]
        for scope in SCOPE_LABELS:
            exists = (row["name"], scope) in existing
            if row[scope] and not exists:
                to_create.append({
                    "business_id": scope, "name": row["name"],
                    "direction": direction, "group_name": group,
                })
            elif not row[scope] and exists:
                to_delete.append(existing[(row["name"], scope)]["id"])
    return to_create, to_delete, group_changes
