"""Interrupted missions become retryable even when still fresh at startup."""

from datetime import datetime, timedelta, timezone
import sqlite3
import threading
import time
from zoneinfo import ZoneInfoNotFoundError

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from internships_project import city_services, state_store
from internships_project.city_routes import add_city_routes
from internships_project.marketdesk_city import CityStore, CityWorker


@pytest.mark.parametrize("invalid_parameters", ["not-json", "[]", "null"])
def test_invalid_queued_payload_does_not_block_valid_mission(tmp_path, monkeypatch, invalid_parameters):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "private.db")
    store = CityStore(tmp_path / "city.db")
    invalid = store.create_task("alice", "market_analyst", "Invalid mission",
                                {"operation": "collect_markets"})
    valid = store.create_task("alice", "developer", "Prepare questions",
                              {"operation": "daily_questions"})
    with store.db() as db:
        db.execute("UPDATE city_tasks SET parameters_json=?,priority=10 WHERE id=?",
                   (invalid_parameters, invalid["id"]))

    claimed = store.claim_next()
    assert claimed["id"] == valid["id"]
    assert store.task_detail("alice", invalid["id"])["status"] == "cancelled"


def test_connection_interruption_retries_only_once(tmp_path, monkeypatch):
    from internships_project import city_coding
    from internships_project.marketdesk_city import CityError
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'private.db')
    store = CityStore(tmp_path/'city.db')
    task = store.create_task('alice', 'job_hunter', 'Corriger City', {'operation': 'develop'})
    def interrupted(*args, **kwargs):
        raise CityError('Connexion Codex interrompue ; travail conservé.')
    monkeypatch.setattr(city_coding, 'implement_change', interrupted)
    worker = CityWorker(store)
    assert worker.run_once()
    assert store.task_detail('alice', task['id'])['status'] == 'queued'
    with store.db() as db:
        assert db.execute('SELECT retry_count FROM city_tasks WHERE id=?', (task['id'],)).fetchone()[0] == 1
        db.execute('UPDATE city_tasks SET scheduled_at=NULL WHERE id=?', (task['id'],))
    assert worker.run_once()
    assert store.task_detail('alice', task['id'])['status'] == 'failed'


def test_interrupted_code_resumes_once_with_same_worktree(tmp_path, monkeypatch):
    from internships_project import city_specialists
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'private.db')
    monkeypatch.setattr(city_specialists, 'repo_root', lambda: tmp_path)
    store = CityStore(tmp_path/'city.db')
    task = store.create_task('alice', 'quality_engineer', 'Vérifier City', {'operation': 'develop'})
    assert store.claim_next()['id'] == task['id']
    directory = tmp_path/'.city-worktrees'/task['id']
    directory.mkdir(parents=True)
    (directory/'partial.py').write_text('value = 1\n')
    for expected in ('queued', 'failed'):
        with store.db() as db:
            db.execute("UPDATE city_tasks SET heartbeat_at='2020-01-01T00:00:00+00:00' WHERE id=?", (task['id'],))
        assert store.recover_stale() == 1
        assert store.task_detail('alice', task['id'])['status'] == expected
        assert (directory/'partial.py').read_text() == 'value = 1\n'
        if expected == 'queued':
            assert store.claim_next()['id'] == task['id']


@pytest.mark.parametrize("operation,completed_work", [
    ("develop", True), ("develop", False), ("daily_questions", False),
])
def test_interrupted_cancelled_project_never_resumes(
        tmp_path, monkeypatch, operation, completed_work):
    from internships_project import city_specialists

    path = tmp_path / "cancelled-recovery.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    store = CityStore(path)
    agent = "job_hunter" if operation == "develop" else "developer"
    project = store.create_custom_workflow("alice", "Review", "Review City", [
        {"id": "work", "agent_id": agent, "operation": operation,
         "description": "Review City", "depends_on": []},
        {"id": "next", "agent_id": "market_analyst",
         "description": "Review markets", "depends_on": ["work"]},
    ])
    task = store.claim_next()
    assert task["id"] == project["task_ids"][0]
    assert store.cancel_workflow("alice", project["id"])

    # Simulate a completed worktree without reading or writing runner artifacts.
    class Worktree:
        def __truediv__(self, name):
            return self

        def is_file(self):
            return completed_work

    monkeypatch.setattr(city_specialists, "repo_root", Worktree)
    assert store.recover_stale() == 0  # A still-live attempt may finish normally.
    with store.db() as db:
        db.execute("UPDATE city_tasks SET heartbeat_at='2020-01-01T00:00:00+00:00' WHERE id=?",
                   (task["id"],))
    assert store.recover_stale() == 1
    assert store.recover_stale() == 0
    detail = store.task_detail("alice", task["id"])
    assert detail["status"] == "cancelled"
    assert detail["finished_at"]
    assert detail["retry_count"] == 0
    assert store.workflow_details("alice", project["id"])["status"] == "cancelled"
    assert store.task_detail("alice", project["task_ids"][1])["status"] == "cancelled"
    event = next(item for item in store.snapshot("alice")["events"] if item["task_id"] == task["id"])
    assert event["status"] == "cancelled"
    assert "annul" in event["message"].lower()

    worker = CityWorker(store)
    monkeypatch.setattr(worker, "start", lambda: None)
    app = FastAPI()
    add_city_routes(app, lambda request: "alice", store, worker)
    with TestClient(app) as client:
        response = client.post(f'/city/api/tasks/{task["id"]}/retry',
                               headers={"X-MarketDesk-City": "1"})
    assert response.status_code == 409
    assert not worker.run_once()

    # Recovery releases the agent for the user's next mission.
    replacement = store.create_task("alice", agent, "Review City", {"operation": operation})
    assert store.claim_next()["id"] == replacement["id"]


@pytest.mark.parametrize("failure_type", [sqlite3.OperationalError, ModuleNotFoundError, ValueError])
def test_api_retry_starts_worker_after_temporary_startup_failure(
        tmp_path, monkeypatch, caplog, failure_type):
    path = tmp_path / "startup.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    store = CityStore(path)
    task = store.create_task("alice", "developer", "Prepare questions",
                             {"operation": "daily_questions"})
    assert store.claim_next()["id"] == task["id"]
    store.finish(task["id"], error="Temporary source failure")
    recover = store.recover_stale
    recovered = threading.Event()
    completed = threading.Event()
    attempts = []

    def intermittent_recovery():
        attempts.append(True)
        if len(attempts) == 1:
            raise failure_type("private startup detail")
        result = recover()
        recovered.set()
        return result

    monkeypatch.setattr(store, "recover_stale", intermittent_recovery)
    for name in ("enqueue_network_daily", "enqueue_specialist_schedules", "enqueue_daily_digest"):
        monkeypatch.setattr(store, name, lambda: None)
    monkeypatch.setattr(city_services, "run_agent", lambda *args: {"text": "Questions ready"})
    finish = store.finish

    def record_completion(task_id, **kwargs):
        finish(task_id, **kwargs)
        completed.set()

    monkeypatch.setattr(store, "finish", record_completion)
    worker = CityWorker(store)
    app = FastAPI()
    add_city_routes(app, lambda request: "alice", store, worker)
    try:
        with TestClient(app) as client:
            response = client.post(f'/city/api/tasks/{task["id"]}/retry',
                                   headers={"X-MarketDesk-City": "1"})
            assert response.status_code == 201
            retried_id = response.json()["task"]["id"]
            assert recovered.wait(5), "Startup recovery was never retried"
            assert completed.wait(5), "The retried mission never finished"
            detail = client.get(f'/city/api/tasks/{retried_id}').json()
        assert detail["status"] == "completed"
        assert detail["result"]["text"] == "Questions ready"
        assert failure_type.__name__ in caplog.text
        assert "private startup detail" not in caplog.text
    finally:
        worker.stop()


@pytest.mark.parametrize("failed_step", [
    "recover_stale", "enqueue_network_daily", "enqueue_specialist_schedules", "enqueue_daily_digest",
])
@pytest.mark.parametrize("failure_type", [
    sqlite3.OperationalError, ModuleNotFoundError, ZoneInfoNotFoundError, ValueError,
])
def test_scheduler_failure_does_not_block_ready_missions(
        tmp_path, monkeypatch, caplog, failed_step, failure_type):
    path = tmp_path / "scheduling.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    store = CityStore(path)
    project = store.create_custom_workflow("alice", "Review", "Review and prepare questions", [
        {"id": "market", "agent_id": "market_analyst", "description": "Review markets",
         "depends_on": []},
        {"id": "interview", "agent_id": "developer", "operation": "daily_questions",
         "description": "Prepare questions", "depends_on": ["market"]},
    ])
    worker = CityWorker(store)
    calls = {name: 0 for name in (
        "recover_stale", "enqueue_network_daily", "enqueue_specialist_schedules", "enqueue_daily_digest",
    )}

    def schedule(name):
        calls[name] += 1
        if name == failed_step and calls[name] <= 2:
            raise failure_type("private scheduling storage detail")

    for name in calls:
        monkeypatch.setattr(store, name, lambda name=name: schedule(name))
    monkeypatch.setattr(city_services, "run_agent", lambda *args: {"text": "Review complete"})
    clock = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    run_once = worker.run_once

    def tick():
        worked = run_once()
        clock[0] += 30.0
        return worked

    monkeypatch.setattr(worker, "run_once", tick)
    # Stop on idle; also bounds the old failure path that never reached run_once.
    monkeypatch.setattr(worker._stop, "wait", lambda seconds: worker._stop.set())
    worker._loop()
    assert store.workflow_details("alice", project["id"])["status"] == "completed"
    assert all(count == 2 for count in calls.values())
    assert failed_step in caplog.text
    assert failure_type.__name__ in caplog.text
    assert "private scheduling storage detail" not in caplog.text

    # The next scheduled pass retries the failed step and the worker stays usable.
    worker._stop.clear()
    worker._loop()
    assert all(count == 3 for count in calls.values())


def test_live_project_survives_temporary_heartbeat_storage_failure(tmp_path, monkeypatch, caplog):
    path = tmp_path / "heartbeat.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    store = CityStore(path)
    project = store.create_custom_workflow("alice", "Review", "Review and prepare questions", [
        {"id": "market", "agent_id": "market_analyst", "description": "Review markets",
         "depends_on": []},
        {"id": "interview", "agent_id": "developer", "operation": "daily_questions",
         "description": "Prepare questions", "depends_on": ["market"]},
    ])
    worker = CityWorker(store)
    ready = threading.Event()
    resumed = threading.Event()
    heartbeat = store.heartbeat
    attempts = []

    def intermittent_heartbeat(task_id):
        if not ready.wait(3):
            return
        attempts.append(task_id)
        if len(attempts) == 1:
            raise sqlite3.OperationalError("database is locked: private storage detail")
        heartbeat(task_id)
        resumed.set()

    monkeypatch.setattr(store, "heartbeat", intermittent_heartbeat)
    heartbeat_loop = worker._heartbeat

    class FastHeartbeat:
        def __init__(self, stopped):
            self.stopped = stopped

        def wait(self, seconds):
            return self.stopped.wait(0.001)

    monkeypatch.setattr(worker, "_heartbeat",
                        lambda task_id, stopped: heartbeat_loop(task_id, FastHeartbeat(stopped)))

    def run_agent(agent_id, username, parameters):
        if agent_id == "market_analyst":
            old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec="seconds")
            with store.db() as db:
                db.execute("UPDATE city_tasks SET heartbeat_at=? WHERE id=?", (old, project["task_ids"][0]))
            ready.set()
            assert resumed.wait(3), "The heartbeat stopped after a temporary storage failure"
            assert store.recover_stale() == 0
            assert store.task_detail("alice", project["task_ids"][0])["status"] == "running"
        return {"text": "Review complete"}

    monkeypatch.setattr(city_services, "run_agent", run_agent)
    assert worker.run_once()
    assert store.task_detail("alice", project["task_ids"][0])["status"] == "completed"
    assert worker.run_once()
    assert store.snapshot("alice")["workflows"][0]["status"] == "completed"
    assert len(attempts) >= 2
    assert "OperationalError" in caplog.text
    assert "private storage detail" not in caplog.text


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
