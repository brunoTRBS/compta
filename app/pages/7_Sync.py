"""Page Synchronisation — import relevé CSV BoursoBank et Stripe."""

import time
from datetime import date, timedelta

import streamlit as st

from src.config import BusinessId
from src.logic.statement_parser import map_statement_transaction, parse_boursobank_csv
from src.logic.import_pipeline import run_full_pipeline
from src.services.db_reader import invalidate_cache, read_transactions
from src.services.stripe_client import fetch_payment_intents, map_payment_intent
from app.components.auth import require_auth

st.set_page_config(page_title="Synchronisation", page_icon="🔄", layout="wide")
require_auth()
st.title("Synchronisation des données")
st.caption("Importe les transactions bancaires (relevé CSV BoursoBank) et les paiements (Stripe).")

_BUSINESS_LABELS: dict[str, str] = {
    str(BusinessId.PERSONAL): "Perso",
    str(BusinessId.PHI_RISING): "Phi Rising",
    str(BusinessId.BOOTH_IN_LYON): "Booth in Lyon",
}

_STRIPE_BUSINESS_MAP = {
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
# Section BoursoBank — import par relevé CSV
# ---------------------------------------------------------------------------
st.subheader("🏦 Banque — Relevé CSV BoursoBank")

col_biz, col_upload = st.columns([1, 2])

with col_biz:
    bank_business_id = st.selectbox(
        "Compte / Activité",
        options=list(_BUSINESS_LABELS.keys()),
        format_func=_BUSINESS_LABELS.get,
        key="bank_biz",
    )

with col_upload:
    uploaded_file = st.file_uploader(
        "Relevé CSV BoursoBank",
        type=["csv"],
        key="bank_csv",
    )

import_btn = st.button(
    "Importer",
    key="btn_import_csv",
    type="primary",
    disabled=uploaded_file is None,
)

if import_btn and uploaded_file is not None:
    with st.status("Import du relevé BoursoBank…", expanded=True) as status:
        try:
            st.write("Lecture du fichier CSV…")
            raw_rows = parse_boursobank_csv(uploaded_file.read())

            if not raw_rows:
                status.update(label="Aucune transaction détectée.", state="complete")
                st.warning(
                    "Le fichier ne contient aucune transaction lisible. "
                    "Vérifiez que l'export est au format CSV BoursoBank standard."
                )
            else:
                st.write(f"→ {len(raw_rows)} ligne(s) lue(s). Déduplication…")
                mapped = [map_statement_transaction(r, bank_business_id) for r in raw_rows]
                existing = _get_existing_ids(bank_business_id)
                report = run_full_pipeline(mapped, existing, source="bank")
                invalidate_cache()

                status.update(label="Import terminé ✅", state="complete")
                _render_report(report)

        except Exception as exc:
            status.update(label="Erreur lors de l'import", state="error")
            st.error(str(exc))

st.caption(
    "Exportez le relevé depuis BoursoBank : Espace client → Mes comptes → "
    "Télécharger le relevé → Format CSV."
)

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
            existing = _get_existing_ids(stripe_business_id)
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
