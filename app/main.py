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
from app.components.help import page_title

st.set_page_config(
    page_title="Compta Pro & Perso",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

require_auth()

page_title("Compta Pro & Perso", "accueil")
st.caption("Gestion comptable — Phi Rising · Booth in Lyon · Budget personnel")

st.markdown("""
Utilise le menu de navigation à gauche (dans cet ordre). Chaque page a une bulle **ℹ️** en haut à droite
qui rappelle comment elle fonctionne.

| Page | À quoi ça sert |
|------|----------------|
| 📘 **Guide** | Le tutoriel complet : comment se servir de l'app, page par page, avec des exemples et des scénarios |
| 📥 **À traiter** | La boîte de réception : affecter et classer les lignes importées, règles automatiques, contrôle des comptes |
| 🧮 **Vue consolidée** | Perso, Phi Rising, Booth in Lyon et Foyer sur une même vue, détail par compte réel |
| 🎯 **Phi Rising** | Coaching & Formation : transactions, récurrences, CA, URSSAF, bénéfice |
| 📸 **Booth in Lyon** | Location photobooth : transactions, récurrences, CA, URSSAF, bénéfice |
| 💰 **Budget Perso** | Ton budget : revenus, dépenses, épargne, reste du mois, où part l'argent |
| 🏠 **Budget Foyer** | Le compte commun : rentrées, dépenses communes, qui met quoi, opérations exceptionnelles |
| 🏦 **Patrimoine** | Bilan des comptes et évolution de tes soldes |
| 🔄 **Sync** | Import des relevés bancaires (CSV) et synchro Stripe |
| ⚙️ **Paramètres** | Catégories partagées, sauvegarde, statut des connexions, cache |
| 🧭 **Règles** | Voir, corriger et tester les règles de rangement automatique |
| 🔎 **Transactions** | Toutes les opérations : recherche, correction, déplacement d'un budget à l'autre, actions groupées |
""")

