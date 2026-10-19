import streamlit as st

from app.components.auth import require_auth
from app.components.help import page_title
from app.components.business_dashboard import render_dashboard
from src.config import BusinessId

st.set_page_config(page_title="Phi Rising", page_icon="🎯", layout="wide")
require_auth()
page_title("Phi Rising — Coaching & Formation", "pro_page")

render_dashboard(BusinessId.PHI_RISING, "Phi Rising")
