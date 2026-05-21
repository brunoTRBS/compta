"""Garde d'authentification Supabase Auth pour Streamlit.

Usage : appeler require_auth() en tête de chaque page.
"""

import time

import streamlit as st

from src.services.supabase import get_supabase

_SESSION_KEY = "sb_session"


def require_auth() -> None:
    """Bloque le rendu de la page si l'utilisateur n'est pas authentifié.

    Affiche le formulaire de login et appelle st.stop() si non connecté.
    Doit être appelé avant tout autre code dans chaque page.
    """
    session = st.session_state.get(_SESSION_KEY)

    if session is not None:
        # Vérifier l'expiration du token
        if session.get("expires_at", 0) > time.time():
            _show_logout_button()
            return
        # Token expiré : nettoyer la session
        st.session_state.pop(_SESSION_KEY, None)

    _render_login_form()
    st.stop()


def _render_login_form() -> None:
    col = st.columns([1, 1, 1])[1]
    with col:
        st.markdown("### Connexion")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Mot de passe", type="password")
            submitted = st.form_submit_button("Se connecter", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Email et mot de passe requis.")
                return
            try:
                response = get_supabase().auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                st.session_state[_SESSION_KEY] = {
                    "access_token": response.session.access_token,
                    "expires_at": response.session.expires_at,
                    "user_email": response.user.email,
                }
                st.rerun()
            except Exception:
                st.error("Email ou mot de passe incorrect.")


def _show_logout_button() -> None:
    session = st.session_state.get(_SESSION_KEY, {})
    email = session.get("user_email", "")
    with st.sidebar:
        st.caption(f"Connecté : {email}")
        if st.button("Déconnexion", use_container_width=True):
            try:
                get_supabase().auth.sign_out()
            except Exception:
                pass
            st.session_state.clear()
            st.rerun()
