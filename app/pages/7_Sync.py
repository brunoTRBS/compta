"""Page Synchronisation — import des relevés CSV (BoursoBank, Crédit Mutuel) et Stripe."""

import time
from datetime import date, timedelta
from typing import Any

import polars as pl
import streamlit as st

from app.components.auth import require_auth
from src.config import JOINT_ACCOUNT_NAME, PARTICIPATION_LABEL, BusinessId
from src.logic.household import (
    KIND_CARD,
    classify_joint_transactions,
    default_business_id,
    default_counts_in_budget,
    is_household,
    resolve_review,
    review_kind,
)
from src.logic.import_pipeline import (
    MANUAL_MATCH_WINDOW_DAYS,
    deduplicate,
    match_manual_entries,
    run_full_pipeline,
)
from src.logic.reconciliation import statement_closing_balance
from src.logic.statement_parser import (
    BANK_BOURSOBANK,
    UnknownStatementFormat,
    map_statement_transaction,
    parse_statement,
)
from src.logic.transfers import (
    TRANSFER_MATCH_WINDOW_DAYS,
    default_counterpart,
    is_transfer_like,
    resolve_transfer_review,
)
from src.services.db_reader import invalidate_cache, read_transactions
from src.services.stripe_client import fetch_payment_intents, map_payment_intent
from src.services.supabase import (
    bulk_update_transaction_fields,
    bulk_upsert_transactions,
    fetch_accounts,
    insert_transactions,
    link_transactions_to_bank,
    record_statement_balance,
    update_account_bank_number,
)

st.set_page_config(page_title="Synchronisation", page_icon="🔄", layout="wide")
require_auth()
st.title("Synchronisation des données")
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


def _get_manual_candidates(
    business_id: str,
    rows: list[dict[str, Any]],
    window_days: int = MANUAL_MATCH_WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """Saisies manuelles pas encore rattachées à un relevé, sur la période des lignes."""
    dates = [date.fromisoformat(str(r["date"])[:10]) for r in rows]
    window = timedelta(days=window_days)
    df = read_transactions(
        business_id=business_id,
        date_from=min(dates) - window,
        date_to=max(dates) + window,
        include_transfers=True,
    )
    if df.is_empty():
        return []
    return df.filter(
        (pl.col("source") == "manual") & pl.col("external_id").is_null()
    ).to_dicts()


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
st.subheader("🏦 Banque — Relevés CSV")
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
            manual_candidates = _get_manual_candidates(manual_scope, rows)
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
                    manual_transactions=_get_manual_candidates(batch["account"]["owner"], batch["rows"]),
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
# Section Compte commun — opérations à vérifier
# ---------------------------------------------------------------------------
try:
    all_review_df = read_transactions().filter(pl.col("needs_review"))
except Exception as exc:
    st.error(f"Impossible de charger les opérations à vérifier : {exc}")
    all_review_df = pl.DataFrame()

_household_scope = str(BusinessId.HOUSEHOLD)
review_df = (
    all_review_df.filter(pl.col("business_id") == _household_scope)
    if not all_review_df.is_empty() else all_review_df
)
transfer_review_df = (
    all_review_df.filter(pl.col("business_id") != _household_scope)
    if not all_review_df.is_empty() else all_review_df
)

if not review_df.is_empty():
    st.divider()
    st.subheader(f"🔎 Compte commun — {len(review_df)} opération(s) à vérifier")
    st.caption(
        "Coche ce qui compte dans **ton** budget. Un paiement avec ta carte coché devient une "
        f"dépense perso ; décoché, il reste une dépense du foyer. Un virement de ta part coché "
        f"crée la dépense « {PARTICIPATION_LABEL} » — inutile de la saisir à la main, "
        "et celles déjà saisies ne sont pas recréées."
    )
    review_rows = review_df.sort("date").to_dicts()
    editor_df = pl.DataFrame({
        "id": [r["id"] for r in review_rows],
        "Date": [r["date"] for r in review_rows],
        "Type": [
            "💳 Ton paiement carte" if review_kind(r) == KIND_CARD else "↘️ Ton virement"
            for r in review_rows
        ],
        "Libellé": [r.get("raw_label") or r["label"] for r in review_rows],
        "Montant": [r["amount"] for r in review_rows],
        "Compte dans mon budget": [default_counts_in_budget(r) for r in review_rows],
    })
    edited = st.data_editor(
        editor_df.to_pandas(),
        hide_index=True,
        width="stretch",
        disabled=["id", "Date", "Type", "Libellé", "Montant"],
        column_config={
            "id": None,
            "Montant": st.column_config.NumberColumn(format="%.2f €"),
            "Compte dans mon budget": st.column_config.CheckboxColumn(),
        },
        key="joint_review_editor",
    )

    if st.button("Valider", key="btn_joint_review", type="primary"):
        try:
            choices = dict(zip(edited["id"], edited["Compte dans mon budget"], strict=True))
            updates, participations = resolve_review(review_rows, choices)

            n_already_entered = 0
            if participations:
                # Mêmes règles qu'à l'import : une participation déjà saisie à la main
                # n'est pas recréée, la saisie reçoit juste la référence bancaire.
                candidates = [
                    c for c in _get_manual_candidates(
                        str(BusinessId.PERSONAL), participations, _PARTICIPATION_MATCH_WINDOW_DAYS,
                    )
                    if c["amount"] < 0
                ]
                to_insert, links = match_manual_entries(
                    [{**p, "account_id": None} for p in participations],
                    candidates,
                    window_days=_PARTICIPATION_MATCH_WINDOW_DAYS,
                )
                link_transactions_to_bank(links)
                inserted_ids = {p["external_id"] for p in to_insert}
                to_insert = [p for p in participations if p["external_id"] in inserted_ids]
                if to_insert:
                    bulk_upsert_transactions(to_insert)
                n_already_entered = len(links)

            bulk_update_transaction_fields(updates)
            invalidate_cache()
            n_perso = sum(1 for u in updates if u["business_id"] == str(BusinessId.PERSONAL))
            message = (
                f"{n_perso} achat(s) perso, {len(participations)} participation(s) "
                f"(dont {n_already_entered} déjà saisie(s) à la main)."
            )
            st.toast(message, icon="✅")
            st.rerun()
        except Exception as exc:
            st.error(f"Erreur lors de la validation : {exc}")

# ---------------------------------------------------------------------------
# Section Virements à vérifier — un seul côté du virement est importé
# ---------------------------------------------------------------------------
if not transfer_review_df.is_empty():
    st.divider()
    st.subheader(f"🔁 Virements à vérifier — {len(transfer_review_df)}")
    st.caption(
        "Virements entre tes comptes dont l'autre côté n'est pas importé (ex : ton virement "
        "depuis le compte pro). Indique l'autre compte : la ligne devient un virement interne, "
        "compté comme si tu l'avais saisi dans l'onglet Virement — inutile de le faire. "
        "Un virement vers ou depuis le compte commun : choisis « Pas un virement »."
    )
    transfer_accounts = [a for a in all_accounts if a["name"] != JOINT_ACCOUNT_NAME]
    transfer_options = {_account_label(a): a for a in transfer_accounts}
    account_names = {a["id"]: a["name"] for a in all_accounts}
    transfer_rows = transfer_review_df.sort("date").to_dicts()

    def _default_option(row: dict[str, Any]) -> str:
        account = default_counterpart(row, transfer_accounts)
        return _account_label(account) if account else _NOT_A_TRANSFER

    transfer_editor_df = pl.DataFrame({
        "id": [r["id"] for r in transfer_rows],
        "Date": [r["date"] for r in transfer_rows],
        "Compte": [account_names.get(r["account_id"], "?") for r in transfer_rows],
        "Libellé": [r.get("raw_label") or r["label"] for r in transfer_rows],
        "Montant": [r["amount"] for r in transfer_rows],
        "Autre compte": [_default_option(r) for r in transfer_rows],
    })
    transfer_edited = st.data_editor(
        transfer_editor_df.to_pandas(),
        hide_index=True,
        width="stretch",
        disabled=["id", "Date", "Compte", "Libellé", "Montant"],
        column_config={
            "id": None,
            "Montant": st.column_config.NumberColumn(format="%.2f €"),
            "Autre compte": st.column_config.SelectboxColumn(
                options=[*transfer_options.keys(), _NOT_A_TRANSFER], required=True,
            ),
        },
        key="transfer_review_editor",
    )

    if st.button("Valider", key="btn_transfer_review", type="primary"):
        try:
            counterparts = {
                row_id: transfer_options.get(choice)
                for row_id, choice in zip(transfer_edited["id"], transfer_edited["Autre compte"], strict=True)
            }
            updates, legs = resolve_transfer_review(transfer_rows, counterparts)
            insert_transactions(legs)
            bulk_update_transaction_fields(updates)
            invalidate_cache()
            st.toast(f"{len(legs)} virement(s) enregistré(s).", icon="✅")
            st.rerun()
        except Exception as exc:
            st.error(f"Erreur lors de la validation : {exc}")

st.divider()

# ---------------------------------------------------------------------------
# Section Stripe
# ---------------------------------------------------------------------------
st.subheader("💳 Stripe — Paiements")

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
