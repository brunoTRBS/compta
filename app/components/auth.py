"""Garde d'authentification Supabase Auth pour Streamlit, avec session persistée via cookie.

Le cookie (chiffré, navigateur) ne stocke que le refresh_token — l'access_token n'est
jamais mis en cache au-delà de sa propre expiration (~1h côté Supabase). À chaque visite,
si aucune session valide n'est en mémoire, un refresh silencieux est tenté à partir du
cookie avant d'afficher le formulaire de connexion.

Usage : appeler require_auth() en tête de chaque page.
"""

import time

import streamlit as st
from gotrue.errors import AuthApiError
from streamlit_cookies_manager import EncryptedCookieManager

from src.services.supabase import get_supabase

_SESSION_KEY = "sb_session"
_COOKIE_REFRESH_TOKEN = "refresh_token"


def require_auth() -> None:
    """Bloque le rendu de la page si l'utilisateur n'est pas authentifié.

    Restaure automatiquement la session depuis le cookie si possible (évite de se
    reconnecter à chaque visite), sinon affiche le formulaire de login et appelle
    st.stop(). Doit être appelé avant tout autre code dans chaque page.
    """
    if str(st.secrets.get("DEV_MODE", "false")).lower() == "true":
        if not st.session_state.get(_SESSION_KEY):
            st.session_state[_SESSION_KEY] = {
                "access_token": "dev-mode",
                "expires_at": time.time() + 86400,
                "user_email": "dev@local",
            }
        _show_logout_button()
        return

    cookies = EncryptedCookieManager(
        prefix="compta_auth/",
        password=str(st.secrets.get("COOKIE_PASSWORD", "changeme-in-secrets-toml")),
    )
    if not cookies.ready():
        st.stop()

    session = st.session_state.get(_SESSION_KEY)
    if session is not None and session.get("expires_at", 0) > time.time():
        _show_logout_button()
        return

    # Pas de session valide en mémoire : tenter un refresh silencieux via le cookie
    refresh_token = cookies.get(_COOKIE_REFRESH_TOKEN)
    if refresh_token:
        try:
            response = get_supabase().auth.refresh_session(refresh_token)
            _store_session(response, cookies)
            _show_logout_button()
            return
        except Exception:
            _forget_session(cookies)

    st.session_state.pop(_SESSION_KEY, None)
    _render_login_form(cookies)
    st.stop()


def _store_session(response, cookies: EncryptedCookieManager) -> None:
    """Enregistre la session en mémoire et son refresh_token (rotatif) dans le cookie."""
    st.session_state[_SESSION_KEY] = {
        "access_token": response.session.access_token,
        "expires_at": response.session.expires_at,
        "user_email": response.user.email,
    }
    cookies[_COOKIE_REFRESH_TOKEN] = response.session.refresh_token
    cookies.save()


def _forget_session(cookies: EncryptedCookieManager) -> None:
    st.session_state.pop(_SESSION_KEY, None)
    if _COOKIE_REFRESH_TOKEN in cookies:
        del cookies[_COOKIE_REFRESH_TOKEN]
        cookies.save()


def _render_login_form(cookies: EncryptedCookieManager) -> None:
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
                _store_session(response, cookies)
                st.rerun()
            except AuthApiError as e:
                st.error(f"Authentification refusée : {e.message}")
            except Exception as e:
                st.error(f"Erreur de connexion : {e}")


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
            cookies = EncryptedCookieManager(
                prefix="compta_auth/",
                password=str(st.secrets.get("COOKIE_PASSWORD", "changeme-in-secrets-toml")),
            )
            if cookies.ready():
                _forget_session(cookies)
            st.session_state.clear()
            st.rerun()
