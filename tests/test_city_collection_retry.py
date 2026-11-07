"""Collection contention must delay missions without breaking their projects."""

from datetime import datetime, timedelta, timezone
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from internships_project import internships, state_store
from internships_project.city_routes import add_city_routes
from internships_project.marketdesk_city import CityStore, CityWorker


@pytest.mark.parametrize("agent_id", ["desk_manager", "networker", "internship_scout"])
@pytest.mark.parametrize("busy_source", ["scheduled", "collector_lock"])
def test_busy_collection_resumes_same_mission_and_project(
        tmp_path, monkeypatch, agent_id, busy_source):
    path = tmp_path / "collection.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    store = CityStore(path)
    project = store.create_custom_workflow("alice", "Stages", "Collecter puis préparer", [
        {"id": "collect", "agent_id": agent_id, "operation": "refresh_internships",
         "description": "Actualiser les stages", "depends_on": []},
        {"id": "questions", "agent_id": "developer", "operation": "daily_questions",
         "description": "Préparer les questions", "depends_on": ["collect"]},
    ]) if agent_id == "internship_scout" else None
    if project:
        task_id, dependent_id = project["task_ids"]
    else:
        task_id = store.create_task("alice", agent_id, "Actualiser les stages",
                                    {"operation": "refresh_internships"})["id"]
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(internships, "load_opportunities", lambda **kwargs: ([], [], now))
    monkeypatch.setattr(internships, "opportunities_loading", lambda: busy_source == "scheduled")
    # Use the real collector's contention path, with an isolated lock and no I/O.
    guard = threading.Lock()
    guard.acquire()
    monkeypatch.setattr(internships, "_refresh_guard", guard)
    worker = CityWorker(store)
    assert worker.run_once()
    guard.release()

    detail = store.task_detail("alice", task_id)
    assert detail["status"] == "queued"
    assert detail["error"] is None
    assert detail["finished_at"] is None
    with store.db() as db:
        row = db.execute("SELECT * FROM city_tasks WHERE id=?", (task_id,)).fetchone()
        remaining = (datetime.fromisoformat(row["scheduled_at"]) - now).total_seconds()
        assert 290 < remaining < 330
        assert row["retry_count"] == 0
        assert row["started_at"] is None
        assert row["heartbeat_at"] is None
    if project:
        assert store.workflow_details("alice", project["id"])["status"] == "queued"
        assert store.task_detail("alice", dependent_id)["status"] == "queued"
    assert not worker.run_once()  # No busy loop and no premature dependent step.

    monkeypatch.setattr(worker, "start", lambda: None)
    app = FastAPI()
    add_city_routes(app, lambda request: "alice", store, worker)
    with TestClient(app) as client:
        response = client.get(f"/city/api/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["scheduled_at"] == row["scheduled_at"]
    assert any("Nouvelle tentative dans 5 minutes" in event["message"]
               for event in store.snapshot("alice")["events"])

    # The collector becomes available; the same task must run without manual retry.
    calls = []
    monkeypatch.setattr(internships, "opportunities_loading", lambda: False)

    def refresh(**kwargs):
        calls.append(kwargs)
        return [], [], now + timedelta(seconds=1)

    monkeypatch.setattr(internships, "refresh_opportunities", refresh)
    with store.db() as db:
        db.execute("UPDATE city_tasks SET scheduled_at=NULL WHERE id=?", (task_id,))
    assert worker.run_once()
    assert store.task_detail("alice", task_id)["status"] == "completed"
    if project:
        from internships_project import city_services
        monkeypatch.setattr(city_services, "run_agent", lambda *args: {"text": "Questions prêtes"})
        assert worker.run_once()
        assert store.workflow_details("alice", project["id"])["status"] == "completed"
    assert calls == [{"force": True, "notify_email": False, "fail_if_busy": True}]
    expected = {task_id, dependent_id} if project else {task_id}
    assert {task["id"] for task in store.snapshot("alice")["tasks"]} == expected


def test_collector_runtime_failure_is_not_misreported_as_contention(tmp_path, monkeypatch):
    path = tmp_path / "failure.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    store = CityStore(path)
    task = store.create_task("alice", "networker", "Actualiser les stages",
                             {"operation": "refresh_internships"})
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(internships, "opportunities_loading", lambda: False)
    monkeypatch.setattr(internships, "load_opportunities", lambda **kwargs: ([], [], now))

    def broken_collector(**kwargs):
        raise RuntimeError("private collector detail")

    monkeypatch.setattr(internships, "refresh_opportunities", broken_collector)
    assert CityWorker(store).run_once()
    detail = store.task_detail("alice", task["id"])
    assert detail["status"] == "failed"
    assert detail["error"] == "Erreur de mission (RuntimeError)."
    assert "private collector detail" not in str(detail)
