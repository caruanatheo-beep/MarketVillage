import importlib.util
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from internships_project import offers_schedule, offers_ui


def test_offers_only_has_no_ai_or_private_actions():
    app = offers_ui.build_offers_app()
    config = app.get_config_file()
    labels = str(config)
    for forbidden in ("Assistant IA", "Mon profil", "Administration", "Mes candidatures", "fileupload"):
        assert forbidden not in labels
    assert not any(component["type"] == "file" for component in config["components"])
    assert all(dependency.get("api_visibility") == "private" for dependency in config["dependencies"])


def test_filters_only_read_cache_and_pagination_is_bounded(monkeypatch):
    loader = Mock(return_value=([], [], datetime.now(ZoneInfo("UTC"))))
    monkeypatch.setattr(offers_ui, "load_opportunities", loader)
    rendered, page, label, _, _ = offers_ui.show_offers("Toutes", "", "Tous métiers", "Toutes dates", "all", "recent", 999)
    loader.assert_called_once_with(refresh=False)
    assert page == 1 and label == "Page 1 / 1"
    assert isinstance(rendered, str)


@pytest.mark.parametrize("stamp,previous,expected", [
    ("2026-11-11T06:59:00+00:00", "", None),
    ("2026-11-11T07:00:00+00:00", "", "2026-11-11T08"),
    ("2026-11-11T12:00:00+00:00", "2026-11-11T08", "2026-11-11T13"),
    ("2026-07-11T06:00:00+00:00", "", "2026-07-11T08"),
    ("2026-11-11T22:00:00+00:00", "2026-11-11T18", None),
])
def test_schedule_uses_paris_time(stamp, previous, expected):
    assert offers_schedule.due_slot(datetime.fromisoformat(stamp), previous) == expected


def test_schedule_survives_restart_without_duplicate_collection(tmp_path, monkeypatch):
    monkeypatch.setattr(offers_schedule.internships, "CACHE_PATH", tmp_path / "internships_cache.json")
    collect = Mock()
    monkeypatch.setattr(offers_schedule.internships, "refresh_opportunities", collect)
    now = datetime.fromisoformat("2026-11-11T13:00:00+01:00")
    assert offers_schedule.collect_if_due(now)
    assert not offers_schedule.collect_if_due(now)
    collect.assert_called_once_with(notify_email=False, fail_if_busy=True)


def test_busy_collection_does_not_mark_slot_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(offers_schedule.internships, "CACHE_PATH", tmp_path / "internships_cache.json")
    monkeypatch.setattr(offers_schedule.internships, "refresh_opportunities",
                        Mock(side_effect=offers_schedule.internships.CollectionBusyError("busy")))
    with pytest.raises(offers_schedule.internships.CollectionBusyError):
        offers_schedule.collect_if_due(datetime.fromisoformat("2026-11-11T13:00:00+01:00"))
    assert not (tmp_path / "offers_schedule.txt").exists()


def test_offers_server_requires_login_and_has_no_signup(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from internships_project import state_store
    monkeypatch.setenv("INTERNSHIPS_OFFERS_ONLY", "1")
    monkeypatch.setenv("INTERNSHIPS_PUBLIC_HTTPS", "1")
    monkeypatch.setenv("INTERNSHIPS_USERS_JSON", '{"testowner":"test-password-only-12345"}')
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    import app_internships
    monkeypatch.setattr(app_internships, "OFFERS_ONLY", True)
    app = offers_ui.build_offers_app()
    server = app_internships.create_shared_server(app, [("testowner", "test-password-only-12345")])
    with TestClient(server, base_url="https://testserver") as client:
        assert client.get("/config").status_code == 401
        assert client.get("/private-download").status_code == 404
        login = client.get("/")
        assert "Créer un compte" not in login.text
        response = client.post("/login", data={"username": "testowner", "password": "test-password-only-12345"})
        assert response.status_code == 200
        assert "access-token-unsecure-" not in response.headers.get("set-cookie", "")
        assert "secure" in response.headers.get("set-cookie", "").lower()
        config = client.get("/config")
        assert config.status_code == 200
        assert "Assistant IA" not in str(config.json()["components"])
        assert client.get("/inscription").status_code == 404
