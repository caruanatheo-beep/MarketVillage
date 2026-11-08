"""A temporary storage lock must not discard completed work or repeat it."""

import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from internships_project import city_services, state_store
from internships_project.city_routes import add_city_routes
from internships_project.marketdesk_city import CityStore, CityWorker


@pytest.mark.parametrize("failures", [1, 2])
@pytest.mark.parametrize("failure_stage", ["before", "transaction"])
def test_completed_result_survives_temporary_storage_contention(
        tmp_path, monkeypatch, caplog, failures, failure_stage):
    path = tmp_path / "results.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    store = CityStore(path)
    project = store.create_custom_workflow("alice", "Review", "Review and prepare questions", [
        {"id": "market", "agent_id": "market_analyst", "description": "Review markets",
         "depends_on": []},
        {"id": "questions", "agent_id": "developer", "operation": "daily_questions",
         "description": "Prepare questions", "depends_on": ["market"]},
    ])
    calls = []

    def run_agent(agent_id, username, parameters):
        calls.append(agent_id)
        return {"text": "Review complete", "xp_award": 10}

    monkeypatch.setattr(city_services, "run_agent", run_agent)
    finish = store.finish
    remember = store._remember_task_result
    attempts = []

    def storage_lock():
        exc = sqlite3.OperationalError("private storage detail")
        exc.sqlite_errorcode = sqlite3.SQLITE_BUSY
        raise exc

    def intermittent_remember(db, task, result):
        # Fail after task, XP and event writes: all must roll back before retry.
        if failure_stage == "transaction" and len(attempts) <= failures:
            storage_lock()
        return remember(db, task, result)

    def intermittent_finish(task_id, **kwargs):
        attempts.append(kwargs)
        if failure_stage == "before" and len(attempts) <= failures:
            storage_lock()
        return finish(task_id, **kwargs)

    monkeypatch.setattr(store, "_remember_task_result", intermittent_remember)
    monkeypatch.setattr(store, "finish", intermittent_finish)
    worker = CityWorker(store)
    assert worker.run_once()
    root = store.task_detail("alice", project["task_ids"][0])
    assert root["status"] == "completed"
    assert root["result"]["text"] == "Review complete"
    assert len(attempts) == failures + 1
    assert all(attempt == attempts[0] for attempt in attempts)
    with store.db() as db:
        xp = db.execute("SELECT xp FROM city_agents WHERE username=? AND agent_id=?",
                        ("alice", "market_analyst")).fetchone()[0]
    assert xp == 10
    assert calls == ["market_analyst"]
    assert worker.run_once()
    assert calls == ["market_analyst", "developer"]
    assert not worker.run_once()
    assert store.workflow_details("alice", project["id"])["status"] == "completed"
    events = store.snapshot("alice")["events"]
    assert sum(e["task_id"] == root["id"] and e["status"] == "completed" for e in events) == 1
    assert not any(e["status"] == "failed" for e in events)
    assert "private storage detail" not in caplog.text
    monkeypatch.setattr(worker, "start", lambda: None)
    app = FastAPI()
    add_city_routes(app, lambda request: "alice", store, worker)
    with TestClient(app) as client:
        detail = client.get(f'/city/api/tasks/{root["id"]}')
    assert detail.status_code == 200
    assert detail.json()["status"] == "completed"
    assert detail.json()["result"]["text"] == "Review complete"


@pytest.mark.parametrize("error_code,expected_attempts", [
    (sqlite3.SQLITE_BUSY, 3), (sqlite3.SQLITE_LOCKED, 3), (sqlite3.SQLITE_READONLY, 1),
])
def test_unavailable_result_storage_is_not_reported_as_agent_failure(
        tmp_path, monkeypatch, error_code, expected_attempts):
    path = tmp_path / "unavailable.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    store = CityStore(path)
    task = store.create_task("alice", "developer", "Prepare questions",
                             {"operation": "daily_questions"})
    calls = []
    monkeypatch.setattr(city_services, "run_agent",
                        lambda *args: calls.append(True) or {"text": "Questions ready"})
    attempts = []

    def unavailable_finish(task_id, **kwargs):
        attempts.append(kwargs)
        exc = sqlite3.OperationalError("private storage detail")
        exc.sqlite_errorcode = error_code
        raise exc

    monkeypatch.setattr(store, "finish", unavailable_finish)
    with pytest.raises(sqlite3.OperationalError):
        CityWorker(store).run_once()
    assert len(attempts) == expected_attempts
    assert all("error" not in attempt for attempt in attempts)
    assert calls == [True]
    assert store.task_detail("alice", task["id"])["status"] == "running"


def test_agent_failure_keeps_its_reason_when_storage_is_temporarily_locked(tmp_path, monkeypatch):
    path = tmp_path / "agent-failure.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    store = CityStore(path)
    task = store.create_task("alice", "developer", "Prepare questions",
                             {"operation": "daily_questions"})
    calls = []

    def failed_agent(*args):
        calls.append(True)
        raise ValueError("private agent detail")

    monkeypatch.setattr(city_services, "run_agent", failed_agent)
    finish = store.finish
    attempts = []

    def intermittent_finish(task_id, **kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            exc = sqlite3.OperationalError("private storage detail")
            exc.sqlite_errorcode = sqlite3.SQLITE_BUSY
            raise exc
        return finish(task_id, **kwargs)

    monkeypatch.setattr(store, "finish", intermittent_finish)
    assert CityWorker(store).run_once()
    detail = store.task_detail("alice", task["id"])
    assert detail["status"] == "failed"
    assert detail["error"] == "Erreur de mission (ValueError)."
    assert calls == [True]
    assert len(attempts) == 2
    assert attempts[0] == attempts[1]
