"""Retrying a project must not duplicate agents' other active missions."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from internships_project import state_store
from internships_project.city_routes import add_city_routes
from internships_project.marketdesk_city import CityStore, CityWorker


@pytest.fixture
def project(tmp_path, monkeypatch):
    path = tmp_path / "retry-conflicts.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    store = CityStore(path)
    workflow = store.create_custom_workflow("alice", "Review", "Review and prepare questions", [
        {"id": "market", "agent_id": "market_analyst", "description": "Review markets",
         "depends_on": []},
        {"id": "interview", "agent_id": "developer", "operation": "daily_questions",
         "description": "Prepare questions", "depends_on": ["market"]},
    ])
    root = store.claim_next()
    store.finish(root["id"], error="Temporary source failure")
    assert store.claim_next() is None
    assert store.task_detail("alice", workflow["task_ids"][1])["status"] == "cancelled"
    worker = CityWorker(store)
    starts = []
    monkeypatch.setattr(worker, "start", lambda: starts.append(True))
    app = FastAPI()
    add_city_routes(app, lambda request: "alice", store, worker)
    with TestClient(app) as client:
        yield store, workflow, root, client, starts


@pytest.mark.parametrize("agent_id", ["market_analyst", "developer"])
@pytest.mark.parametrize("status", ["queued", "running", "waiting_approval"])
def test_retry_rejects_conflicts_for_every_reactivated_step(project, agent_id, status):
    store, workflow, root, client, starts = project
    if status == "waiting_approval":
        store.save_settings("alice", {"auto_tasks": False})
    parameters = {"operation": "daily_questions"} if agent_id == "developer" else {}
    other = store.create_task("alice", agent_id, "Separate mission", parameters)
    if status == "running":
        assert store.claim_next()["id"] == other["id"]
    assert store.task_detail("alice", other["id"])["status"] == status
    before = store.snapshot("alice")

    response = client.post(f'/city/api/tasks/{root["id"]}/retry',
                           headers={"X-MarketDesk-City": "1"})

    assert response.status_code == 409
    assert "mission active" in response.json()["detail"]
    assert starts == []
    after = store.snapshot("alice")
    for key in ("tasks", "workflows", "events"):
        assert after[key] == before[key]

    # Once the competing mission ends, the whole original project can resume.
    if status == "running":
        store.finish(other["id"], result={"text": "Separate mission finished"})
    else:
        assert store.cancel_queued("alice", other["id"])
    response = client.post(f'/city/api/tasks/{root["id"]}/retry',
                           headers={"X-MarketDesk-City": "1"})
    assert response.status_code == 201
    assert starts == [True]
    assert store.claim_next()["id"] == root["id"]
    store.finish(root["id"], result={"text": "Market review"})
    assert store.claim_next()["id"] == workflow["task_ids"][1]
    store.finish(workflow["task_ids"][1], result={"text": "Interview questions"})
    assert store.snapshot("alice")["workflows"][0]["status"] == "completed"


def test_another_accounts_missions_do_not_block_project_retry(project):
    store, workflow, root, client, starts = project
    for agent_id in ("market_analyst", "developer"):
        parameters = {"operation": "daily_questions"} if agent_id == "developer" else {}
        store.create_task("bob", agent_id, "Separate mission", parameters)
    before = store.snapshot("bob")

    response = client.post(f'/city/api/tasks/{root["id"]}/retry',
                           headers={"X-MarketDesk-City": "1"})

    assert response.status_code == 201
    assert starts == [True]
    for task_id in workflow["task_ids"]:
        assert store.task_detail("alice", task_id)["status"] == "queued"
    after = store.snapshot("bob")
    for key in ("tasks", "workflows", "events"):
        assert after[key] == before[key]
