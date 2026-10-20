"""Onglet Simulateur des activités pro : « si je fais ces prestations, combien me reste-t-il ? »."""

from datetime import date

import polars as pl
import streamlit as st

from src.config import BusinessId
from src.logic.revenue import compute_ytd_summary
from src.logic.simulator import (
    average_monthly_expenses,
    categories_for,
    month_label,
    month_options,
    simulate,
)
from src.services.db_reader import read_transactions

_MONTH_COLUMN, _LABEL_COLUMN, _CATEGORY_COLUMN, _AMOUNT_COLUMN, _FEES_COLUMN = (
    "Mois", "Prestation", "Type de revenu", "Montant encaissé (€)", "Frais Stripe (€)"
)


def _eur(value: float) -> str:
    return f"{value:,.2f} €".replace(",", " ")


def render_simulator(business_id: BusinessId) -> None:
    """Calculateur : rien n'est enregistré, c'est un brouillon pour prévoir les mois à venir."""
    today = date.today()
    key = f"sim_{business_id}"
    months = month_options(today)
    labels = [month_label(m) for m in months]
    by_label = dict(zip(labels, months, strict=True))
    categories = categories_for(business_id)

    st.caption(
        "Ajoute les prestations que tu espères faire (un mois, un type de revenu, un montant). "
        "L'app calcule l'URSSAF avec les mêmes taux que tes chiffres réels et te dit ce qu'il te reste. "
        "**Rien n'est enregistré** : c'est un brouillon."
    )

    try:
        history = read_transactions(business_id=str(business_id))
    except Exception:
        history = pl.DataFrame()
    suggested_charges = average_monthly_expenses(history, today)

    col_charges, col_vl = st.columns(2)
    charges = col_charges.number_input(
        "Charges pro par mois (€)",
        min_value=0.0,
        value=float(suggested_charges),
        step=10.0,
        key=f"{key}_charges",
        help="Abonnements, outils, loyer coworking… Proposé : la moyenne de tes 3 derniers mois "
             "de dépenses pro (hors frais Stripe). Compté chaque mois simulé.",
    )
    with_vl = col_vl.checkbox(
        "Je suis au versement libératoire de l'impôt",
        key=f"{key}_vl",
        help="Ajoute l'impôt prélevé en même temps que l'URSSAF (2,2 % pour le BNC).",
    )

    default_rows = pl.DataFrame({
        _MONTH_COLUMN: [labels[0], labels[0]],
        _LABEL_COLUMN: ["Exemple : séance de coaching", "Exemple : atelier"],
        _CATEGORY_COLUMN: [categories[0]] * 2,
        _AMOUNT_COLUMN: [300.0, 500.0],
        _FEES_COLUMN: [0.0, 0.0],
    })
    edited = st.data_editor(
        default_rows.to_pandas(),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            _MONTH_COLUMN: st.column_config.SelectboxColumn(options=labels, required=True),
            _LABEL_COLUMN: st.column_config.TextColumn(),
            _CATEGORY_COLUMN: st.column_config.SelectboxColumn(
                options=categories, required=True,
                help="Le type de revenu décide du taux d'URSSAF (ND = non déclaré, taux 0 %).",
            ),
            _AMOUNT_COLUMN: st.column_config.NumberColumn(min_value=0.0, step=10.0, format="%.2f"),
            _FEES_COLUMN: st.column_config.NumberColumn(
                min_value=0.0, step=1.0, format="%.2f",
                help="Frais prélevés par Stripe sur ce paiement : ils réduisent la base de l'URSSAF.",
            ),
        },
        key=f"{key}_table",
    )

    prestations = [
        {
            "month": by_label.get(row[_MONTH_COLUMN]),
            "label": row[_LABEL_COLUMN],
            "category": row[_CATEGORY_COLUMN],
            "amount": row[_AMOUNT_COLUMN],
            "fees": row[_FEES_COLUMN],
        }
        for row in edited.to_dict("records")
    ]
    ytd = compute_ytd_summary(history, business_id, today.year)["ca"] if not history.is_empty() else 0.0
    result = simulate(prestations, charges, business_id, ytd, with_vl, year=today.year)

    if not result["months"]:
        st.info("Ajoute une prestation avec un montant pour voir le résultat.")
        return

    total = result["total"]
    st.subheader("Ce qu'il te reste")
    col_ca, col_urssaf, col_costs, col_left = st.columns(4)
    col_ca.metric("Chiffre d'affaires", _eur(total["ca"]))
    col_urssaf.metric("URSSAF" + (" + impôt" if with_vl else ""), _eur(total["urssaf"]))
    col_costs.metric("Charges + frais Stripe", _eur(total["charges"] + total["stripe_fees"]))
    col_left.metric("Il te reste", _eur(total["remaining"]),
                    delta=f"{total['remaining'] / total['ca'] * 100:.0f} % du CA" if total["ca"] else None)

    st.dataframe(
        pl.DataFrame([
            {
                "Mois": month_label(m["month"]),
                "CA": m["ca"],
                "URSSAF": m["urssaf"],
                "Charges + frais Stripe": m["charges"] + m["stripe_fees"],
                "Il te reste": m["remaining"],
            }
            for m in result["months"]
        ]).to_pandas(),
        hide_index=True,
        width="stretch",
        column_config={
            name: st.column_config.NumberColumn(format="%.2f €")
            for name in ("CA", "URSSAF", "Charges + frais Stripe", "Il te reste")
        },
    )

    # Seuils annuels (année en cours seulement : c'est celle dont on connaît le CA déjà encaissé)
    if result["ca_after"] > result["threshold"]:
        st.error(
            f"Avec ces prestations, ton CA {today.year} atteindrait {_eur(result['ca_after'])} : "
            f"au-dessus du plafond micro-entreprise ({_eur(result['threshold'])})."
        )
    elif result["ca_after"] > result["tva_threshold"]:
        st.warning(
            f"Ton CA {today.year} atteindrait {_eur(result['ca_after'])} : au-dessus du seuil de la "
            f"franchise de TVA ({_eur(result['tva_threshold'])})."
        )
    elif ytd:
        st.caption(
            f"CA {today.year} déjà encaissé : {_eur(ytd)} → après simulation : {_eur(result['ca_after'])} "
            f"(plafond micro-entreprise : {_eur(result['threshold'])})."
        )
