"""Point d'entrée Streamlit multi-page.

Lancer avec : streamlit run app/main.py
"""

import sys
from pathlib import Path

# Garantit que 'src/' et 'app/' sont importables depuis toutes les pages
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

st.set_page_config(
    page_title="Compta Pro & Perso",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Compta Pro & Perso")
st.caption("Gestion comptable — Phi Rising · Booth in Lyon · Budget personnel")

st.markdown("""
Utilisez le menu de navigation à gauche pour accéder aux modules :

| # | Module | Description |
|---|--------|-------------|
| 1 | **Phi Rising** | CA, cotisations URSSAF, marge nette — Coaching & Formation |
| 2 | **Booth in Lyon** | CA, cotisations URSSAF, marge nette — Location Photobooth |
| 3 | **Budget Perso** | Dépenses par catégorie, taux d'épargne, catégorisation |
| 4 | **Patrimoine** | Bilan des comptes et évolution patrimoniale |
| 5 | **Saisie** | Ajout manuel, file d'attente, correction de transactions |
| 6 | **Sync** | Import automatique GoCardless & Stripe |
| 7 | **Paramètres** | Statut des connexions, gestion du cache |
""")
