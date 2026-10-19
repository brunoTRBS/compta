"""Garde-fou des bulles d'aide ℹ️ : chaque bulle posée dans l'app a son texte, et inversement."""

import ast
from pathlib import Path

from app.help_texts import HELP

APP = Path(__file__).resolve().parents[2] / "app"
# fonction -> position de l'argument qui porte le sujet de la bulle
_TOPIC_ARG = {"page_title": 1, "section_title": 1, "tab_help": 0, "help_popover": 0}


def _used_topics() -> dict[str, list[str]]:
    """{sujet: [fichiers qui le posent]}, lu dans le code de l'app."""
    used: dict[str, list[str]] = {}
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            position = _TOPIC_ARG.get(node.func.id)
            if position is None or len(node.args) <= position:
                continue
            arg = node.args[position]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                used.setdefault(arg.value, []).append(path.name)
    return used


def test_every_bubble_has_its_text():
    missing = {topic: files for topic, files in _used_topics().items() if topic not in HELP}
    assert not missing, f"Bulles sans texte dans help_texts.py : {missing}"


def test_every_text_is_used_somewhere():
    unused = sorted(set(HELP) - set(_used_topics()))
    assert not unused, f"Textes d'aide jamais affichés : {unused}"


def test_texts_are_not_empty_and_stay_short():
    for topic, text in HELP.items():
        assert text.strip(), topic
        assert len(text) < 1500, f"{topic} est trop long pour une bulle ({len(text)} caractères)"


def test_every_page_has_a_bubble():
    """Chaque page de l'app (hors guide) pose une bulle de titre."""
    for path in sorted((APP / "pages").glob("*.py")):
        if path.name.startswith("0_"):
            continue
        assert "page_title(" in path.read_text(encoding="utf-8"), f"{path.name} n'a pas de bulle ℹ️"
