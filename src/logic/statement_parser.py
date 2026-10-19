"""Parseurs des relevés bancaires CSV (BoursoBank, Crédit Mutuel, Hello Bank).

Chaque ligne parsée porte le n° de compte d'où elle vient, ce qui permet à la
page Sync de reconnaître le compte toute seule (accounts.bank_account_number).
"""

import csv
import hashlib
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any

BANK_BOURSOBANK = "boursobank"
BANK_CREDIT_MUTUEL = "credit_mutuel"
BANK_HELLO_BANK = "hello_bank"

_EXTERNAL_ID_PREFIX = {BANK_BOURSOBANK: "bourso", BANK_CREDIT_MUTUEL: "cm", BANK_HELLO_BANK: "hello"}

# Catégorie BoursoBank qui ne porte aucune information
_BOURSO_UNCATEGORIZED = "non catégorisé"

# Colonnes BoursoBank, par position. Deux en-têtes existent selon l'export :
#   dateOp;dateVal;label;suggestedLabel;category;categoryParent;amount;comment;accountNum;accountLabel;accountbalance
#   "Date Opération";"Date Valeur";Libellé;"Libellé Suggéré";Catégorie;"Catégorie Parente";Solde;Commentaire;"Numéro Compte";"Libellé Compte";Solde;Pointage
# Le second nomme "Solde" à la fois le montant (col. 6) et le solde du compte
# (col. 10) : on lit donc par position, jamais par nom de colonne.
_B_DATE, _B_LABEL, _B_SUGGESTED, _B_CATEGORY, _B_AMOUNT, _B_ACCOUNT, _B_BALANCE = 0, 2, 3, 4, 6, 8, 10

# Colonnes Crédit Mutuel : Date;Date de valeur;Débit;Crédit;Libellé;Solde
_CM_DATE, _CM_DEBIT, _CM_CREDIT, _CM_LABEL, _CM_BALANCE = 0, 2, 3, 4, 5


# Colonnes Hello Bank (compte pro), sans ligne d'en-tête de colonnes :
#   1re ligne : type de compte;type de compte;****9077;date de l'export;;solde
#   puis : date opération;type;libellé court;libellé complet;date valeur;montant
_H_DATE, _H_LABEL, _H_AMOUNT = 0, 3, 5


class UnknownStatementFormat(ValueError):
    """Le fichier n'est ni un export BoursoBank, ni Crédit Mutuel, ni Hello Bank."""


def _decode(content: bytes | str) -> str:
    """Décode le fichier : UTF-8 (BoursoBank) ou Windows-1252 (Crédit Mutuel)."""
    if isinstance(content, str):
        return content
    try:
        return content.decode("utf-8-sig")  # utf-8-sig absorbe le BOM éventuel
    except UnicodeDecodeError:
        return content.decode("cp1252")


def _rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text), delimiter=";", quotechar='"'))


def _cell(row: list[str], idx: int) -> str:
    return row[idx].strip() if idx < len(row) else ""


def detect_bank(content: bytes | str) -> str | None:
    """Reconnaît la banque d'après l'en-tête du fichier."""
    rows = _rows(_decode(content))
    if not rows:
        return None
    if _is_hello_bank_header(rows[0]):
        return BANK_HELLO_BANK
    header = [c.strip().lower() for c in rows[0]]
    if header and header[0] in ("dateop", "date opération"):
        return BANK_BOURSOBANK
    if header[:2] == ["date", "date de valeur"]:
        return BANK_CREDIT_MUTUEL
    return None


def _is_hello_bank_header(row: list[str]) -> bool:
    """1re ligne d'un export Hello Bank : n° de compte masqué (****9077) puis une date."""
    return (
        len(row) >= 6
        and re.fullmatch(r"\*+\d{3,}", _cell(row, 2)) is not None
        and _parse_fr_date(_cell(row, 3)) is not None
    )


def _hello_bank_label(raw: str) -> str:
    """Libellé lisible d'une ligne Hello Bank (le libellé complet est gardé en raw_label)."""
    text = " ".join(raw.split())
    if match := re.match(r"FACTURE CARTE DU \d{6} (.+?) CARTE\b", text):
        return match.group(1).strip()
    if match := re.match(r"PRLV SEPA (.+?) (?:ECH|ID EMETTEUR)\b", text):
        return f"Prélèvement {match.group(1).strip()}"
    if match := re.search(r"/FRM (.+?) /EID", text):
        return f"Virement de {match.group(1).strip()}"
    if match := re.search(r"/BEN (.+?) /REF", text):
        motive = re.search(r"/MOTIF (.+?) /BEN", text)
        return f"Virement vers {match.group(1).strip()}" + (f" ({motive.group(1).strip()})" if motive else "")
    if text.startswith("COMMISSIONS HELLO BUSINESS"):
        return "Commission Hello Business"
    if text.startswith("RETRAIT DAB"):
        return "Retrait distributeur"
    return text


def parse_hello_bank_csv(content: bytes | str) -> list[dict[str, Any]]:
    """Parse un export CSV Hello Bank (compte pro).

    Le n° de compte (masqué : ****9077) et le solde du compte sont sur la 1re ligne ;
    le solde est rattaché à la dernière opération pour le contrôle des comptes.

    Returns:
        list[{date, amount, label, suggested_label, bank_category, account_number, balance}]
    """
    rows = _rows(_decode(content))
    if not rows or not _is_hello_bank_header(rows[0]):
        return []
    account_number = _cell(rows[0], 2)
    results: list[dict[str, Any]] = []
    for row in rows[1:]:
        date_str = _parse_fr_date(_cell(row, _H_DATE))
        label = " ".join(_cell(row, _H_LABEL).split())
        amount = _parse_amount(_cell(row, _H_AMOUNT))
        if not date_str or not label or amount is None:
            continue
        results.append({
            "date": date_str,
            "amount": amount,
            "label": label,
            "suggested_label": _hello_bank_label(label),
            "bank_category": None,
            "account_number": account_number,
            "balance": None,
        })
    if results:
        results[-1]["balance"] = _parse_amount(_cell(rows[0], 5))
    return results


def parse_boursobank_csv(content: bytes | str) -> list[dict[str, Any]]:
    """Parse un export CSV BoursoBank (ancien ou nouveau format).

    Returns:
        list[{date, amount, label, suggested_label, bank_category, account_number, balance}]
        où label est le libellé brut de la banque.
    """
    results: list[dict[str, Any]] = []
    for row in _rows(_decode(content))[1:]:
        date_str = _cell(row, _B_DATE)
        label = _cell(row, _B_LABEL)
        amount = _parse_amount(_cell(row, _B_AMOUNT))
        if not date_str or not label or amount is None:
            continue

        category = _cell(row, _B_CATEGORY)
        results.append({
            "date": date_str,
            "amount": amount,
            "label": label,
            "suggested_label": _cell(row, _B_SUGGESTED) or None,
            "bank_category": None if category.lower() in ("", _BOURSO_UNCATEGORIZED) else category,
            "account_number": _cell(row, _B_ACCOUNT) or None,
            "balance": _parse_amount(_cell(row, _B_BALANCE)),
        })
    return results


def parse_credit_mutuel_csv(
    content: bytes | str,
    account_number: str | None = None,
) -> list[dict[str, Any]]:
    """Parse un export CSV Crédit Mutuel.

    Le fichier ne contient pas le n° de compte : il est passé par l'appelant
    (voir account_number_from_filename).

    Returns:
        list[{date, amount, label, suggested_label, bank_category, account_number, balance}]
    """
    results: list[dict[str, Any]] = []
    for row in _rows(_decode(content))[1:]:
        date_str = _parse_fr_date(_cell(row, _CM_DATE))
        label = _cell(row, _CM_LABEL)
        debit = _parse_amount(_cell(row, _CM_DEBIT))
        credit = _parse_amount(_cell(row, _CM_CREDIT))
        amount = debit if debit is not None else credit
        if not date_str or not label or amount is None:
            continue

        results.append({
            "date": date_str,
            # Le débit est déjà négatif dans l'export ; abs() protège d'un export non signé
            "amount": -abs(amount) if debit is not None else abs(amount),
            "label": label,
            "suggested_label": None,
            "bank_category": None,
            "account_number": account_number,
            "balance": _parse_amount(_cell(row, _CM_BALANCE)),
        })
    return results


def account_number_from_filename(filename: str | None) -> str | None:
    """Le Crédit Mutuel nomme l'export d'après le n° de compte (ex : 00022222901.csv)."""
    if not filename:
        return None
    stem = Path(filename).stem
    return stem if re.fullmatch(r"\d{6,}", stem) else None


def parse_statement(content: bytes | str, filename: str | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Détecte la banque, parse le relevé et attribue un external_id à chaque ligne.

    Returns:
        (banque, lignes) — chaque ligne porte son external_id.

    Raises:
        UnknownStatementFormat: si l'en-tête n'est reconnu ni comme BoursoBank ni
            comme Crédit Mutuel.
    """
    text = _decode(content)
    bank = detect_bank(text)
    if bank == BANK_BOURSOBANK:
        rows = parse_boursobank_csv(text)
    elif bank == BANK_CREDIT_MUTUEL:
        rows = parse_credit_mutuel_csv(text, account_number_from_filename(filename))
    elif bank == BANK_HELLO_BANK:
        rows = parse_hello_bank_csv(text)
    else:
        raise UnknownStatementFormat(
            "Format de relevé non reconnu (attendu : export CSV BoursoBank, Crédit Mutuel ou Hello Bank)."
        )

    # Deux opérations identiques le même jour (2 cafés au même endroit) doivent
    # rester 2 lignes : la 2e reçoit un n° d'occurrence dans son identifiant.
    seen: dict[tuple, int] = {}
    for row in rows:
        key = (row["account_number"], row["date"], row["amount"], row["label"].lower())
        seen[key] = seen.get(key, 0) + 1
        row["external_id"] = build_external_id(
            row["date"], row["amount"], row["label"],
            prefix=_EXTERNAL_ID_PREFIX[bank], occurrence=seen[key],
        )
    return bank, rows


def _parse_amount(text: str) -> float | None:
    """Parse un montant bancaire : '-0,86', '1 234,56' ou '0.96' → float."""
    try:
        normalized = (
            text.strip()
            .replace(" ", "")  # espace fine insécable
            .replace("\xa0", "")    # espace insécable
            .replace(" ", "")
            .replace(",", ".")
        )
        return float(normalized)
    except (ValueError, AttributeError):
        return None


def _parse_fr_date(text: str) -> str | None:
    """'28/09/2026' → '2026-09-28'."""
    try:
        return datetime.strptime(text.strip(), "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def build_external_id(
    date: str,
    amount: float,
    label: str,
    prefix: str = "bourso",
    occurrence: int = 1,
) -> str:
    """Génère un identifiant stable pour la déduplication.

    SHA256(date|amount|label)[:16] → 'bourso_xxxxxxxxxxxxxxxx'. La 1re occurrence
    garde la forme historique, pour reconnaître les lignes déjà importées.
    """
    raw = f"{date}|{amount}|{label.lower().strip()}"
    if occurrence > 1:
        raw += f"|{occurrence}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{prefix}_{digest}"


def map_statement_transaction(
    raw: dict[str, Any],
    business_id: str,
    account_id: str | None = None,
) -> dict[str, Any]:
    """Transforme une ligne parsée en schéma de la table transactions.

    label reçoit le libellé nettoyé par la banque s'il existe (« La Villa Marlioz »),
    raw_label garde toujours le libellé brut (« CARTE 10/10/26 VILLA MARLIOZ 4 CB*8589 »).
    """
    return {
        "date": raw["date"],
        "amount": raw["amount"],
        "label": raw.get("suggested_label") or raw["label"],
        "raw_label": raw["label"],
        "bank_category": raw.get("bank_category"),
        "source": "bank",
        "business_id": business_id,
        "account_id": account_id,
        "category": None,
        "external_id": raw.get("external_id")
        or build_external_id(raw["date"], raw["amount"], raw["label"]),
        "notes": None,
        "needs_review": False,
        # Tous les champs sont présents sur chaque ligne : en insertion par lot,
        # un champ absent serait envoyé à NULL (refusé pour is_transfer).
        "is_transfer": False,
        "transfer_group_id": None,
        "is_exceptional": False,
    }
