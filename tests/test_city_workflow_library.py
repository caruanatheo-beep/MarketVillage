"""Saved workflows remain accessible throughout the supported library capacity."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from internships_project import state_store
from internships_project.city_routes import add_city_routes
from internships_project.marketdesk_city import CityStore, CityWorker


STEPS = [{"id": "questions", "agent_id": "developer", "operation": "daily_questions",
          "description": "Prepare interview questions", "depends_on": []}]
HEADERS = {"x-test-user": "alice", "X-MarketDesk-City": "1"}
URL = "/city/api/workflows/definitions"


@pytest.fixture
def library(tmp_path, monkeypatch):
    path = tmp_path / "workflow-library.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    store = CityStore(path)
    for index in range(50):
        store.save_workflow_definition("alice", f"Interview {index:02}", STEPS,
                                       f"saved-{index:02}")
    # Fixed dates make the oldest workflows unambiguous even on fast machines.
    with store.db() as db:
        for index in range(50):
            db.execute("UPDATE city_workflow_definitions SET updated_at=? WHERE id=?",
                       (f"2026-01-01T00:00:{index:02}+00:00", f"saved-{index:02}"))
    store = CityStore(path)
    worker = CityWorker(store)
    starts = []
    monkeypatch.setattr(worker, "start", lambda: starts.append(True))
    app = FastAPI()
    add_city_routes(app, lambda request: request.headers.get("x-test-user"), store, worker)
    with TestClient(app) as client:
        yield client, store, starts


def test_all_saved_workflows_reach_the_interface_after_reopening(library):
    client, _, _ = library
    response = client.get(URL, headers=HEADERS)
    assert response.status_code == 200
    definitions = response.json()["definitions"]
    assert [item["id"] for item in definitions] == [f"saved-{i:02}" for i in reversed(range(50))]
    assert definitions[-1]["name"] == "Interview 00"
    assert definitions[-1]["steps"] == STEPS
    assert client.get(URL, headers={"x-test-user": "bob"}).json() == {"definitions": []}


def test_oldest_workflow_can_be_edited_and_relaunched_at_capacity(library):
    client, store, starts = library
    definitions = client.get(URL, headers=HEADERS).json()["definitions"]
    oldest = next(item for item in definitions if item["id"] == "saved-00")
    steps = [{**oldest["steps"][0], "description": "Prepare updated questions"}]
    response = client.post(URL, headers=HEADERS,
                           json={"id": oldest["id"], "name": "Updated interview", "steps": steps})
    assert response.status_code == 201
    assert len(store.workflow_definitions("alice")) == 50
    assert next(item for item in store.workflow_definitions("alice")
                if item["id"] == oldest["id"])["steps"] == steps

    response = client.post(f"{URL}/{oldest['id']}/run", headers=HEADERS, json={})
    assert response.status_code == 201
    workflow = response.json()["workflow"]
    assert workflow["request"] == "Updated interview"
    task = store.task_detail("alice", workflow["task_ids"][0])
    assert task["description"] == "Prepare updated questions"
    assert task["agent_id"] == "developer"
    assert starts == [True]


def test_library_still_rejects_new_workflows_above_capacity(library):
    client, store, _ = library
    response = client.post(URL, headers=HEADERS, json={"name": "Extra workflow", "steps": STEPS})
    assert response.status_code == 400
    assert "50" in response.json()["detail"]
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM city_workflow_definitions WHERE username='alice'").fetchone()[0] == 50
