import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace

from internships_project import state_store
from internships_project.accounts import (account_exists, admin_username, authenticate,
                                          create_account, delete_registered_account, list_accounts)


def test_registered_accounts_are_hashed_unique_and_keep_private_state(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    configured = [("theo", "admin-password-123")]
    create_account("camille", "a-long-password-123", configured)
    assert authenticate("camille", "a-long-password-123", configured)
    assert not authenticate("camille", "wrong-password", configured)
    assert not authenticate("Camille", "a-long-password-123", configured)
    assert authenticate("theo", "admin-password-123", configured)
    with state_store._connect() as connection:
        saved = connection.execute("SELECT password_hash FROM registered_accounts").fetchone()[0]
    assert "a-long-password-123" not in saved
    with pytest.raises(ValueError, match="déjà utilisé"):
        create_account("theo", "a-long-password-123", configured)
    with pytest.raises(ValueError, match="déjà utilisé"):
        create_account("camille", "a-long-password-123", configured)
    state_store.save_user_data("camille", "profiles", {"one": {"name": "Camille"}})
    assert state_store.load_user_data("theo", "profiles") == {}
    assert [name for name, _, _ in list_accounts(configured)] == ["theo", "camille"]


def test_admin_identity_must_be_an_initial_account(monkeypatch):
    monkeypatch.setenv("INTERNSHIPS_ADMIN_USER", "theo")
    assert admin_username([("theo", "secret"), ("alice", "secret")]) == "theo"
    monkeypatch.setenv("INTERNSHIPS_ADMIN_USER", "outsider")
    with pytest.raises(ValueError):
        admin_username([("theo", "secret")])


def test_account_list_is_generated_only_for_admin(tmp_path, monkeypatch):
    from internships_project.internships_ui import build_internships_app

    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    monkeypatch.setenv("INTERNSHIPS_USERS_JSON", '{"theo":"admin-password-123"}')
    monkeypatch.setenv("INTERNSHIPS_ADMIN_USER", "theo")
    create_account("camille", "a-long-password-123", [("theo", "admin-password-123")])
    demo = build_internships_app()
    callback = next(item.fn for item in demo.fns.values()
                    if item.fn is not None and item.fn.__name__ == "account_overview")
    hidden, content, usage, choices = callback(SimpleNamespace(username="camille"))
    assert hidden["visible"] is False
    assert content == ""
    assert usage == ""
    assert choices.choices == []
    visible, content, usage, choices = callback(SimpleNamespace(username="theo"))
    assert visible["visible"] is True
    assert "camille" in content
    assert "password" not in content
    assert "Coût" not in content
    assert "Estimation" in usage
    assert "camille" in str(choices.choices)


def test_admin_can_delete_registered_member_and_private_state(tmp_path, monkeypatch):
    from internships_project.internships_ui import build_internships_app

    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    monkeypatch.setenv("INTERNSHIPS_USERS_JSON", '{"theo":"admin-password-123"}')
    monkeypatch.setenv("INTERNSHIPS_ADMIN_USER", "theo")
    configured = [("theo", "admin-password-123")]
    create_account("camille", "a-long-password-123", configured)
    state_store.save_user_data("camille", "profiles", {"one": {"name": "Camille"}})
    demo = build_internships_app()
    remove = next(item.fn for item in demo.fns.values()
                  if item.fn is not None and item.fn.__name__ == "remove_account")
    with pytest.raises(Exception, match="administrateur"):
        remove("camille", True, SimpleNamespace(username="camille"))
    with pytest.raises(Exception, match="Confirme"):
        remove("camille", False, SimpleNamespace(username="theo"))
    with pytest.raises(Exception, match="compte initial"):
        delete_registered_account("theo", configured)
    message, checked = remove("camille", True, SimpleNamespace(username="theo"))
    assert "camille" in message
    assert checked is False
    assert not account_exists("camille", configured)
    assert not authenticate("camille", "a-long-password-123", configured)
    assert state_store.load_user_data("camille", "profiles") == {}
    assert account_exists("theo", configured)


def test_signup_uses_native_gradio_auth_and_protects_routes(tmp_path, monkeypatch):
    import gradio as gr
    from app_internships import create_shared_server

    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    monkeypatch.delenv("INTERNSHIPS_SIGNUP_CODE", raising=False)
    demo = gr.Interface(lambda text: text, "text", "text")
    server = create_shared_server(demo, [("theo", "admin-password-123")])
    with TestClient(server) as client:
        page = client.get("/inscription")
        assert page.status_code == 200
        assert "Créer ton compte" in page.text
        assert client.get("/config").status_code == 401
        assert client.post("/inscription", json={"username": "camille", "password": "a-long-password-123",
                                                   "confirm": "a-long-password-123"}).status_code == 403
        token = client.cookies.get("signup_csrf")
        response = client.post("/inscription", headers={"X-Signup-Token": token},
                               json={"username": "camille", "password": "a-long-password-123",
                                     "confirm": "a-long-password-123"})
        assert response.status_code == 201
        assert client.post("/login", data={"username": "camille", "password": "wrong"}).status_code == 400
        assert client.post("/login", data={"username": "camille",
                                           "password": "a-long-password-123"}).status_code == 200
        assert client.get("/config").status_code == 200
        delete_registered_account("camille", [("theo", "admin-password-123")])
        assert client.get("/config").status_code == 401


def test_signup_invitation_code_when_configured(tmp_path, monkeypatch):
    import gradio as gr
    from app_internships import create_shared_server

    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    monkeypatch.setenv("INTERNSHIPS_SIGNUP_CODE", "friends-only-code")
    server = create_shared_server(gr.Interface(lambda x: x, "text", "text"),
                                  [("theo", "admin-password-123")])
    with TestClient(server) as client:
        assert "Code d’invitation" in client.get("/inscription").text
        token = client.cookies.get("signup_csrf")
        payload = {"username": "camille", "password": "a-long-password-123",
                   "confirm": "a-long-password-123", "code": "wrong"}
        assert client.post("/inscription", headers={"X-Signup-Token": token}, json=payload).status_code == 403
        assert not authenticate("camille", "a-long-password-123", [("theo", "admin-password-123")])
