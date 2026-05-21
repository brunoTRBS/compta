"""Page Synchronisation — import GoCardless (banque) et Stripe."""

import time
from datetime import date, timedelta

import streamlit as st

from src.config import BusinessId
from src.logic.import_pipeline import run_full_pipeline
from src.services.db_reader import invalidate_cache, read_transactions
from src.services.gocardless import fetch_transactions, list_accounts, map_transaction
from src.services.stripe_client import fetch_payment_intents, map_payment_intent

st.set_page_config(page_title="Synchronisation", page_icon="🔄", layout="wide")
st.title("Synchronisation des données")
st.caption("Importe les transactions bancaires (GoCardless) et les paiements (Stripe).")

_BUSINESS_OPTIONS = {
    "Perso": str(BusinessId.PERSONAL),
    "Phi Rising": str(BusinessId.PHI_RISING),
    "Booth in Lyon": str(BusinessId.BOOTH_IN_LYON),
}


def _get_existing_ids(business_id: str) -> set[str]:
    """Récupère les external_id déjà en base pour la déduplication."""
    try:
        df = read_transactions(business_id=business_id)
        if df.is_empty() or "external_id" not in df.columns:
            return set()
        return set(df.filter(df["external_id"].is_not_null())["external_id"].to_list())
    except Exception:
        return set()


def _render_report(report) -> None:
    """Affiche les métriques du rapport d'import."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Récupérés", report.total_fetched)
    c2.metric("Nouveaux", report.new)
    c3.metric("Doublons ignorés", report.duplicates_ignored)
    c4.metric("Catégorisés auto", report.auto_categorized)
    if report.pending_manual:
        st.info(
            f"{report.pending_manual} transaction(s) sans catégorie — "
            "rendez-vous sur Budget Perso ou une page activité pour les traiter."
        )
    for err in report.errors:
        st.error(err)


# ---------------------------------------------------------------------------
# Filtres de période (communs aux deux sources)
# ---------------------------------------------------------------------------
st.subheader("Période d'import")
col_df, col_dt = st.columns(2)
date_from = col_df.date_input("Date début", value=date.today() - timedelta(days=30), key="sync_from")
date_to = col_dt.date_input("Date fin", value=date.today(), key="sync_to")

if date_from > date_to:
    st.error("La date de début doit être antérieure à la date de fin.")
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# Section GoCardless
# ---------------------------------------------------------------------------
st.subheader("🏦 Banque — GoCardless")

with st.expander("Configuration GoCardless", expanded=True):
    gc_left, gc_right = st.columns([3, 1])
    with gc_left:
        requisition_id = st.text_input(
            "Requisition ID",
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            help="Créez votre réquisition sur bankaccountdata.gocardless.com",
            key="gc_req_id",
        )
        gc_business_label = st.selectbox(
            "Activité", list(_BUSINESS_OPTIONS.keys()), key="gc_biz"
        )
    with gc_right:
        st.write("")
        st.write("")
        st.write("")
        sync_bank = st.button(
            "Synchroniser", key="btn_bank", type="primary", width='stretch'
        )

if sync_bank:
    if not requisition_id.strip():
        st.error("Saisissez un Requisition ID GoCardless.")
    else:
        gc_business_id = _BUSINESS_OPTIONS[gc_business_label]
        with st.status("Synchronisation bancaire…", expanded=True) as status:
            try:
                st.write("Récupération des comptes liés à la réquisition…")
                account_ids = list_accounts(requisition_id.strip())
                st.write(f"→ {len(account_ids)} compte(s) trouvé(s).")

                raw_all: list[dict] = []
                for acc_id in account_ids:
                    st.write(f"Chargement des transactions — compte {acc_id[:8]}…")
                    raw = fetch_transactions(
                        acc_id,
                        date_from=date_from.isoformat(),
                        date_to=date_to.isoformat(),
                    )
                    raw_all.extend(map_transaction(tx, gc_business_id) for tx in raw)

                st.write(f"→ {len(raw_all)} transaction(s) récupérée(s). Déduplication…")
                existing = _get_existing_ids(gc_business_id)
                report = run_full_pipeline(raw_all, existing, source="bank")
                invalidate_cache()

                status.update(label="Synchronisation bancaire terminée ✅", state="complete")
                _render_report(report)

            except Exception as exc:
                status.update(label="Erreur lors de la synchronisation", state="error")
                st.error(str(exc))

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
            ["Phi Rising", "Booth in Lyon"],
            key="stripe_biz",
        )
    with stripe_right:
        st.write("")
        st.write("")
        st.write("")
        sync_stripe = st.button(
            "Synchroniser", key="btn_stripe", type="primary", width='stretch'
        )

if sync_stripe:
    stripe_business_id = _BUSINESS_OPTIONS[stripe_business_label]
    with st.status("Synchronisation Stripe…", expanded=True) as status:
        try:
            since_ts = int(time.mktime(date_from.timetuple()))

            st.write(f"Récupération des PaymentIntents ({stripe_business_label})…")
            pis = fetch_payment_intents(stripe_business_id, created_after=since_ts)
            st.write(f"→ {len(pis)} paiement(s) trouvé(s). Déduplication…")

            mapped = [map_payment_intent(pi, stripe_business_id) for pi in pis]
            existing = _get_existing_ids(stripe_business_id)
            report = run_full_pipeline(mapped, existing, source="stripe")
            invalidate_cache()

            status.update(label="Synchronisation Stripe terminée ✅", state="complete")
            _render_report(report)

        except Exception as exc:
            status.update(label="Erreur lors de la synchronisation Stripe", state="error")
            st.error(str(exc))

st.divider()

# ---------------------------------------------------------------------------
# Historique (dernières synchros)
# ---------------------------------------------------------------------------
st.caption(
    "Les transactions importées apparaissent immédiatement sur les pages "
    "Phi Rising, Booth in Lyon et Budget Perso après synchronisation."
)
