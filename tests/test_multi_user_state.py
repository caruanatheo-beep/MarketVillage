import pytest

from internships_project import state_store
from internships_project.migrate_local_state import migrate


def test_accounts_keep_profiles_tracking_and_drafts_separate(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    alice = {"alice-profile": {"name": "Alice", "target_roles": ["Sales"]}}
    bob = {"bob-profile": {"name": "Bob", "target_roles": ["Trading"]}}
    state_store.save_user_data("alice", "profiles", alice)
    state_store.save_user_data("bob", "profiles", bob)
    state_store.save_user_data("alice", "drafts", {"offer-a": "Alice's letter"})
    state_store.save_user_data("bob", "drafts", {"offer-b": "Bob's letter"})
    state_store.save_user_data("alice", "ai_cache", {"briefs": {"id": "alice-only"}})
    state_store.save_user_data("bob", "ai_cache", {"briefs": {"id": "bob-only"}})
    offer = "https://example.com/jobs/sales"
    state_store.save_user_data("alice", "tracking", {
        offer: {"title": "Sales Intern", "company": "Bank", "status": "Postulé"}})
    assert state_store.load_user_data("alice", "profiles") == alice
    assert state_store.load_user_data("bob", "profiles") == bob
    assert state_store.load_user_data("alice", "drafts") == {"offer-a": "Alice's letter"}
    assert state_store.load_user_data("bob", "drafts") == {"offer-b": "Bob's letter"}
    assert state_store.load_user_data("alice", "ai_cache")["briefs"]["id"] == "alice-only"
    assert state_store.load_user_data("bob", "ai_cache")["briefs"]["id"] == "bob-only"
    assert offer in state_store.load_user_data("alice", "tracking")
    assert state_store.load_user_data("bob", "tracking") == {}


def test_account_store_rejects_missing_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    with pytest.raises(ValueError):
        state_store.load_user_data("", "profiles")
    with pytest.raises(ValueError):
        state_store.save_user_data("", "tracking", {})


def test_shared_gradio_build_has_no_browser_personal_state(monkeypatch):
    from internships_project.internships_ui import build_internships_app
    monkeypatch.setenv("INTERNSHIPS_USERS_JSON", '{"alice":"abcdefghijklmnop"}')
    app = build_internships_app()
    components = app.get_config_file()["components"]
    assert any(item["type"] == "state" for item in components)
    assert "Importer mes données de ce navigateur" in str(app.get_config_file())


def test_migrating_local_tracker_does_not_overwrite_account(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    monkeypatch.setattr(state_store, "STATE_PATH", tmp_path / "user_state.json")
    monkeypatch.setattr(state_store, "BACKUP_PATH", tmp_path / "user_state.backup.json")
    url = "https://example.com/jobs/trading"
    state_store._write_unlocked({url: {"title": "Trader", "company": "Bank",
                                       "status": "Postulé"}}, {})
    state_store.save_user_data("theo", "tracking", {
        url: {"title": "Trader", "company": "Bank", "status": "Interview"}})
    assert migrate("theo") == (1, 0)
    assert state_store.load_user_data("theo", "tracking")[url]["status"] == "Interview"
    assert state_store.load_user_data("friend", "tracking") == {}


def test_shared_launch_requires_strong_per_user_credentials(monkeypatch):
    from app_internships import configured_users
    monkeypatch.setenv("INTERNSHIPS_USERS_JSON", '{"alice":"short"}')
    with pytest.raises(ValueError, match="12 caractères"):
        configured_users()
    monkeypatch.setenv("INTERNSHIPS_USERS_JSON", '{"alice":"abcdefghijklmnop","bob":"qrstuvwxyz123456"}')
    assert [name for name, _ in configured_users()] == ["alice", "bob"]
