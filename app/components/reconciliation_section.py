"""Section réutilisable : contrôle de solde des comptes importés."""

from typing import Any

import polars as pl
import streamlit as st

from src.logic.reconciliation import account_status, check_account
from src.services.db_reader import read_statement_balances, read_transactions


def render_reconciliation_section(accounts: list[dict[str, Any]]) -> None:
    """Affiche, pour chaque compte importé, si l'app a bien toutes ses opérations.

    Args:
        accounts: comptes (fetch_accounts) — seuls ceux reconnus par un n° de relevé
            (bank_account_number) sont contrôlés.
    """
    st.subheader("✅ Contrôle des comptes")
    st.caption(
        "À chaque import, l'app note le solde réel du compte. Entre deux relevés, ses "
        "opérations doivent expliquer exactement la variation du solde — sinon il manque "
        "quelque chose (période non importée, opération supprimée, saisie en trop)."
    )

    imported = [a for a in accounts if a.get("bank_account_number")]
    if not imported:
        st.info("Aucun compte importé pour l'instant.")
        return

    for account in sorted(imported, key=lambda a: a["name"]):
        try:
            snapshots = read_statement_balances(account["id"])
        except Exception as exc:
            st.error(f"{account['name']} : impossible de lire les soldes ({exc})")
            continue

        if snapshots.is_empty():
            st.markdown(f"⏳ **{account['name']}** — aucun solde relevé pour l'instant.")
            continue

        last = snapshots.sort("date").row(-1, named=True)
        header = (
            f"**{account['name']}** — solde au {last['date']:%d/%m/%Y} : "
            f"{last['balance']:,.2f} €"
        )
        if snapshots.height < 2:
            st.markdown(f"🆕 {header} — le contrôle commence au prochain import.")
            continue

        transactions = read_transactions(
            date_from=snapshots["date"].min(), include_transfers=True,
        )
        if not transactions.is_empty():
            transactions = transactions.filter(pl.col("account_id") == account["id"])
        periods = check_account(snapshots, transactions)
        complete, total_gap = account_status(periods)

        if complete:
            st.markdown(f"✅ {header} — complet.")
            continue

        st.markdown(f"⚠️ {header} — **écart de {total_gap:+,.2f} €**.")
        with st.expander(f"Détail — {account['name']}"):
            st.caption(
                "Écart positif : il manque une rentrée ou une dépense est en trop dans l'app. "
                "Écart négatif : il manque une dépense ou une rentrée est en trop."
            )
            st.dataframe(
                pl.DataFrame([p for p in periods if abs(p["gap"]) >= 0.01])
                .rename({
                    "start": "Du", "end": "Au", "bank_change": "Variation banque",
                    "app_change": "Opérations app", "gap": "Écart",
                })
                .to_pandas(),
                hide_index=True,
                width="stretch",
                column_config={
                    c: st.column_config.NumberColumn(format="%.2f €")
                    for c in ("Variation banque", "Opérations app", "Écart")
                },
            )
