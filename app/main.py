"""Point d'entrée Streamlit multi-page.

Lancer avec : streamlit run app/main.py
"""

import sys
from pathlib import Path

# Ajoute la racine du projet EN FIN de sys.path pour que les packages installés
# (ex: supabase-py) soient trouvés avant le dossier local supabase/ de la CLI.
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.append(_project_root)

import streamlit as st

from app.components.auth import require_auth

st.set_page_config(
    page_title="Compta Pro & Perso",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

require_auth()

st.title("Compta Pro & Perso")
st.caption("Gestion comptable — Phi Rising · Booth in Lyon · Budget personnel")

st.markdown("""
Utilisez le menu de navigation à gauche pour accéder aux modules :

| # | Module | Description |
|---|--------|-------------|
| 1 | **Saisie** | Ajout manuel, virements entre comptes, file d'attente, correction de transactions |
| 2 | **Vue consolidée** | Perso + Phi Rising + Booth in Lyon sur une même vue, détail par compte réel |
| 3 | **Phi Rising** | CA, cotisations URSSAF, marge nette — Coaching & Formation |
| 4 | **Booth in Lyon** | CA, cotisations URSSAF, marge nette — Location Photobooth |
| 5 | **Budget Perso** | Revenus et dépenses par catégorie, taux d'épargne, catégorisation |
| 6 | **Patrimoine** | Bilan des comptes et évolution patrimoniale |
| 7 | **Sync** | Import automatique GoCardless & Stripe |
| 8 | **Paramètres** | Statut des connexions, gestion du cache |
""")
