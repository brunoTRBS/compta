"""Bulles d'aide ℹ️ : un petit bouton qui ouvre l'explication de la page, de l'onglet ou du bloc."""

import streamlit as st

from app.help_texts import HELP

_HELP_COLUMNS = [14, 1]


def help_popover(topic: str) -> None:
    """Le bouton ℹ️ seul ; son contenu vient de app/help_texts.py."""
    with st.popover("ℹ️", help="Comment ça marche"):
        st.markdown(HELP[topic])


def _row():
    """Une ligne « titre | ℹ️ » ; le centrage vertical n'existe que dans les Streamlit récents."""
    try:
        return st.columns(_HELP_COLUMNS, vertical_alignment="center")
    except TypeError:
        return st.columns(_HELP_COLUMNS)


def page_title(title: str, topic: str) -> None:
    """Titre de page avec sa bulle ℹ️ à droite."""
    col_title, col_help = _row()
    col_title.title(title)
    with col_help:
        help_popover(topic)


def section_title(title: str, topic: str, level: str = "subheader") -> None:
    """Titre de bloc avec sa bulle ℹ️. level : « subheader » ou « markdown » (texte en gras)."""
    col_title, col_help = _row()
    if level == "markdown":
        col_title.markdown(f"**{title}**")
    else:
        col_title.subheader(title)
    with col_help:
        help_popover(topic)


def tab_help(topic: str) -> None:
    """La bulle ℹ️ d'un onglet, alignée à droite en haut de son contenu."""
    _, col_help = st.columns(_HELP_COLUMNS)
    with col_help:
        help_popover(topic)
