"""Memory retrieval across long histories, using only synthetic local records."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from internships_project import state_store
from internships_project.city_routes import add_city_routes
from internships_project.marketdesk_city import CityStore, CityWorker


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "synthetic.sqlite3")
    return CityStore(state_store.USER_DB_PATH)


def test_http_search_finds_saved_preference_beyond_recent_1200_entries(store):
    preference = store.record_memory("alice", "Localisation souhaitée", "Privilégier Montréal.")
    with store.db() as db:
        db.execute("UPDATE city_memory SET updated_at='2025-01-01' WHERE id=?", (preference["id"],))
        db.executemany(
            "INSERT INTO city_memory(id,username,agent_id,kind,subject_key,title,content,"
            "metadata_json,created_at,updated_at) VALUES(?,'alice','networker','contact',?,"
            "'Contact exemple','Paris','{}','2026-01-01','2026-01-01')",
            [(f"contact-{i}", f"contact-{i}") for i in range(1205)],
        )
    store.record_memory("bob", "Montréal", "Préférence distincte, très pertinente pour Montréal.")
    app = FastAPI()
    add_city_routes(app, lambda request: request.headers.get("x-test-user"), store, CityWorker(store))
    with TestClient(app) as client:
        response = client.get("/city/api/memory", params={"q": "montreal"},
                              headers={"x-test-user": "alice"})
        assert response.status_code == 200
        assert [entry["id"] for entry in response.json()["entries"]] == [preference["id"]]
        assert response.headers["cache-control"] == "private, no-store"
        # The initial view still shows recent entries, rather than old matches.
        recent = client.get("/city/api/memory", headers={"x-test-user": "alice"}).json()["entries"]
        assert len(recent) == 12
        assert all(entry["kind"] == "contact" for entry in recent)


def test_search_keeps_best_matches_then_recency_with_bounded_result_count(store):
    ids = []
    for index, title, content in [
        (0, "Note", "Préférence " + "Paris " * 80),
        (1, "Préférence", "Paris"),
        (2, "Préférence", "Paris"),
        (3, "Sans rapport", "Londres"),
    ]:
        entry = store.record_memory("alice", title, content, subject_key=str(index))
        ids.append(entry["id"])
        with store.db() as db:
            db.execute("UPDATE city_memory SET updated_at=? WHERE id=?", (f"2026-01-0{index+1}", entry["id"]))
    assert [entry["id"] for entry in store.search_memory("alice", "preference", limit=2)] == [ids[2], ids[1]]
    assert [entry["id"] for entry in store.search_memory("alice", limit=2)] == [ids[3], ids[2]]
    assert store.search_memory("alice", "inexistant") == []


def test_recent_view_applies_draft_eligibility_before_limit(store):
    note = store.record_memory("alice", "Préférence", "Paris")
    with store.db() as db:
        db.execute("UPDATE city_memory SET updated_at='2025-01-01' WHERE id=?", (note["id"],))
        store._upsert_memory(db, "alice", "outreach_agent", "outreach_draft", "draft",
                             "Brouillon", "Bonjour", {})
    assert [entry["id"] for entry in store.search_memory("alice", agent_id="networker", limit=1)] == [note["id"]]
    assert store.search_memory("alice", agent_id="outreach_agent", limit=1)[0]["kind"] == "outreach_draft"


def test_agent_memory_search_keeps_synonyms_and_cross_agent_preferences(store):
    preference = store.record_memory("alice", "Projet", "Stage obligataire")
    store.record_memory("alice", "Autre projet", "Comptabilité")
    entries = store.search_memory("alice", "internship bonds", agent_id="internship_scout", limit=6)
    assert [entry["id"] for entry in entries] == [preference["id"]]
    assert entries[0]["agent_id"] == "desk_manager"
    assert entries[0]["score"] > 0
