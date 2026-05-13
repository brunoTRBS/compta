import streamlit as st
import polars as pl
from supabase import create_client

# Récupération des secrets (configurés sur Streamlit Cloud)
URL = st.secrets["SUPABASE_URL"]
KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def get_supabase():
    return create_client(URL, KEY)

st.title("Compta Pro & Perso")
supabase = get_supabase()

# Test rapide de lecture avec Polars
st.write("Connexion établie avec Supabase !")