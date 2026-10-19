"""Boîte de réception « À traiter » : tout ce qui demande un geste après un import.

Une ligne arrive ici pour l'une de quatre raisons : elle n'a pas de catégorie, c'est un
paiement avec ta carte sur le compte commun (foyer ou perso ?), c'est ta participation au
foyer, ou c'est un virement entre tes comptes dont l'autre côté n'est pas importé.
Chaque ligne reçoit une affectation (Perso, Foyer, Phi Rising, Booth in Lyon, ou virement
interne) et une catégorie ; un seul « Enregistrer » applique le tout (voir plan_inbox_changes).

Deux aides :
- un motif de règle proposé à partir du libellé de la banque (« EasyPark »,
  « E LECLERC »…), pour que la même dépense se classe seule la prochaine fois ;
- une catégorie suggérée d'après les choix passés : si les opérations que la banque
  range en « Restaurants, bars… » ont surtout été classées « Restau / Soirées »,
  c'est celle-là qui est proposée.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import polars as pl

from src.config import HOUSEHOLD_PARTICIPATION_CATEGORY, BusinessId
from src.logic.categories import resolve_category
from src.logic.categorizer import apply_rules
from src.logic.household import KIND_CARD, KIND_PARTICIPATION, participation_expense, review_kind
from src.logic.transfers import resolve_transfer_review

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

# Affectations proposées, dans l'ordre d'affichage de la page
AFFECTATIONS: dict[str, str] = {
    TRANSFER: "Virement interne",
    str(BusinessId.HOUSEHOLD): "Foyer",
    str(BusinessId.PERSONAL): "Perso",
    str(BusinessId.PHI_RISING): "Phi Rising",
    str(BusinessId.BOOTH_IN_LYON): "Booth in Lyon",
}
_AFFECTATION_KEYS = {label: key for key, label in AFFECTATIONS.items()}

REASON_CARD = "💳 Ta carte sur le commun"
REASON_PARTICIPATION = "↘️ Ta participation"
REASON_TRANSFER = "🔁 Virement entre tes comptes ?"
REASON_CLASSIFY = "🏷️ À classer"


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
        kind = review_kind(tx)
        if kind == KIND_CARD:
            return REASON_CARD
        if kind == KIND_PARTICIPATION:
            return REASON_PARTICIPATION
    return REASON_CLASSIFY


def proposed_affectation(tx: dict[str, Any]) -> str:
    """Affectation affichée au départ : celle de l'opération, ou « virement interne » pour
    un virement à confirmer."""
    if inbox_reason(tx) == REASON_TRANSFER:
        return TRANSFER
    return tx["business_id"]


def rule_updates(df: pl.DataFrame, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ce que les règles changent sur des opérations déjà en base : catégorie, affectation,
    et fin de la vérification d'une carte du commun reconnue.

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
        if (
            before.get("needs_review") and fields.get("category")
            and review_kind(before) == KIND_CARD
        ):
            fields["needs_review"] = False
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


def plan_inbox_changes(
    originals: list[dict[str, Any]],
    edited: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    categories: dict[str, dict[str, set[str]]],
) -> InboxPlan:
    """Transforme les lignes de la boîte de réception, telles qu'affichées, en modifications.

    Enregistrer valide aussi les lignes à vérifier laissées telles quelles : une carte du
    commun reste au foyer, une participation reste une participation.

    Args:
        originals: opérations en base (id, business_id, label, category, amount, needs_review…).
        edited: lignes du tableau après modification, avec les clés Libellé, Affectation,
            Catégorie, "Autre compte", Exceptionnel (ou None), Règle, Motif.
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
        affectation = _AFFECTATION_KEYS.get(row.get("Affectation") or "", proposed_affectation(tx))
        fields: dict[str, Any] = {}

        label = (row.get("Libellé") or "").strip()
        if label and label != tx["label"]:
            fields["label"] = label

        # --- virement entre deux de tes comptes -------------------------------------------
        if affectation == TRANSFER:
            counterpart = accounts_by_label.get(row.get("Autre compte") or "")
            if counterpart is None or counterpart["id"] == tx.get("account_id"):
                plan.errors.append(f"« {name} » : choisis l'autre compte du virement.")
                if fields:
                    plan.updates.append({"id": tx["id"], **fields})
                continue
            updates, legs = resolve_transfer_review([{**tx, **fields}], {tx["id"]: counterpart})
            plan.updates.append({**updates[0], **fields})
            plan.legs.extend(legs)
            continue

        # --- affectation à un budget ------------------------------------------------------
        if affectation != tx["business_id"]:
            fields["business_id"] = affectation

        valid = categories.get(affectation, {}).get(direction, set())
        chosen = row.get("Catégorie") or None
        current = tx.get("category") or None
        final, rejected = resolve_category(current, chosen, valid)
        if rejected:
            plan.errors.append(
                f"« {name} » : la catégorie « {chosen} » n'existe pas pour {AFFECTATIONS[affectation]} "
                "(catégorie non appliquée)."
            )
            chosen = None
        if final != current:
            fields["category"] = final

        if tx.get("needs_review"):
            fields["needs_review"] = False

        exceptional = row.get("Exceptionnel")
        if exceptional is not None and bool(exceptional) != bool(tx.get("is_exceptional")):
            fields["is_exceptional"] = bool(exceptional)

        if fields:
            plan.updates.append({"id": tx["id"], **fields})

        # Ta participation validée en « Participation Charlotte » crée ta dépense perso
        if (
            review_kind(tx) == KIND_PARTICIPATION
            and affectation == str(BusinessId.HOUSEHOLD)
            and final == HOUSEHOLD_PARTICIPATION_CATEGORY
        ):
            plan.participations.append(participation_expense(tx))

        # Règle : les prochaines opérations avec ce motif se rangent seules
        pattern = (row.get("Motif") or "").strip()
        if row.get("Règle") and chosen and pattern:
            target = affectation if affectation != tx["business_id"] else None
            plan.rules.append(build_rule(pattern, chosen, tx["business_id"], direction, target))

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
