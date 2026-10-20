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

# Le menu est regroupé en trois parties. Chaque page appelle elle-même require_auth() et
# set_page_config() : ce fichier ne fait que décrire le menu.
pages = st.navigation(
    {
        "Chaque semaine": [
            st.Page("home.py", title="Accueil", icon="📊", default=True),
            st.Page("pages/7_Sync.py", title="Importer", icon="🔄"),
            st.Page("pages/1_A_Traiter.py", title="À classer", icon="📥"),
        ],
        "Mes budgets": [
            st.Page("pages/5_Budget_Perso.py", title="Mon budget", icon="👤"),
            st.Page("pages/6_Budget_Foyer.py", title="Budget du foyer", icon="🏠"),
            st.Page("pages/3_Phi_Rising.py", title="Phi Rising", icon="💼"),
            st.Page("pages/4_Booth_in_Lyon.py", title="Booth in Lyon", icon="📸"),
            st.Page("pages/2_Vue_Consolidee.py", title="Tout ensemble", icon="🧮"),
        ],
        "Plus": [
            st.Page("pages/10_Transactions.py", title="Transactions", icon="🔎"),
            st.Page("pages/9_Regles.py", title="Règles", icon="🧭"),
            st.Page("pages/6_Patrimoine.py", title="Patrimoine", icon="🏦"),
            st.Page("pages/8_Settings.py", title="Paramètres", icon="⚙️"),
            st.Page("pages/0_Guide.py", title="Guide", icon="📘"),
        ],
    }
)
pages.run()
