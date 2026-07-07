"""Parseur CSV pour les exports de relevés Boursobank."""

import csv
import hashlib
import io
from typing import Any


def parse_boursobank_csv(content: bytes | str) -> list[dict[str, Any]]:
    """Parse un export CSV Boursobank, retourne list[{date, amount, label}].

    Format attendu (séparateur ';', quotechar '"', dates ISO YYYY-MM-DD) :
        dateOp;dateVal;label;suggestedLabel;category;categoryParent;amount;...
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")  # utf-8-sig absorbe le BOM éventuel

    reader = csv.DictReader(io.StringIO(content), delimiter=";", quotechar='"')
    results: list[dict[str, Any]] = []

    for row in reader:
        date_str = (row.get("dateOp") or "").strip()
        label = (row.get("label") or "").strip()
        amount_str = (row.get("amount") or "").strip()

        if not date_str or not label or not amount_str:
            continue

        amount = _parse_amount(amount_str)
        if amount is None:
            continue

        results.append({"date": date_str, "amount": amount, "label": label})

    return results


def _parse_amount(text: str) -> float | None:
    """Parse un montant au format Boursobank : '-0,86' ou '1 234,56' → float."""
    try:
        normalized = (
            text.strip()
            .replace(" ", "")  # espace fine insécable
            .replace("\xa0", "")    # espace insécable
            .replace(" ", "")
            .replace(",", ".")
        )
        return float(normalized)
    except (ValueError, AttributeError):
        return None


def build_external_id(date: str, amount: float, label: str) -> str:
    """Génère un identifiant stable pour la déduplication.

    SHA256(date|amount|label)[:16] → 'bourso_xxxxxxxxxxxxxxxx'
    """
    raw = f"{date}|{amount}|{label.lower().strip()}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"bourso_{digest}"


def map_statement_transaction(raw: dict[str, Any], business_id: str) -> dict[str, Any]:
    """Transforme une ligne parsée en schéma de la table transactions."""
    return {
        "date": raw["date"],
        "amount": raw["amount"],
        "label": raw["label"],
        "source": "bank",
        "business_id": business_id,
        "category": None,
        "external_id": build_external_id(raw["date"], raw["amount"], raw["label"]),
        "notes": None,
    }
