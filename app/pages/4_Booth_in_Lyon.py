import streamlit as st

from app.components.auth import require_auth
from app.components.business_dashboard import render_dashboard
from src.config import BusinessId

st.set_page_config(page_title="Booth in Lyon", page_icon="📸", layout="wide")
require_auth()
st.title("Booth in Lyon — Location Photobooth")

render_dashboard(BusinessId.BOOTH_IN_LYON, "Booth in Lyon")
