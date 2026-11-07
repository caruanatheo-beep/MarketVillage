"""Interrupted missions become retryable even when still fresh at startup."""

from datetime import datetime, timedelta, timezone
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from internships_project import city_services, state_store
from internships_project.city_routes import add_city_routes
from internships_project.marketdesk_city import CityStore, CityWorker


@pytest.mark.parametrize("still_alive", [False, True])
def test_worker_rechecks_interrupted_project_and_allows_api_retry(tmp_path, monkeypatch, still_alive):
    path = tmp_path / "recovery.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    store = CityStore(path)
    project = store.create_custom_workflow("alice", "Review", "Review and prepare questions", [
        {"id": "market", "agent_id": "market_analyst", "description": "Review markets",
         "depends_on": []},
        {"id": "interview", "agent_id": "developer", "operation": "daily_questions",
         "description": "Prepare questions", "depends_on": ["market"]},
    ])
    root = store.claim_next()
    # A worker restarting immediately after an interruption cannot detect it yet.
    assert store.recover_stale() == 0
    worker = CityWorker(store)
    for name in ("enqueue_network_daily", "enqueue_specialist_schedules", "enqueue_daily_digest"):
        monkeypatch.setattr(store, name, lambda: None)
    clock = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    run_once = worker.run_once

    def tick():
        assert not run_once()  # The dependent step cannot run without its parent.
        if clock[0] == 0:
            old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec="seconds")
            with store.db() as db:
                db.execute("UPDATE city_tasks SET heartbeat_at=? WHERE id=?", (old, root["id"]))
            if still_alive:
                store.heartbeat(root["id"])
            clock[0] = 60.0
        else:
            worker._stop.set()
        return True

    monkeypatch.setattr(worker, "run_once", tick)
    worker._loop()
    # Restore the real clock before using the HTTP client and executing services.
    monkeypatch.undo()
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    detail = store.task_detail("alice", root["id"])
    if still_alive:
        assert detail["status"] == "running"
        assert store.task_detail("alice", project["task_ids"][1])["status"] == "queued"
        return

    assert detail["status"] == "failed"
    assert "interrompue" in detail["error"]
    assert store.snapshot("alice")["workflows"][0]["status"] == "failed"
    monkeypatch.setattr(worker, "start", lambda: None)
    monkeypatch.setattr(city_services, "run_agent", lambda *args: {"text": "Review complete"})
    app = FastAPI()
    add_city_routes(app, lambda request: "alice", store, worker)
    with TestClient(app) as client:
        response = client.post(f'/city/api/tasks/{root["id"]}/retry',
                               headers={"X-MarketDesk-City": "1"})
    assert response.status_code == 201
    assert worker.run_once()
    assert worker.run_once()
    assert store.snapshot("alice")["workflows"][0]["status"] == "completed"
