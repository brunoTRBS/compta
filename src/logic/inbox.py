"""File « À traiter » : opérations importées sans catégorie, et aide à les classer.

Deux aides :
- un motif de règle proposé à partir du libellé de la banque (« EasyPark »,
  « E LECLERC »…), pour que la même dépense se classe seule la prochaine fois ;
- une catégorie suggérée d'après les choix passés : si les opérations que la banque
  range en « Restaurants, bars… » ont surtout été classées « Restau / Soirées »,
  c'est celle-là qui est proposée.
"""

import re
from collections import Counter
from typing import Any

import polars as pl

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


def pending_transactions(df: pl.DataFrame) -> pl.DataFrame:
    """Opérations à classer : sans catégorie, hors virements et hors foyer."""
    if df.is_empty():
        return df
    return df.filter(
        (pl.col("category").is_null() | (pl.col("category") == ""))
        & ~pl.col("is_transfer").fill_null(False)
        & ~pl.col("is_household").fill_null(False)
    )


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


def build_rule(pattern: str, category: str, business_id: str) -> dict[str, Any]:
    """Règle de catégorisation à enregistrer depuis la file."""
    return {
        "pattern": pattern.strip(),
        "category": category,
        "business_id": business_id,
        "priority": USER_RULE_PRIORITY,
        "is_active": True,
    }
