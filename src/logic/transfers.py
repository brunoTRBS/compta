"""Détection des virements internes dans les relevés importés.

Un virement entre deux comptes de l'utilisatrice n'est ni une dépense ni un revenu :
il doit devenir une paire d'écritures is_transfer liées par un transfer_group_id,
exactement comme un virement saisi dans l'onglet Virement. Les règles de budget
existantes s'appliquent ensuite telles quelles (vers le Livret → Épargne, depuis
Booth in Lyon → revenu, depuis Phi Rising → déjà compté dans son bénéfice).

Trois cas :
- virement rejeté : « VIR … » puis « REJ VIR … » du même montant sur le même compte —
  les deux s'annulent ;
- les deux côtés sont importés (ex : Compte perso → Livret) : appariés automatiquement ;
- un seul côté est importé (ex : virement reçu du compte pro, saisi à la main) :
  proposé à la vérification, l'utilisatrice indique l'autre compte.

Le compte commun n'est jamais concerné : ses opérations ont leurs propres règles
(voir household.py).
"""

import uuid
from datetime import date as Date
from typing import Any

from src.config import JOINT_OWN_NAME_PATTERNS, BusinessId
from src.logic.scopes import default_business_id

# La banque peut passer les deux côtés d'un virement à 1-3 jours d'écart
TRANSFER_MATCH_WINDOW_DAYS = 3

_TRANSFER_KEYWORDS = ("LIVRET", "EPARGNE", "ÉPARGNE")
_TRANSFER_NOTE = "Créé automatiquement depuis le relevé bancaire"


def _bank_label(tx: dict[str, Any]) -> str:
    return (tx.get("raw_label") or tx.get("label") or "").upper()


def _is_vir(tx: dict[str, Any]) -> bool:
    words = _bank_label(tx).split()
    return "VIR" in words or "VIREMENT" in words


def _as_date(value: Any) -> Date:
    return value if isinstance(value, Date) else Date.fromisoformat(str(value)[:10])


def _is_household(tx: dict[str, Any]) -> bool:
    return tx.get("business_id") == str(BusinessId.HOUSEHOLD)


def _eligible(tx: dict[str, Any]) -> bool:
    return not _is_household(tx) and not tx.get("is_transfer")


def is_transfer_like(tx: dict[str, Any]) -> bool:
    """Virement vers/depuis un autre compte de l'utilisatrice, d'après le libellé."""
    if not _eligible(tx) or not _is_vir(tx):
        return False
    label = _bank_label(tx)
    return any(p in label for p in JOINT_OWN_NAME_PATTERNS + _TRANSFER_KEYWORDS)


def _date_gap(a: dict[str, Any], b: dict[str, Any], window_days: int) -> int | None:
    gap = abs((_as_date(a["date"]) - _as_date(b["date"])).days)
    return gap if gap <= window_days else None


def find_rejected_pairs(
    rows: list[dict[str, Any]],
    include_household: bool = False,
) -> list[tuple[dict, dict]]:
    """Paires (virement, rejet) : même compte, montants opposés, « REJ » + même libellé.

    include_household=True : cherche aussi parmi les opérations du foyer (compte commun),
    où un virement rejeté fausserait les rentrées du budget du foyer.
    """
    def _ok(r: dict[str, Any]) -> bool:
        return not r.get("is_transfer") and (include_household or not _is_household(r))

    pairs: list[tuple[dict, dict]] = []
    used: set[int] = set()
    rejections = [r for r in rows if _ok(r) and _bank_label(r).startswith("REJ ")]
    for rej in rejections:
        original_label = _bank_label(rej)[4:].strip()
        for cand in rows:
            if (
                id(cand) not in used
                and cand is not rej
                and _ok(cand)
                and cand.get("account_id") == rej.get("account_id")
                and round(float(cand["amount"]), 2) == -round(float(rej["amount"]), 2)
                and _bank_label(cand) == original_label
            ):
                pairs.append((cand, rej))
                used.update({id(cand), id(rej)})
                break
    return pairs


def find_bank_transfer_pairs(
    new_rows: list[dict[str, Any]],
    existing_rows: list[dict[str, Any]],
    window_days: int = TRANSFER_MATCH_WINDOW_DAYS,
) -> list[tuple[dict, dict]]:
    """Apparie les 2 côtés d'un virement quand les deux comptes sont importés.

    Une ligne nouvelle « VIR … » est appariée à une ligne « VIR … » d'un AUTRE compte
    (nouvelle ou déjà en base), de montant opposé, à ≤ window_days jours. Au moins
    l'une des deux doit ressembler à un virement interne (is_transfer_like), pour ne
    pas apparier deux virements sans rapport du même montant.
    """
    pool = [r for r in new_rows + existing_rows if _eligible(r) and _is_vir(r)]
    pool_ids = {id(r) for r in pool}
    pairs: list[tuple[dict, dict]] = []
    used: set[int] = set()
    for tx in sorted((r for r in new_rows if id(r) in pool_ids), key=lambda r: str(r["date"])):
        if id(tx) in used:
            continue
        best, best_gap = None, None
        for cand in pool:
            if (
                id(cand) in used
                or cand is tx
                or cand.get("account_id") == tx.get("account_id")
                or round(float(cand["amount"]), 2) != -round(float(tx["amount"]), 2)
                or not (is_transfer_like(tx) or is_transfer_like(cand))
            ):
                continue
            gap = _date_gap(tx, cand, window_days)
            if gap is not None and (best_gap is None or gap < best_gap):
                best, best_gap = cand, gap
        if best is not None:
            pairs.append((tx, best))
            used.update({id(tx), id(best)})
    return pairs


def detect_transfers(
    new_rows: list[dict[str, Any]],
    existing_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Marque les virements dans un lot importé.

    - les paires trouvées (rejets, deux côtés importés) deviennent is_transfer avec
      un transfer_group_id commun ;
    - les autres lignes « virement interne » sont marquées needs_review.

    Args:
        new_rows: lignes du lot (sans id), modifiées sur place.
        existing_rows: lignes bancaires déjà en base (avec id) pouvant servir de 2e côté.

    Returns:
        (new_rows, mises_à_jour des lignes existantes [{id, ...}], nb de paires)
    """
    existing_updates: list[dict[str, Any]] = []
    pairs = find_rejected_pairs(new_rows + existing_rows)
    paired_ids = {id(r) for pair in pairs for r in pair}
    remaining_new = [r for r in new_rows if id(r) not in paired_ids]
    remaining_existing = [r for r in existing_rows if id(r) not in paired_ids]
    pairs += find_bank_transfer_pairs(remaining_new, remaining_existing)

    for pair in pairs:
        group_id = str(uuid.uuid4())
        for row in pair:
            fields = {"is_transfer": True, "transfer_group_id": group_id, "needs_review": False}
            if row.get("id"):
                existing_updates.append({"id": row["id"], **fields})
            row.update(fields)

    for row in new_rows:
        if is_transfer_like(row):
            row["needs_review"] = True

    return new_rows, existing_updates, len(pairs)


def default_counterpart(tx: dict[str, Any], accounts: list[dict[str, Any]]) -> dict | None:
    """Compte proposé par défaut comme 2e côté : le Livret pour un virement sortant,
    le compte pro Phi Rising pour un virement reçu (le virement mensuel du pro)."""
    if float(tx["amount"]) < 0:
        wanted = lambda a: a.get("type") == "savings"  # noqa: E731
    else:
        wanted = lambda a: a.get("owner") == "phi_rising"  # noqa: E731
    return next(
        (a for a in accounts if wanted(a) and a["id"] != tx.get("account_id")), None
    )


def resolve_transfer_review(
    transactions: list[dict[str, Any]],
    counterparts: dict[str, dict[str, Any] | None],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Applique les choix faits sur les virements à vérifier.

    Args:
        transactions: lignes needs_review (avec id).
        counterparts: {id: compte de l'autre côté, ou None si ce n'est pas un virement}.

    Returns:
        (mises_à_jour, écritures_à_créer) — l'écriture créée est le 2e côté du
        virement, en saisie manuelle : si ce compte est importé plus tard, sa ligne
        de relevé y sera rattachée au lieu d'être dupliquée.
    """
    updates: list[dict[str, Any]] = []
    legs: list[dict[str, Any]] = []
    for tx in transactions:
        account = counterparts.get(tx["id"])
        if account is None or account["id"] == tx.get("account_id"):
            updates.append({"id": tx["id"], "needs_review": False})
            continue
        group_id = str(uuid.uuid4())
        updates.append({
            "id": tx["id"], "needs_review": False,
            "is_transfer": True, "transfer_group_id": group_id,
        })
        legs.append({
            "date": str(tx["date"])[:10],
            "amount": -float(tx["amount"]),
            "label": tx["label"],
            "source": "manual",
            "business_id": default_business_id(account),
            "account_id": account["id"],
            "category": None,
            "is_transfer": True,
            "transfer_group_id": group_id,
            "needs_review": False,
            "notes": _TRANSFER_NOTE,
        })
    return updates, legs
