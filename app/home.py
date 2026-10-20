"""Page d'accueil : les trois gestes de la semaine et le plan de l'application."""

import streamlit as st

from app.components.auth import require_auth
from app.components.help import page_title

st.set_page_config(page_title="Compta Pro & Perso", page_icon="📊", layout="wide")
require_auth()

page_title("Bienvenue 👋", "accueil")
st.caption("Phi Rising · Booth in Lyon · Mon budget · Budget du foyer")

st.markdown("""
### Chaque semaine, 3 gestes

1. **🔄 Importer** : dépose les relevés CSV de tes banques.
2. **📥 À classer** : pour chaque ligne, dis *pour qui elle compte* et sa *catégorie*, puis clique sur **Enregistrer**.
3. **👀 Regarder** : ouvre *Mon budget*, *Budget du foyer*, *Phi Rising* ou *Booth in Lyon*.

Chaque page a un bouton **ℹ️** en haut à droite qui explique à quoi elle sert.
""")

st.markdown("""
| Où | Page | À quoi ça sert |
|----|------|----------------|
| Chaque semaine | 🔄 **Importer** | Déposer les relevés des banques (et synchroniser Stripe) |
| Chaque semaine | 📥 **À classer** | Les lignes qui attendent un geste, et le contrôle des comptes |
| Mes budgets | 👤 **Mon budget** | Tes revenus, tes dépenses, ce qu'il te reste |
| Mes budgets | 🏠 **Budget du foyer** | Le compte commun : rentrées, dépenses communes |
| Mes budgets | 💼 **Phi Rising** · 📸 **Booth in Lyon** | Chiffre d'affaires, URSSAF, bénéfice, et un simulateur pour les mois à venir |
| Mes budgets | 🧮 **Tout ensemble** | Tous les budgets côte à côte |
| Plus | 🔎 **Transactions** | Retrouver, corriger ou déplacer n'importe quelle opération |
| Plus | 🧭 **Règles** | Les rangements automatiques |
| Plus | 🏦 **Patrimoine** · ⚙️ **Paramètres** · 📘 **Guide** | Soldes, catégories, mode d'emploi complet |
""")
