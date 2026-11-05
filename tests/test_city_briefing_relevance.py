"""Briefing and Hugo ranking use real stored state without paid services."""
from datetime import date, datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internships_project import city_services, internships, state_store
from internships_project.city_routes import add_city_routes
from internships_project.internship_relevance import rank_offers
from internships_project.marketdesk_city import CityStore, CityWorker


def test_hugo_profile_ranking_deadline_and_account_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "users.sqlite3")
    state_store.save_user_data("alice", "profiles", {"p": {
        "name": "Profil", "source_text": "private CV", "target_roles": ["Rates Sales"],
        "locations": ["Paris"], "start_month": "2027-04", "end_month": "2027-09"}})
    today = date.today()
    job = lambda title, place, score, deadline: internships.Opportunity(
        title, "Bank", place, "Stage", "https://example.test/" + title.replace(" ", "-"),
        today.isoformat(), score, start_period="2027-06", deadline=deadline)
    good = job("Rates Sales", "Paris", 20, (today + timedelta(days=10)).isoformat())
    general = job("Software Engineering", "London", 95, "")
    expired = job("Rates Sales Assistant", "Paris", 18, (today - timedelta(days=1)).isoformat())
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(internships, "opportunities_loading", lambda: False)
    monkeypatch.setattr(internships, "load_opportunities", lambda **kwargs: ([], [], now - timedelta(seconds=1)))
    monkeypatch.setattr(internships, "refresh_opportunities", lambda **kwargs: ([general, good, expired], [], now))
    alice = city_services.run_agent("internship_scout", "alice")
    bob = city_services.run_agent("internship_scout", "bob")
    assert alice["offers"][0]["title"] == "Rates Sales"
    assert alice["offers"][0]["match_reasons"] == ["Métier ciblé", "Lieu souhaité", "Période de début souhaitée"]
    assert alice["offers"][0]["deadline"] == good.deadline
    assert not next(o for o in alice["offers"] if o["title"] == expired.title)["deadline"]
    assert bob["profile_name"] == "" and all(not o["match_reasons"] for o in bob["offers"])
    assert "private CV" not in str(alice)


def test_manager_briefing_is_scoped_and_needs_explicit_request(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "users.sqlite3")
    store = CityStore(state_store.USER_DB_PATH)
    task = store.create_task("alice", "internship_scout", "Hugo update")
    assert store.claim_next()["id"] == task["id"]
    store.finish(task["id"], result={"text": "Deux nouveaux stages détectés.", "offers": []})
    proposal = store.create_task("alice", "job_hunter", "Corriger les cloisons", {"operation": "repository_audit"})
    assert store.claim_next()["id"] == proposal["id"]
    store.finish(proposal["id"], result={"role_version": 2, "approval_required": True})
    app = FastAPI()
    add_city_routes(app, lambda request: request.headers.get("x-test-user"), store, CityWorker(store))
    headers = {"x-test-user": "alice", "X-MarketDesk-City": "1"}
    with TestClient(app) as client:
        assert client.post("/city/api/manager/briefing", json={}).status_code == 401
        assert client.post("/city/api/manager/briefing", headers={"x-test-user": "alice"}, json={}).status_code == 403
        assert client.post("/city/api/manager/briefing", headers={**headers, "Origin": "https://evil.invalid"}, json={}).status_code == 403
        assert client.post("/city/api/manager/briefing", headers=headers, json={"agent": "bob"}).status_code == 400
        assert not store.chat_history("alice", "desk_manager")
        response = client.post("/city/api/manager/briefing", headers=headers, json={})
        assert response.status_code == 200
        assert "Deux nouveaux stages" in response.json()["content"]
        assert "Corriger les cloisons" in response.json()["content"]
        assert len(store.chat_history("alice", "desk_manager")) == 1
        assert not store.chat_history("bob", "desk_manager")
    from pydantic_ai.models.test import TestModel
    from internships_project.city_agents import build_agent
    assert "read_morning_briefing" in build_agent("desk_manager", TestModel())._function_toolset.tools


def test_ranking_does_not_infer_missing_deadline():
    offer = internships.Opportunity("Sales", "Bank", "Paris", "Stage", "https://example.test", "", 10,
                                    deadline="bientôt")
    assert rank_offers([offer], {"target_roles": ["Sales"]}, date(2026, 11, 2))[0][1]["deadline"] == ""


def test_manager_briefing_uses_successful_market_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "users.sqlite3")
    store = CityStore(state_store.USER_DB_PATH)
    failed = store.create_task("alice", "market_analyst", "Premier essai",
                               {"operation": "collect_markets"}, auto_run=True)
    assert store.claim_next()["id"] == failed["id"]
    store.finish(failed["id"], error="Markets indisponible")
    recovered = store.create_task("alice", "market_analyst", "Rattrapage",
                                  {"operation": "collect_markets"}, auto_run=True)
    assert store.claim_next()["id"] == recovered["id"]
    store.finish(recovered["id"], result={"text": "Brief vérifié du jour"})
    summary = store.morning_briefing("alice")
    assert "Brief vérifié du jour" in summary
    assert "Collecte du jour en échec" not in summary
