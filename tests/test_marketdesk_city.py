"""Phase 1 City checks: real state, account isolation and allowlisted execution."""

from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from internships_project.marketdesk_city import CityError, CityStore, CityWorker, refresh_jobs_workflow


def test_agent_registry_queue_persistence_and_xp_once(tmp_path):
    path = tmp_path / "accounts.sqlite3"
    store = CityStore(path)
    initial = store.snapshot("theo")
    assert len(initial["agents"]) == 9
    assert all(agent["xp"] == 0 for agent in initial["agents"])
    created = store.create_task("theo", "networker", "Actualiser Internships", {"operation":"refresh_internships"})
    with pytest.raises(CityError, match="déjà"):
        store.create_task("theo", "networker", "Actualiser Internships", {"operation":"refresh_internships"})
    running = store.claim_next()
    assert running["id"] == created["id"]
    assert running["status"] == "running"
    store.finish(created["id"], result={"new_count": 2, "new_urls": ["https://example.com/a", "https://example.com/b"],
                                         "total_count": 102, "offers": [], "xp_award":20})
    store.finish(created["id"], result={"new_count": 9, "total_count": 109})
    reloaded = CityStore(path).snapshot("theo")
    networker = next(agent for agent in reloaded["agents"] if agent["id"] == "networker")
    assert networker["xp"] == 20
    assert networker["achievements"] == ["Première mission"]
    assert reloaded["tasks"][0]["status"] == "completed"
    assert [event["status"] for event in reloaded["events"]] == ["completed", "running", "queued"]
    repeat = store.create_task("theo", "networker", "Actualiser Internships", {"operation":"refresh_internships"})
    assert store.claim_next()["id"] == repeat["id"]
    store.finish(repeat["id"], result={"new_count": 1, "new_urls": ["https://example.com/a"]})
    assert next(agent for agent in store.snapshot("theo")["agents"] if agent["id"] == "networker")["xp"] == 20
    assert CityStore(path).snapshot("friend")["tasks"] == []


def test_sensitive_missions_and_unlimited_manual_retries(tmp_path):
    store = CityStore(tmp_path / "users.sqlite3")
    with pytest.raises(CityError, match="incompatible"):
        store.create_task("theo", "job_hunter", "Exécuter une commande shell")
    first = store.create_task("theo", "networker", "Actualiser Internships", {"operation":"refresh_internships"})
    assert store.cancel_queued("friend", first["id"]) is False
    assert store.cancel_queued("theo", first["id"]) is True
    second = store.create_task("theo", "networker", "Actualiser Internships", {"operation":"refresh_internships"})
    assert second["id"] != first["id"]
    store.claim_next()
    store.finish(second["id"], result={"new_count": 0})
    third = store.create_task("theo", "networker", "Actualiser Internships", {"operation":"refresh_internships"})
    assert third['id'] not in {first['id'], second['id']}
    assert next(agent for agent in store.snapshot("theo")["agents"] if agent["id"] == "networker")["xp"] == 0


def test_failure_and_restart_recovery(tmp_path, monkeypatch):
    from internships_project import city_services
    monkeypatch.setattr(city_services, "run_agent", lambda *args: (_ for _ in ()).throw(CityError("Source indisponible")))
    store = CityStore(tmp_path / "users.sqlite3")
    created = store.create_task("theo", "networker", "Actualiser Internships", {"operation":"refresh_internships"})
    worker = CityWorker(store)
    assert worker.run_once()
    task = store.snapshot("theo")["tasks"][0]
    assert task["status"] == "failed"
    assert task["error"] == "Source indisponible"
    assert task["xp_awarded"] == 0
    created2 = store.create_task("theo", "networker", "Actualiser Internships", {"operation":"refresh_internships"})
    assert store.claim_next()["id"] == created2["id"]
    old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec="seconds")
    with store.db() as db:
        db.execute("UPDATE city_tasks SET heartbeat_at=? WHERE id=?", (old, created2["id"]))
    assert CityStore(store.path).recover_stale() == 1
    assert store.snapshot("theo")["tasks"][0]["status"] == "failed"


def test_worker_completes_queue_and_records_service_xp(tmp_path, monkeypatch):
    from internships_project import city_services
    monkeypatch.setattr(city_services, "run_agent", lambda *args: {"new_count":1,"xp_award":10})
    store = CityStore(tmp_path / "users.sqlite3")
    store.create_task("theo", "networker", "Actualiser Internships", {"operation":"refresh_internships"})
    worker = CityWorker(store)
    assert worker.run_once()
    assert not worker.run_once()
    snapshot = store.snapshot("theo")
    assert snapshot["tasks"][0]["status"] == "completed"
    assert snapshot["tasks"][0]["xp_awarded"] == 10
    assert snapshot["today_completed"] == 1


def test_city_settings_are_account_scoped_and_validate_models(tmp_path):
    store = CityStore(tmp_path / "settings.sqlite3")
    saved = store.save_settings("theo", {"models": {"job_hunter": "gpt-4.1-mini"},
        "daily_limit_usd": 2, "monthly_limit_usd": 20, "max_concurrent_tasks": 3, "auto_tasks": False})
    assert saved["models"]["job_hunter"] == "gpt-4.1-mini"
    assert store.get_settings("friend")["models"]["job_hunter"] == "gpt-4o-mini"
    with pytest.raises(CityError, match="mod\u00e8le"):
        store.save_settings("theo", {"models": {"job_hunter": "not-a-model"}})


def test_approval_scheduling_and_mission_parameters_persist(tmp_path):
    store = CityStore(tmp_path / "scheduled.sqlite3")
    store.save_settings("theo", {"auto_tasks": False})
    scheduled = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    task = store.create_task("theo", "networker", "Review contacts", {"query": "Rates Sales"}, scheduled)
    assert task["status"] == "waiting_approval"
    assert store.claim_next() is None
    with store.db() as db:
        row = db.execute("SELECT parameters_json,scheduled_at FROM city_tasks WHERE id=?", (task["id"],)).fetchone()
    assert 'Rates Sales' in row[0]
    assert row[1] == task["scheduled_at"]
    assert store.approve_task("theo", task["id"])
    assert store.claim_next() is None
    with store.db() as db:
        db.execute("UPDATE city_tasks SET scheduled_at=NULL WHERE id=?", (task["id"],))
    claimed = store.claim_next()
    assert claimed["parameters_json"] == '{"query": "Rates Sales"}'


def test_chat_history_persists_and_is_private_per_user(tmp_path):
    store = CityStore(tmp_path / "chat.sqlite3")
    store.append_chat_message("theo", "market_analyst", "user", "What moved rates?")
    store.append_chat_message("theo", "market_analyst", "assistant", "The dated snapshot shows...")
    assert [row["role"] for row in CityStore(store.path).chat_history("theo", "market_analyst")] == ["user", "assistant"]
    assert CityStore(store.path).chat_history("friend", "market_analyst") == []
    store.clear_chat("theo", "market_analyst")
    assert store.chat_history("theo", "market_analyst") == []


def test_chat_stream_calls_real_tool_and_records_usage(tmp_path, monkeypatch):
    import asyncio
    import json
    from pydantic_ai.models.test import TestModel
    from internships_project import city_chat, city_agents, state_store
    from internships_project.llm_usage import _connect

    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "chat-stream.sqlite3")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-sent")
    store = CityStore(state_store.USER_DB_PATH)
    original = city_agents.build_agent
    monkeypatch.setattr(city_chat, "build_agent",
                        lambda agent_id, _model: original(agent_id,
                            TestModel(call_tools=["inspect_collaboration"], custom_output_text="No project running.")))

    async def collect():
        return [json.loads(line) async for line in city_chat.stream_chat(
            store, "theo", "desk_manager", "Summarize my projects")]

    frames = asyncio.run(collect())
    assert any(row["type"] == "tool" and row["name"] == "Desk Manager · suivi" for row in frames), frames
    assert any(row["type"] == "delta" and "No project running." in row["text"] for row in frames)
    assert store.chat_history("theo", "desk_manager")[-1]["content"] == "No project running.", frames
    assert store.chat_turns("theo", "desk_manager")
    with _connect() as db:
        assert db.execute("SELECT COUNT(*) FROM llm_usage WHERE username='theo'").fetchone()[0] == 1


def test_eight_agents_and_specialist_tool_contract(tmp_path, monkeypatch):
    import asyncio
    from pydantic_ai.models.test import TestModel
    from internships_project.city_agents import ChatDeps, PROMPTS, build_agent
    from internships_project.internships import load_opportunities

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-sent")
    store = CityStore(tmp_path / "city.sqlite3")
    assert len(PROMPTS) == 9
    assert len(set(PROMPTS.values())) == 9
    cached, _, _ = load_opportunities(refresh=False)
    assert isinstance(cached, list)

    async def verify():
        for agent_id in PROMPTS:
            agent = build_agent(agent_id, TestModel(call_tools=[], custom_output_text=agent_id))
            result = await agent.run("Bonjour", deps=ChatDeps("theo", store))
            assert result.output == agent_id
        agent = build_agent("job_hunter", TestModel())
        assert "execute_specialist_operation" in agent._function_toolset.tools
        assert "search_market_jobs" not in agent._function_toolset.tools
    asyncio.run(verify())


def test_city_chat_conversations_and_learning_are_isolated(tmp_path):
    store = CityStore(tmp_path / "city.sqlite3")
    mira = store.conversation_id("theo", "market_analyst")
    jules = store.conversation_id("theo", "job_hunter")
    friend = store.conversation_id("friend", "market_analyst")
    assert len({mira, jules, friend}) == 3
    store.record_learning_answer("theo", "basis_points", True)
    assert CityStore(store.path).learning_progress("theo")["correct"] == 1
    assert store.learning_progress("friend")["attempts"] == 0
    store.clear_chat("theo", "market_analyst")
    assert store.conversation_id("theo", "market_analyst") != mira
    assert store.conversation_id("theo", "job_hunter") == jules


def test_outreach_agent_reports_missing_profile_as_unavailable(tmp_path):
    import asyncio
    from pydantic_ai.models.test import TestModel
    from internships_project.city_agents import ChatDeps, build_agent

    store = CityStore(tmp_path / "city.sqlite3")
    deps = ChatDeps("new_user", store)
    agent = build_agent("outreach_agent", TestModel(
        call_tools=["read_outreach_context"], custom_output_text="Profil requis."))
    asyncio.run(agent.run("Prépare un email", deps=deps))
    assert deps.calls[0]["status"] == "unavailable"
    assert "profil" in deps.calls[0]["text"].casefold()


def test_internship_service_reuses_collector_without_sending_email(monkeypatch):
    from internships_project import internships

    now = datetime.now(timezone.utc)
    before = internships.Opportunity("Sales Intern", "Bank", "Paris", "Stage",
                                     "https://example.com/1", "", 90)
    discovered = internships.Opportunity("Rates Sales Intern", "Bank", "Paris", "Stage",
                                         "https://example.com/2", "", 98, start_period="mai 2027")
    monkeypatch.setattr(internships, "opportunities_loading", lambda: False)
    monkeypatch.setattr(internships, "load_opportunities", lambda **kwargs: ([before], [], now))
    calls = []

    def fake_refresh(*, force=False, notify_email=True, fail_if_busy=False):
        calls.append((force, notify_email, fail_if_busy))
        return [before, discovered], [], now + timedelta(seconds=1)

    monkeypatch.setattr(internships, "refresh_opportunities", fake_refresh)
    result = refresh_jobs_workflow()
    assert calls == [(True, False, True)]
    assert result["new_count"] == 1
    assert result["new_urls"] == [discovered.url]
    assert result["priority_count"] == 1
    assert result["offers"][0]["url"] == discovered.url


def test_internship_service_does_not_claim_another_refresh(monkeypatch):
    from internships_project import internships

    now = datetime.now(timezone.utc)
    monkeypatch.setattr(internships, "opportunities_loading", lambda: False)
    monkeypatch.setattr(internships, "load_opportunities", lambda **kwargs: ([], [], now))
    monkeypatch.setattr(internships, "refresh_opportunities", lambda **kwargs: (_ for _ in ()).throw(
        internships.CollectionBusyError("already running")))
    with pytest.raises(CityError, match="déjà en cours"):
        refresh_jobs_workflow()


def test_city_http_requires_same_account_and_browser_origin(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from internships_project import city_app, state_store

    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "users.sqlite3")
    monkeypatch.setattr(city_app, "store", CityStore(state_store.USER_DB_PATH))
    monkeypatch.setenv("MARKETDESK_CITY_SESSION_KEY", "t" * 48)
    monkeypatch.setenv("INTERNSHIPS_USERS_JSON", '{"theo":"admin-password-123","friend":"friend-password-123"}')
    monkeypatch.setattr(CityWorker, "start", lambda self: None)
    monkeypatch.setattr(CityWorker, "stop", lambda self: None)
    server = city_app.app
    with TestClient(server) as client:
        assert client.get("/city/").status_code == 401
        assert client.get("/city/api/state").status_code == 401
        assert client.post("/login", json={"username": "theo", "password": "admin-password-123"}).status_code == 200
        page = client.get("/city/")
        assert page.status_code == 200
        assert '/city/city.css?v=' in page.text
        assert '/city/city.js?v=' in page.text
        assert "no-store" in page.headers["cache-control"]
        bundle = client.get("/city/city.js")
        assert bundle.status_code == 200
        assert "no-cache" in bundle.headers["cache-control"]
        floor = client.get("/city/pixelfloor.html")
        assert floor.status_code == 200
        assert "window.PIXELFLOOR_CONFIG" in floor.text
        assert "desk_manager" in floor.text
        campus = client.get("/city/campus.svg")
        assert campus.status_code == 200
        assert "image/svg+xml" in campus.headers["content-type"]
        assert "DRIVING RANGE" in campus.text and "GLOBAL MARKETS" in campus.text
        assert client.get("/city/PIXELFLOOR_LICENSE.txt").status_code == 200
        assert client.get("/city/tower-robots.png").status_code == 404
        payload = {"template": "source_review", "request": "Vérifier les sources"}
        assert client.post("/city/api/workflows", json=payload).status_code == 403
        assert client.post("/city/api/tasks", headers={"X-MarketDesk-City": "1"},
                           json={"agent_id": "job_hunter"}).status_code == 403
        response = client.post("/city/api/workflows", headers={"X-MarketDesk-City": "1"}, json=payload)
        assert response.status_code == 201
        assert len(client.get("/city/api/state").json()["tasks"]) == 1
    with TestClient(server) as friend:
        assert friend.post("/login", json={"username": "friend", "password": "friend-password-123"}).status_code == 200
        assert friend.get("/city/api/state").json()["tasks"] == []


def test_deleting_member_removes_city_history(tmp_path, monkeypatch):
    from internships_project import state_store
    from internships_project.accounts import create_account, delete_registered_account

    path = tmp_path / "users.sqlite3"
    monkeypatch.setattr(state_store, "USER_DB_PATH", path)
    configured = [("theo", "admin-password-123")]
    create_account("friend", "friend-password-123", configured)
    store = CityStore(path)
    store.create_task("friend", "networker", "Actualiser Internships", {"operation":"refresh_internships"})
    store.append_chat_message("friend", "job_hunter", "user", "Follow my applications")
    store.save_settings("friend", {"auto_tasks": False})
    delete_registered_account("friend", configured)
    with sqlite3.connect(path) as db:
        for table in ("city_agents", "city_tasks", "city_events", "city_awarded_offers",
                      "city_chat_messages", "city_chat_turns", "city_chat_conversations",
                      "city_learning_progress", "city_settings", "city_network_schedule"):
            assert db.execute(f"SELECT COUNT(*) FROM {table} WHERE username='friend'").fetchone()[0] == 0
