"""Boîte de réception « À traiter » : tout ce qui demande un geste après un import.

Une ligne arrive ici pour l'une de trois raisons : elle n'a pas de catégorie, c'est ta part du
foyer (virement reçu sur le compte commun), ou c'est un virement entre tes comptes dont l'autre
côté n'est pas importé. Chaque ligne indique « Payé avec » (le compte du relevé) et « Ça compte
pour » (Notre foyer, Moi, Phi Rising, Booth in Lyon, ou un virement entre tes comptes), plus une
catégorie ; un seul « Enregistrer » applique le tout (voir plan_inbox_changes).
Tout ce qui vient du compte commun compte pour le foyer tant que tu ne le changes pas.

Deux aides :
- un motif de règle proposé à partir du libellé de la banque (« EasyPark »,
  « E LECLERC »…), pour que la même dépense se classe seule la prochaine fois ;
- une catégorie suggérée d'après les choix passés : si les opérations que la banque
  range en « Restaurants, bars… » ont surtout été classées « Restau / Soirées »,
  c'est celle-là qui est proposée.
"""

import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import polars as pl

from src.config import HOUSEHOLD_PARTICIPATION_CATEGORY, JOINT_ACCOUNT_NAME, BusinessId
from src.logic.categories import resolve_category
from src.logic.categorizer import apply_rules
from src.logic.household import (
    KIND_PARTICIPATION,
    participation_expense,
    propose_exceptional,
    review_kind,
)
from src.logic.transfers import default_counterpart, resolve_transfer_review

# Priorité des règles créées depuis la file : au-dessus des règles génériques du seed
USER_RULE_PRIORITY = 200

# Préfixes de libellés bancaires qui ne disent rien du commerçant
_PREFIXES = [
    r"CARTE \d{2}/\d{2}/\d{2,4}",           # BoursoBank : CARTE 10/10/26 …
    r"PAIEMENT (?:CB|PSC) \d{4}",            # Crédit Mutuel : PAIEMENT CB 0810 …
    r"PRLV SEPA",
    r"PRLV",
    r"VIR (?:INST|SEPA)",
    r"VIR",
    r"AVOIR CB \d{4}",
    r"RETRAIT DAB \d{2}/\d{2}/\d{2,4}",
]
# Ce qui suit le commerçant : n° de carte, références
_STOP_TOKENS = re.compile(r"^(CARTE|CB\*\S*|HI[A-Z]\d+|REF.*)$")
_MIN_PATTERN_LENGTH = 3


def suggest_pattern(tx: dict[str, Any]) -> str:
    """Motif de règle proposé pour une opération (modifiable par l'utilisatrice).

    Le libellé nettoyé par la banque (BoursoBank) est le meilleur motif ; à défaut,
    le libellé brut sans son préfixe technique ni ses références.
    """
    label = (tx.get("label") or "").strip()
    raw = (tx.get("raw_label") or "").strip()
    if raw and label and label.upper() != raw.upper():
        return label

    text = (raw or label).upper()
    for prefix in _PREFIXES:
        text = re.sub(rf"^{prefix}\s+", "", text)
    words: list[str] = []
    for token in text.split():
        # Arrêt au 1er n° de carte / référence / token avec beaucoup de chiffres
        if _STOP_TOKENS.match(token) or sum(c.isdigit() for c in token) >= 4:
            break
        words.append(token)
    pattern = " ".join(words).strip()
    return pattern if len(pattern) >= _MIN_PATTERN_LENGTH else (raw or label)


TRANSFER = "transfer"

# « Ça compte pour » : les choix proposés, dans l'ordre d'affichage
AFFECTATIONS: dict[str, str] = {
    str(BusinessId.HOUSEHOLD): "🏠 Notre foyer",
    str(BusinessId.PERSONAL): "👤 Moi",
    str(BusinessId.PHI_RISING): "💼 Phi Rising",
    str(BusinessId.BOOTH_IN_LYON): "📸 Booth in Lyon",
    TRANSFER: "🔁 Virement entre mes comptes",
}
_AFFECTATION_KEYS = {label: key for key, label in AFFECTATIONS.items()}

REASON_PARTICIPATION = "↘️ Ta part du foyer"
REASON_TRANSFER = "🔁 Virement ?"
REASON_CLASSIFY = "🏷️ À classer"

# Colonnes du tableau (le tableau et le calcul de l'enregistrement s'accordent sur ces noms)
COL_REASON = "Pourquoi"
COL_DATE = "Date"
COL_ACCOUNT = "Payé avec"
COL_LABEL = "Libellé"
COL_AMOUNT = "Montant"
COL_COUNTS_FOR = "Ça compte pour"
COL_CATEGORY = "Catégorie"
COL_SUGGESTED = "✨"
COL_RULE = "Pareil la prochaine fois"
COL_FROM = "De"
COL_TO = "Vers"
COL_PATTERN = "Mot reconnu"
COL_OFF_MONTH = "Ne pas compter dans le mois"
COL_BANK_LABEL = "Libellé de la banque"
COL_BANK_CATEGORY = "Catégorie de la banque"

_MAIN_COLUMNS = [COL_REASON, COL_DATE, COL_ACCOUNT, COL_LABEL, COL_AMOUNT, COL_COUNTS_FOR,
                 COL_SUGGESTED, COL_CATEGORY, COL_RULE]
_DETAIL_COLUMNS = [COL_PATTERN, COL_OFF_MONTH, COL_BANK_LABEL, COL_BANK_CATEGORY]


def account_label(account: dict[str, Any]) -> str:
    return f"{account['name']} ({account.get('institution') or '?'})"


def inbox_rows(df: pl.DataFrame) -> pl.DataFrame:
    """Opérations à traiter : à vérifier, ou sans catégorie (virements internes exclus)."""
    if df.is_empty():
        return df
    return df.filter(
        ~pl.col("is_transfer").fill_null(False)
        & (
            pl.col("needs_review").fill_null(False)
            | pl.col("category").is_null()
            | (pl.col("category") == "")
        )
    )


def inbox_reason(tx: dict[str, Any]) -> str:
    """Pourquoi cette opération est dans la boîte de réception."""
    if tx.get("needs_review"):
        if tx.get("business_id") != str(BusinessId.HOUSEHOLD):
            return REASON_TRANSFER
        if review_kind(tx) == KIND_PARTICIPATION:
            return REASON_PARTICIPATION
    return REASON_CLASSIFY


def proposed_affectation(tx: dict[str, Any]) -> str:
    """« Ça compte pour » affiché au départ : celui de l'opération, ou « virement entre mes
    comptes » pour un virement à confirmer."""
    if inbox_reason(tx) == REASON_TRANSFER:
        return TRANSFER
    return tx["business_id"]


def rule_updates(df: pl.DataFrame, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ce que les règles changent sur des opérations déjà en base : catégorie et budget.

    Returns:
        [{id, champ: valeur…}] — seules les opérations qui changent.
    """
    if df.is_empty() or not rules:
        return []
    original = {r["id"]: r for r in df.to_dicts()}
    updates: list[dict[str, Any]] = []
    for row in apply_rules(df, rules).to_dicts():
        before = original[row["id"]]
        fields: dict[str, Any] = {}
        if row.get("category") and not before.get("category"):
            fields["category"] = row["category"]
        if row["business_id"] != before["business_id"]:
            fields["business_id"] = row["business_id"]
        if fields:
            updates.append({"id": row["id"], **fields})
    return updates


@dataclass
class InboxPlan:
    """Résultat de plan_inbox_changes : tout ce qu'il faut écrire, et ce qui a posé problème."""

    updates: list[dict[str, Any]] = field(default_factory=list)       # [{id, champs…}]
    legs: list[dict[str, Any]] = field(default_factory=list)          # 2e écriture des virements
    participations: list[dict[str, Any]] = field(default_factory=list)  # dépenses perso à créer
    rules: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def proposed_category(
    tx: dict[str, Any],
    suggestions: dict[tuple[str, str], str],
    categories: dict[str, dict[str, set[str]]],
) -> tuple[str | None, bool]:
    """Catégorie affichée au départ pour une ligne, et si elle est une suggestion (✨).

    Une catégorie déjà posée est gardée. Ta part du foyer reçoit « Participation Charlotte » :
    il suffit d'enregistrer. Sinon, la catégorie la plus choisie jusqu'ici pour la catégorie
    de la banque.
    """
    if tx.get("category"):
        return tx["category"], False
    if inbox_reason(tx) == REASON_PARTICIPATION:
        return HOUSEHOLD_PARTICIPATION_CATEGORY, True
    direction = "income" if float(tx["amount"]) > 0 else "expense"
    allowed = sorted(categories.get(tx["business_id"], {}).get(direction, set()))
    suggested = suggest_category(tx, suggestions, allowed)
    return suggested, suggested is not None


def inbox_table(
    rows: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    categories: dict[str, dict[str, set[str]]],
    suggestions: dict[tuple[str, str], str],
) -> dict[str, list[Any]]:
    """Colonnes du tableau « À traiter » (toutes, visibles ou non), une ligne par opération.

    Les lignes à vérifier d'abord, puis les plus récentes. Pour un virement entre tes comptes,
    « De » et « Vers » se lisent comme une phrase : le côté connu est le compte du relevé
    (d'après le signe du montant), l'autre est proposé.
    """
    ordered = sorted(rows, key=lambda r: (not r.get("needs_review"), -_as_ordinal(r["date"])))
    account_by_id = {a["id"]: a for a in accounts}
    columns: dict[str, list[Any]] = {"id": [], COL_REASON: [], COL_DATE: [], COL_ACCOUNT: [],
                                     COL_LABEL: [], COL_AMOUNT: [], COL_COUNTS_FOR: [],
                                     COL_CATEGORY: [], COL_SUGGESTED: [], COL_RULE: [],
                                     COL_FROM: [], COL_TO: [], COL_PATTERN: [],
                                     COL_OFF_MONTH: [], COL_BANK_LABEL: [],
                                     COL_BANK_CATEGORY: []}
    for tx in ordered:
        affectation = proposed_affectation(tx)
        own = account_by_id.get(tx.get("account_id"))
        own_label = account_label(own) if own else None
        origin, destination = None, None
        category, suggested = None, False
        if affectation == TRANSFER:
            other = default_counterpart(tx, accounts)
            other_label = account_label(other) if other else None
            origin, destination = (own_label, other_label) if float(tx["amount"]) < 0 \
                else (other_label, own_label)
        else:
            category, suggested = proposed_category(tx, suggestions, categories)
        columns["id"].append(tx["id"])
        columns[COL_REASON].append(inbox_reason(tx))
        columns[COL_DATE].append(tx["date"])
        columns[COL_ACCOUNT].append(own["name"] if own else "—")
        columns[COL_LABEL].append(tx["label"])
        columns[COL_AMOUNT].append(tx["amount"])
        columns[COL_COUNTS_FOR].append(AFFECTATIONS[affectation])
        columns[COL_CATEGORY].append(category)
        columns[COL_SUGGESTED].append("✨" if suggested and not tx.get("category") else "")
        columns[COL_RULE].append(False)
        columns[COL_FROM].append(origin)
        columns[COL_TO].append(destination)
        columns[COL_PATTERN].append(suggest_pattern(tx))
        columns[COL_OFF_MONTH].append(bool(tx.get("is_exceptional")) or propose_exceptional(tx))
        columns[COL_BANK_LABEL].append(tx.get("raw_label") or "")
        columns[COL_BANK_CATEGORY].append(tx.get("bank_category") or "")
    return columns


def visible_columns(table: dict[str, list[Any]], details: bool) -> list[str]:
    """Colonnes à afficher : l'essentiel ; les détails sur demande ; De/Vers dès qu'une ligne
    est un virement entre tes comptes (sinon on ne saurait pas où choisir l'autre compte)."""
    names = ["id", *_MAIN_COLUMNS]
    has_transfer = any(label == AFFECTATIONS[TRANSFER] for label in table[COL_COUNTS_FOR])
    if has_transfer or details:
        names[names.index(COL_CATEGORY) + 1:names.index(COL_CATEGORY) + 1] = [COL_FROM, COL_TO]
    if details:
        names += _DETAIL_COLUMNS
    return names


def _as_ordinal(value: Any) -> int:
    return value.toordinal() if hasattr(value, "toordinal") else date.fromisoformat(str(value)[:10]).toordinal()


def plan_inbox_changes(
    originals: list[dict[str, Any]],
    edited: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    categories: dict[str, dict[str, set[str]]],
) -> InboxPlan:
    """Transforme les lignes de la boîte de réception, telles qu'affichées, en modifications.

    Enregistrer valide aussi les lignes à vérifier laissées telles quelles : ta part du foyer
    reste une participation.

    Args:
        originals: opérations en base (id, business_id, label, category, amount, needs_review…).
        edited: lignes du tableau après modification, avec les clés COL_* (Libellé, Ça compte
            pour, Catégorie, De, Vers, Ne pas compter dans le mois (ou None), Pareil la prochaine
            fois, Mot reconnu).
        accounts: comptes actifs.
        categories: {activité: {"expense": {noms}, "income": {noms}}}.
    """
    plan = InboxPlan()
    by_id = {tx["id"]: tx for tx in originals}
    accounts_by_label = {account_label(a): a for a in accounts}

    for row in edited:
        tx = by_id.get(row["id"])
        if tx is None:
            continue
        name = tx["label"]
        direction = "income" if float(tx["amount"]) > 0 else "expense"
        affectation = _AFFECTATION_KEYS.get(row.get(COL_COUNTS_FOR) or "", proposed_affectation(tx))
        fields: dict[str, Any] = {}

        label = (row.get(COL_LABEL) or "").strip()
        if label and label != tx["label"]:
            fields["label"] = label

        # --- virement entre deux de tes comptes ------------------------------------------
        if affectation == TRANSFER:
            # L'autre côté est celui des deux choix (De, Vers) qui n'est pas le compte du relevé
            chosen = {
                accounts_by_label[value]["id"]: accounts_by_label[value]
                for value in (row.get(COL_FROM), row.get(COL_TO))
                if value in accounts_by_label and accounts_by_label[value]["id"] != tx.get("account_id")
            }
            if len(chosen) != 1:
                plan.errors.append(
                    f"« {name} » : choisis l'autre compte du virement (colonnes De et Vers, visibles avec « Plus de détails »)."
                    if not chosen else f"« {name} » : un virement n'a qu'un autre compte, garde-en un seul."
                )
                if fields:
                    plan.updates.append({"id": tx["id"], **fields})
                continue
            counterpart = next(iter(chosen.values()))
            if counterpart["name"] == JOINT_ACCOUNT_NAME:
                # Le compte commun a son propre relevé : on ne crée pas son côté, la ligne
                # est seulement sortie des revenus / dépenses (la part du foyer se traite
                # sur la ligne reçue côté commun).
                plan.updates.append({
                    "id": tx["id"], "needs_review": False, "is_transfer": True,
                    "transfer_group_id": str(uuid.uuid4()), **fields,
                })
                continue
            updates, legs = resolve_transfer_review([{**tx, **fields}], {tx["id"]: counterpart})
            plan.updates.append({**updates[0], **fields})
            plan.legs.extend(legs)
            continue

        # --- ça compte pour un budget ----------------------------------------------------
        if affectation != tx["business_id"]:
            fields["business_id"] = affectation

        valid = categories.get(affectation, {}).get(direction, set())
        chosen_category = row.get(COL_CATEGORY) or None
        current = tx.get("category") or None
        final, rejected = resolve_category(current, chosen_category, valid)
        if rejected:
            plan.errors.append(
                f"« {name} » : la catégorie « {chosen_category} » n'existe pas pour "
                f"{AFFECTATIONS[affectation]} (catégorie non appliquée)."
            )
            chosen_category = None
        if final != current:
            fields["category"] = final

        if tx.get("needs_review"):
            fields["needs_review"] = False

        off_month = row.get(COL_OFF_MONTH)
        if off_month is not None and bool(off_month) != bool(tx.get("is_exceptional")):
            fields["is_exceptional"] = bool(off_month)

        if fields:
            plan.updates.append({"id": tx["id"], **fields})

        # Ta part du foyer validée en « Participation Charlotte » crée ta dépense perso
        if (
            review_kind(tx) == KIND_PARTICIPATION
            and affectation == str(BusinessId.HOUSEHOLD)
            and final == HOUSEHOLD_PARTICIPATION_CATEGORY
        ):
            plan.participations.append(participation_expense(tx))

        # Pareil la prochaine fois : les opérations avec ce mot se rangent seules
        pattern = (row.get(COL_PATTERN) or "").strip()
        if row.get(COL_RULE) and chosen_category and pattern:
            target = affectation if affectation != tx["business_id"] else None
            plan.rules.append(build_rule(pattern, chosen_category, tx["business_id"], direction, target))

    return plan


def category_suggestions_from_history(history: pl.DataFrame) -> dict[tuple[str, str], str]:
    """Catégorie la plus souvent choisie pour chaque (activité, catégorie banque).

    Returns:
        {(business_id, bank_category): category}
    """
    if history.is_empty() or "bank_category" not in history.columns:
        return {}
    rows = history.filter(
        pl.col("bank_category").is_not_null()
        & pl.col("category").is_not_null()
        & (pl.col("category") != "")
    ).select(["business_id", "bank_category", "category"]).to_dicts()

    counts: dict[tuple[str, str], Counter] = {}
    for r in rows:
        counts.setdefault((r["business_id"], r["bank_category"]), Counter())[r["category"]] += 1
    return {key: c.most_common(1)[0][0] for key, c in counts.items()}


def suggest_category(
    tx: dict[str, Any],
    suggestions: dict[tuple[str, str], str],
    allowed: list[str],
) -> str | None:
    """Catégorie proposée pour une opération, si elle fait partie des catégories permises."""
    if not tx.get("bank_category"):
        return None
    category = suggestions.get((tx["business_id"], tx["bank_category"]))
    return category if category in allowed else None


def build_rule(
    pattern: str,
    category: str,
    business_id: str,
    direction: str | None = None,
    target_business_id: str | None = None,
) -> dict[str, Any]:
    """Règle de catégorisation à enregistrer depuis la boîte de réception.

    business_id : le budget des opérations visées ; target_business_id : le budget où les
    ranger si différent (None = elles restent où elles sont).
    """
    return {
        "pattern": pattern.strip(),
        "category": category,
        "business_id": business_id,
        "priority": USER_RULE_PRIORITY,
        "is_active": True,
        "direction": direction,
        "target_business_id": target_business_id,
    }
