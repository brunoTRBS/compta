"""Page Synchronisation — import des relevés CSV (BoursoBank, Crédit Mutuel) et Stripe."""

import time
from datetime import date, timedelta
from typing import Any

import polars as pl
import streamlit as st

from app.components.auth import require_auth
from app.components.help import page_title, section_title
from src.config import JOINT_ACCOUNT_NAME, BusinessId
from src.logic.household import (
    classify_joint_transactions,
    default_business_id,
    is_household,
)
from src.logic.import_pipeline import (
    MANUAL_MATCH_WINDOW_DAYS,
    deduplicate,
    match_manual_entries,
    run_full_pipeline,
)
from src.logic.inbox import inbox_rows
from src.logic.reconciliation import statement_closing_balance
from src.logic.statement_parser import (
    BANK_BOURSOBANK,
    UnknownStatementFormat,
    map_statement_transaction,
    parse_statement,
)
from src.logic.transfers import (
    TRANSFER_MATCH_WINDOW_DAYS,
    is_transfer_like,
)
from src.services.db_reader import invalidate_cache, read_manual_candidates, read_transactions
from src.services.stripe_client import fetch_payment_intents, map_payment_intent
from src.services.supabase import (
    fetch_accounts,
    record_statement_balance,
    update_account_bank_number,
)

st.set_page_config(page_title="Synchronisation", page_icon="🔄", layout="wide")
require_auth()
page_title("Synchronisation des données", "sync")
st.caption("Importe les relevés bancaires (CSV BoursoBank, Crédit Mutuel) et les paiements (Stripe).")

_BANK_LABELS = {BANK_BOURSOBANK: "BoursoBank"}
_BANK_LABEL_DEFAULT = "Crédit Mutuel"

# La participation peut être saisie à la main n'importe quand dans le mois :
# fenêtre plus large que pour un paiement carte.
_PARTICIPATION_MATCH_WINDOW_DAYS = 10

_NOT_A_TRANSFER = "❌ Pas un virement (dépense / revenu normal)"

_STRIPE_BUSINESS_MAP = {
    "Phi Rising": str(BusinessId.PHI_RISING),
    "Booth in Lyon": str(BusinessId.BOOTH_IN_LYON),
}


def _get_existing_ids() -> set[str]:
    """Récupère tous les external_id déjà en base (virements et foyer compris) pour la déduplication."""
    try:
        df = read_transactions(include_transfers=True)
        if df.is_empty() or "external_id" not in df.columns:
            return set()
        return set(df.filter(df["external_id"].is_not_null())["external_id"].to_list())
    except Exception:
        return set()


def _get_existing_bank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lignes de relevé déjà en base (tous comptes) pouvant être l'autre côté d'un virement."""
    dates = [date.fromisoformat(str(r["date"])[:10]) for r in rows]
    window = timedelta(days=TRANSFER_MATCH_WINDOW_DAYS)
    df = read_transactions(date_from=min(dates) - window, date_to=max(dates) + window)
    if df.is_empty():
        return []
    return df.filter(pl.col("source") == "bank").to_dicts()


def _treatment(row: dict[str, Any]) -> str:
    """Ce que l'import fera de la ligne, pour l'aperçu."""
    if is_household(row):
        return "🔎 À vérifier" if row.get("needs_review") else "🏠 Foyer (hors budget)"
    if is_transfer_like(row):
        return "🔁 Virement interne"
    return "💰 Budget"


def _render_report(report) -> None:
    """Affiche les métriques du rapport d'import."""
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Récupérés", report.total_fetched)
    c2.metric("Nouveaux", report.new)
    c3.metric("Déjà importés", report.duplicates_ignored)
    c4.metric("Déjà saisis à la main", report.linked_manual)
    c5.metric("Catégorisés auto", report.auto_categorized)
    if report.pending_manual:
        st.info(
            f"{report.pending_manual} transaction(s) sans catégorie — "
            "rendez-vous sur Budget Perso ou une page activité pour les traiter."
        )
    if report.transfers_detected:
        st.success(f"{report.transfers_detected} virement(s) interne(s) reconnu(s) automatiquement.")
    if report.transfers_to_review:
        st.info(
            f"{report.transfers_to_review} virement(s) à confirmer — voir « Virements à vérifier » "
            "plus bas."
        )
    for err in report.errors:
        st.error(err)


def _account_label(account: dict[str, Any]) -> str:
    return f"{account['name']} ({account.get('institution') or '?'})"


# ---------------------------------------------------------------------------
# Section Banque — import des relevés CSV
# ---------------------------------------------------------------------------
section_title("🏦 Banque — Relevés CSV", "sync_banque")
st.caption(
    "Dépose un ou plusieurs relevés : le compte est reconnu automatiquement. "
    "Les opérations déjà importées ou déjà saisies à la main ne sont pas recréées."
)

uploaded_files = st.file_uploader(
    "Relevés CSV (BoursoBank, Crédit Mutuel)",
    type=["csv"],
    accept_multiple_files=True,
    key="bank_csv",
)

try:
    all_accounts = fetch_accounts()
except Exception as exc:
    st.error(f"Impossible de charger les comptes : {exc}")
    all_accounts = []
accounts_by_number = {a["bank_account_number"]: a for a in all_accounts if a.get("bank_account_number")}
accounts_by_label = {_account_label(a): a for a in all_accounts}

# Un "lot" = les lignes d'un fichier appartenant à un même compte
ready_batches: list[dict[str, Any]] = []
existing_ids = _get_existing_ids() if uploaded_files else set()

for uploaded_file in uploaded_files or []:
    try:
        bank, parsed_rows = parse_statement(uploaded_file.getvalue(), uploaded_file.name)
    except UnknownStatementFormat as exc:
        st.error(f"**{uploaded_file.name}** : {exc}")
        continue

    if not parsed_rows:
        st.warning(f"**{uploaded_file.name}** : aucune opération lisible dans ce fichier.")
        continue

    rows_by_number: dict[str | None, list[dict[str, Any]]] = {}
    for row in parsed_rows:
        rows_by_number.setdefault(row["account_number"], []).append(row)

    for number, rows in rows_by_number.items():
        bank_label = _BANK_LABELS.get(bank, _BANK_LABEL_DEFAULT)
        number_label = f"n° …{number[-4:]}" if number else "n° de compte absent"
        with st.container(border=True):
            st.markdown(f"**📄 {uploaded_file.name}** — {bank_label}, {number_label}")

            account = accounts_by_number.get(number) if number else None
            if account:
                st.caption(f"Compte reconnu : **{_account_label(account)}**")
            else:
                choice = st.selectbox(
                    "À quel compte correspond ce relevé ?"
                    + (" (retenu pour les prochains imports)" if number else ""),
                    options=list(accounts_by_label.keys()),
                    index=None,
                    placeholder="Choisir un compte…",
                    key=f"acc_{uploaded_file.name}_{number}",
                )
                account = accounts_by_label.get(choice) if choice else None

            if account is None:
                continue

            # Activité d'affectation (le foyer pour le compte commun) et activité des
            # saisies manuelles à rapprocher (celle du propriétaire du compte)
            business_id = default_business_id(account)
            manual_scope = account["owner"]
            mapped = [map_statement_transaction(r, business_id, account["id"]) for r in rows]
            is_joint = account["name"] == JOINT_ACCOUNT_NAME
            if is_joint:
                mapped = classify_joint_transactions(mapped)
                st.caption(
                    "Compte commun : les opérations sont enregistrées comme dépenses du foyer, "
                    "hors budget perso. Tes paiements carte et tes virements seront à vérifier "
                    "juste en dessous après l'import."
                )
            manual_candidates = read_manual_candidates(manual_scope, rows, MANUAL_MATCH_WINDOW_DAYS)
            new_rows, n_duplicates = deduplicate(mapped, existing_ids)
            new_rows, links = match_manual_entries(new_rows, manual_candidates)

            dates = sorted(r["date"] for r in rows)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Opérations", len(rows), help=f"Du {dates[0]} au {dates[-1]}")
            c2.metric("Déjà importées", n_duplicates)
            c3.metric("Déjà saisies à la main", len(links))
            c4.metric("Nouvelles", len(new_rows))

            if new_rows:
                with st.expander(f"Voir les {len(new_rows)} nouvelle(s) opération(s)"):
                    st.dataframe(
                        pl.DataFrame(new_rows)
                        .select(["date", "label", "amount", "bank_category"])
                        .with_columns(pl.Series("Traitement", [_treatment(r) for r in new_rows]))
                        .rename({
                            "date": "Date", "label": "Libellé",
                            "amount": "Montant", "bank_category": "Catégorie banque",
                        })
                        .to_pandas(),
                        hide_index=True,
                        width="stretch",
                        column_config={"Montant": st.column_config.NumberColumn(format="%.2f €")},
                    )

            ready_batches.append({
                "file": uploaded_file.name,
                "number": number,
                "account": account,
                "rows": rows,
                "mapped": mapped,
                "remember_number": bool(number) and number not in accounts_by_number,
            })

import_btn = st.button(
    f"Importer {len(ready_batches)} relevé(s)" if ready_batches else "Importer",
    key="btn_import_csv",
    type="primary",
    disabled=not ready_batches,
)

if import_btn:
    for batch in ready_batches:
        account_label = _account_label(batch["account"])
        with st.status(f"Import {batch['file']} → {account_label}…", expanded=True) as status:
            try:
                if batch["remember_number"]:
                    update_account_bank_number(batch["account"]["id"], batch["number"])
                report = run_full_pipeline(
                    batch["mapped"],
                    _get_existing_ids(),
                    source="bank",
                    # Relu ici : un lot précédent a pu rattacher certaines saisies
                    manual_transactions=read_manual_candidates(batch["account"]["owner"], batch["rows"], MANUAL_MATCH_WINDOW_DAYS),
                    existing_bank_transactions=_get_existing_bank_rows(batch["rows"]),
                )
                # Solde réel en fin de relevé : sert au contrôle des comptes (page À traiter)
                closing = statement_closing_balance(batch["rows"])
                if closing and not report.errors:
                    try:
                        record_statement_balance(batch["account"]["id"], *closing)
                    except Exception as exc:
                        report.errors.append(f"Solde du relevé non enregistré : {exc}")
                invalidate_cache()
                status.update(label=f"{account_label} : import terminé ✅", state="complete")
                _render_report(report)
            except Exception as exc:
                status.update(label=f"{account_label} : erreur lors de l'import", state="error")
                st.error(str(exc))

st.caption(
    "Exporte les opérations au format CSV depuis l'espace client de la banque. "
    "Crédit Mutuel : garde le nom de fichier d'origine, c'est le n° de compte."
)

# ---------------------------------------------------------------------------
# Ce qui reste à traiter après l'import
# ---------------------------------------------------------------------------
try:
    _pending_df = inbox_rows(read_transactions(include_transfers=True))
    _n_pending = _pending_df.height
    _n_review = _pending_df.filter(pl.col("needs_review")).height if _n_pending else 0
except Exception:
    _n_pending = _n_review = 0

if _n_pending:
    st.info(
        f"**{_n_pending} opération(s) à traiter** dont {_n_review} à vérifier (ta carte sur le "
        "commun, ta participation, virements entre tes comptes)."
    )
    st.page_link("pages/1_A_Traiter.py", label="Aller à la page À traiter", icon="📥")

st.divider()

# ---------------------------------------------------------------------------
# Section Stripe
# ---------------------------------------------------------------------------
section_title("💳 Stripe — Paiements", "sync_stripe")

with st.expander("Configuration Stripe", expanded=True):
    stripe_left, stripe_right = st.columns([3, 1])
    with stripe_left:
        stripe_business_label = st.selectbox(
            "Activité Stripe",
            list(_STRIPE_BUSINESS_MAP.keys()),
            key="stripe_biz",
        )
        stripe_date_from = st.date_input(
            "Depuis le",
            value=date.today() - timedelta(days=30),
            key="stripe_from",
        )
    with stripe_right:
        st.write("")
        st.write("")
        st.write("")
        sync_stripe = st.button(
            "Synchroniser", key="btn_stripe", type="primary", width='stretch'
        )

if sync_stripe:
    stripe_business_id = _STRIPE_BUSINESS_MAP[stripe_business_label]
    with st.status("Synchronisation Stripe…", expanded=True) as status:
        try:
            since_ts = int(time.mktime(stripe_date_from.timetuple()))

            st.write(f"Récupération des PaymentIntents ({stripe_business_label})…")
            pis = fetch_payment_intents(stripe_business_id, created_after=since_ts)
            st.write(f"→ {len(pis)} paiement(s) trouvé(s). Déduplication…")

            mapped = [map_payment_intent(pi, stripe_business_id) for pi in pis]
            existing = _get_existing_ids()
            report = run_full_pipeline(mapped, existing, source="stripe")
            invalidate_cache()

            status.update(label="Synchronisation Stripe terminée ✅", state="complete")
            _render_report(report)

        except Exception as exc:
            status.update(label="Erreur lors de la synchronisation Stripe", state="error")
            st.error(str(exc))

st.divider()

st.caption(
    "Les transactions importées apparaissent immédiatement sur les pages "
    "Phi Rising, Booth in Lyon et Budget Perso après synchronisation."
)
