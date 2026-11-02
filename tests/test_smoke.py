import os
import subprocess
import sys
from pathlib import Path

import gradio as gr

from app import available_local_port
from internships_project.internships_ui import CSS as INTERNSHIPS_CSS, build_internships_app
from src.ui import build_app

ROOT = Path(__file__).resolve().parents[1]


def test_gradio_interface_builds():
    app = build_app()
    assert isinstance(app, gr.Blocks)
    config = app.get_config_file()
    labels = str(config)
    assert "Overview" in labels
    assert "News" in labels
    assert "Research Agent" in labels
    assert "About" in labels
    assert "Documents / RAG" not in labels
    assert "Refresh" in labels
    assert "AI Desk Report" in labels
    assert "Internships" not in labels
    assert "Demo (historical)" not in labels


def test_internships_interface_is_independent():
    app = build_internships_app()
    assert isinstance(app, gr.Blocks)
    config = app.get_config_file()
    labels = str(config)
    assert "Internships" in labels
    assert "Aujourd’hui" in labels
    assert "7 derniers jours" in labels
    assert "Mes candidatures" in labels
    assert "Nouvelles pour moi" not in labels
    assert "Assistant IA" in labels
    assert "Offres" in labels
    assert "Mon profil" in labels
    assert "MSc Financial Markets &amp; Investments" in labels
    assert "Markets Career Desk" not in labels
    assert "skema-emblem" in labels
    assert "data:image/png;base64," in labels
    assert "Théo Caruana" in labels
    assert "Développé avec Codex" in labels
    assert "Créer mon profil" in labels
    assert "Marquer « Postulé »" in labels
    assert "offer-return-notification" in labels
    assert "Analyser les offres" in labels
    assert "Analyser mon CV ou mon résumé" in labels
    assert "Ton CV" in labels
    assert "Ton parcours" in labels
    assert "Ta recherche" in labels
    assert "Tes expériences" in labels
    assert "Tes compétences" in labels
    assert "Informations à compléter" in labels
    assert "Profil à utiliser" not in labels
    assert "Nouveau profil" not in labels
    assert "Masquer les offres écartées" not in labels
    components = config["components"]
    contract = next(component for component in components
                    if component.get("props", {}).get("elem_id") == "internship-contract-types")
    assert contract["type"] == "dropdown"
    assert contract["props"]["value"] == "Toutes"
    start = next(component for component in components
                 if component.get("props", {}).get("elem_id") == "internship-start")
    assert ("Mars 2027", "2027-03") in [tuple(choice) for choice in start["props"]["choices"]]
    assert [value for _, value in contract["props"]["choices"]] == [
        "Toutes", "Stages Paris", "Stages International", "VIE", "Graduate",
    ]
    sort = next(component for component in components
                if component.get("props", {}).get("elem_id") == "internship-sort")
    assert sort["props"]["value"] == "pertinence"
    assert "Plus récentes d’abord" in labels
    assert any(component.get("props", {}).get("elem_id") == "primary-navigation"
               for component in components)
    assert any(component.get("props", {}).get("elem_id") == "jobs-sections"
               for component in components)
    profile_name = next(component for component in components
                        if component.get("props", {}).get("elem_id") == "profile-name")
    assert profile_name["props"]["value"] == ""
    assert "Prochaine action" in labels
    assert "Notes et dates (facultatif)" in labels
    assert "Enregistrer" in labels
    assert "Offre publiée" not in labels
    assert "--desk-bg: #f7f7fb" in INTERNSHIPS_CSS
    assert "Research Agent" not in labels


def test_python_entry_point():
    env = os.environ.copy()
    env["APP_TEST_MODE"] = "1"
    result = subprocess.run(
        [sys.executable, "app.py"], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=40, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "entry point: OK" in result.stdout


def test_internships_entry_point():
    env = os.environ.copy()
    env["APP_TEST_MODE"] = "1"
    result = subprocess.run(
        [sys.executable, "app_internships.py"], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=40, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Internships entry point: OK" in result.stdout


def test_local_port_falls_forward_when_preferred_is_busy():
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        preferred = occupied.getsockname()[1]
        assert available_local_port(preferred, attempts=2) == preferred + 1
