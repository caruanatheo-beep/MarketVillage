"""Persistent City collaboration without external sends or model requests."""

from datetime import datetime, timezone
import threading
import time

import pytest

from internships_project.marketdesk_city import CityError, CityStore, CityWorker


def _workspace(tmp_path, monkeypatch):
    from internships_project import state_store
    from internships_project.state_store import save_user_data

    path = tmp_path / "accounts.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    save_user_data("theo", "profiles", {"profile": {"name": "Candidate Example", "source_text": "Markets sales internship experience."}})
    save_user_data("theo", "mail_contacts", {"contact": {"name": "Contact Example", "role": "Rates Sales",
                    "company": "Bank A", "location": "Paris", "verification_status": "À vérifier"}})
    return CityStore(path)


def test_complete_careers_workflow_reuses_real_adapters_and_never_sends(tmp_path, monkeypatch):
    from internships_project import internships, mail_outreach
    from internships_project.state_store import load_user_data

    store = _workspace(tmp_path, monkeypatch)
    def unexpected_jobs(*args, **kwargs):
        raise AssertionError("Networking must use saved contacts without searching internships")
    monkeypatch.setattr(internships, "load_opportunities", unexpected_jobs)
    monkeypatch.setattr(mail_outreach, "draft_mail", lambda *args, **kwargs: (
        "Rates Sales internship", "Hello, could we discuss your team?", "Following up on my note."))
    sent = []
    monkeypatch.setattr(mail_outreach, "_provider_send", lambda *args, **kwargs: sent.append(args))

    workflow = store.create_workflow("theo", "careers_outreach", "Find Rates Sales roles and prepare outreach",
                                     "Rates Sales", priority=2)
    assert len(workflow["task_ids"]) == 2
    assert store.snapshot("friend")["workflows"] == []
    worker = CityWorker(store)
    assert worker.run_once()
    assert worker.run_once()
    assert not worker.run_once()

    snapshot = CityStore(store.path).snapshot("theo")
    completed = snapshot["workflows"][0]
    assert completed["status"] == "completed"
    assert [step["status"] for step in completed["steps"]] == ["completed"] * 2
    assert completed["result"][0]["result"]["contacts"][0]["id"] == "contact"
    assert completed["result"][1]["result"]["body"] == "Hello, could we discuss your team?"
    assert load_user_data("theo", "mail_contacts")["contact"]["body"] == "Hello, could we discuss your team?"
    assert sent == []
    assert store.shared_results("friend") == []
    assert store.shared_results("theo")[0]["agent_id"] == "networker"


def test_parallel_roots_dependencies_retry_and_cancellation(tmp_path, monkeypatch):
    store = _workspace(tmp_path, monkeypatch)
    first = store.create_custom_workflow("theo", "Review", "Review markets contacts", [
        {"id":"market", "agent_id":"market_analyst", "description":"Review markets", "depends_on":[]},
        {"id":"contacts", "agent_id":"networker", "description":"Review contacts", "depends_on":[]},
        {"id":"draft", "agent_id":"outreach_agent", "description":"Prepare draft", "depends_on":["market","contacts"]},
    ])
    root_a = store.claim_next()
    root_b = store.claim_next()
    assert {root_a["agent_id"], root_b["agent_id"]} == {"market_analyst", "networker"}
    assert store.claim_next() is None  # Iris waits for both results.
    store.finish(root_a["id"], result={"text": "Dated market review"})
    assert store.claim_next() is None
    store.finish(root_b["id"], error="Temporary source failure")
    assert store.claim_next() is None  # Cancels the dependent stage, never runs it.
    assert store.snapshot("theo")["workflows"][0]["status"] == "failed"
    retried = store.retry_task("theo", root_b["id"])
    assert retried["id"] == root_b["id"]
    assert store.claim_next()["id"] == root_b["id"]
    store.finish(root_b["id"], result={"contacts": [{"id": "contact"}]})
    assert store.claim_next()["agent_id"] == "outreach_agent"
    assert store.cancel_workflow("friend", first["id"]) is False
    assert store.cancel_workflow("theo", first["id"]) is True
    assert store.snapshot("theo")["workflows"][0]["status"] == "cancelled"


def test_manager_tool_is_registered_and_workflow_requires_profile(tmp_path, monkeypatch):
    import asyncio
    from pydantic_ai.models.test import TestModel
    from internships_project.city_agents import ChatDeps, build_agent
    from internships_project import state_store

    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "empty.sqlite3")
    store = CityStore(state_store.USER_DB_PATH)
    with pytest.raises(CityError, match="profil"):
        store.create_workflow("theo", "careers_outreach", "Prepare outreach")
    manager = build_agent("desk_manager", TestModel())
    assert manager.name == "city_desk_manager"
    deps = ChatDeps("theo", store)
    manager = build_agent("desk_manager", TestModel(
        call_tools=["inspect_collaboration"], custom_output_text="Aucun projet actif."))
    result = asyncio.run(manager.run("Quels projets sont en cours ?", deps=deps))
    assert result.output == "Aucun projet actif."
    assert deps.calls[0]["status"] == "completed"


def test_worker_runs_independent_agents_in_parallel(tmp_path, monkeypatch):
    from internships_project import city_services, state_store

    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "parallel.sqlite3")
    store = CityStore(state_store.USER_DB_PATH)
    project = store.create_custom_workflow("theo", "Parallel review", "Review code and interviews", [
        {"id":"code", "agent_id":"job_hunter", "operation":"repository_audit", "description":"Audit code", "depends_on":[]},
        {"id":"interview", "agent_id":"developer", "operation":"daily_questions", "description":"Prepare questions", "depends_on":[]},
    ])
    together = threading.Barrier(2, timeout=3)

    def technical_agent(agent_id, username, parameters):
        together.wait()
        return {"title": "Sources vérifiées", "text": "État disponible."}

    monkeypatch.setattr(city_services, "run_agent", technical_agent)
    worker = CityWorker(store)
    worker.start()
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = store.snapshot("theo")["workflows"][0]["status"]
            if status in {"completed", "failed"}:
                break
            time.sleep(0.05)
        assert store.snapshot("theo")["workflows"][0]["status"] == "completed"
        assert project["status"] == "queued"
    finally:
        worker.stop()


def test_tower_events_trace_real_handoffs_and_reject_cross_account_sources(tmp_path, monkeypatch):
    store = _workspace(tmp_path, monkeypatch)
    source = store.create_task("theo", "market_analyst", "Review markets")
    claimed = store.claim_next()
    assert claimed["id"] == source["id"]
    store.finish(source["id"], result={"offers": []})

    target = store.create_task("theo", "networker", "Review relevant contacts",
                               source_task_id=source["id"])
    snapshot = store.snapshot("theo")
    linked = next(task for task in snapshot["tasks"] if task["id"] == target["id"])
    assert linked["depends_on"] == [source["id"]]
    assert all(isinstance(event["id"], int) for event in snapshot["events"])
    assert store.snapshot("friend")["events"] == []
    with pytest.raises(CityError, match="source"):
        store.create_task("friend", "networker", "Review contacts", source_task_id=source["id"])


def test_market_snapshot_includes_wti_and_exercise_keeps_observation_date(monkeypatch):
    from internships_project import city_services
    from tests.sample_data import sample_points
    from src import data

    points = sample_points()
    monkeypatch.setattr(data, "load_snapshot", lambda: (points, {"source": "fixture"}))
    city_services._market_snapshot_cached.cache_clear()
    try:
        snapshot = city_services.market_snapshot()
        assert any(point["series_id"] == "DCOILWTICO" for point in snapshot["points"])
        exercise = city_services.market_exercise()
        assert exercise["observed_at"] == "2026-09-18"
    finally:
        city_services._market_snapshot_cached.cache_clear()
