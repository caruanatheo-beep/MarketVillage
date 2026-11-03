from __future__ import annotations


def test_all_agents_have_real_allowlisted_workflows():
    from internships_project.marketdesk_city import AGENTS
    assert {agent["id"] for agent in AGENTS if agent["available"]} == {
        "desk_manager", "market_analyst", "finance_tutor", "job_hunter", "networker", "outreach_agent", "developer", "innovation_lab", "internship_scout"
    }


def test_networker_only_reads_the_users_existing_contacts(tmp_path, monkeypatch):
    from internships_project import state_store
    from internships_project.state_store import save_user_data
    from internships_project.city_services import network_contacts
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "users.sqlite3")
    save_user_data("theo", "mail_contacts", {
        "contact-1": {"name": "Alex Sales", "role": "Rates Sales", "company": "Bank A",
                      "location": "Paris", "linkedin_url": "https://linkedin.com/in/alex", "verification_status": "À vérifier"},
        "contact-2": {"name": "Sam Quant", "role": "Quant Research", "company": "Bank B"},
    })
    result = network_contacts("theo", "Rates Sales")
    assert result["count"] == 1
    assert result["contacts"][0]["name"] == "Alex Sales"
    assert "Aucune recherche externe" in result["warning"]
    assert network_contacts("friend")["count"] == 0


def test_market_analyst_uses_the_existing_market_brief_services(monkeypatch):
    import src.data, src.news, src.calendar
    from src.models import MarketPoint, NewsItem
    from internships_project.city_services import market_brief
    point = MarketPoint(series_id="SP500", label="S&P 500", category="Risk", value=7587.22,
                        previous=7722.36, change=-135.14, date="2026-11-03", unit="index",
                        frequency="daily", status="latest available", source_name="FRED",
                        source_url="https://fred.stlouisfed.org/series/SP500")
    monkeypatch.setattr(src.data, "load_snapshot", lambda: ([point], {"state": "cached"}))
    monkeypatch.setattr(src.news, "load_news", lambda: ([
        NewsItem("Credit union reforms", "Bank of England", "2026-11-03", "https://example.org/credit-unions"),
        NewsItem("Monetary policy decision", "ECB", "2026-11-03", "https://example.org/monetary-policy"),
    ], []))
    monkeypatch.setattr(src.calendar, "load_calendar", lambda **kwargs: ([], None))
    result = market_brief()
    assert result["market_points"] == 1
    assert "## À retenir" in result["text"]
    assert "## Prochains rendez-vous" in result["text"]
    assert "Monetary policy decision" in result["text"]
    assert "Credit union reforms" not in result["text"]
    assert "1 série vérifiée" in result["summary"]


def test_outreach_adapter_saves_a_draft_without_sending(tmp_path, monkeypatch):
    from internships_project import state_store, mail_outreach
    from internships_project.state_store import save_user_data, load_user_data
    from internships_project.city_services import prepare_outreach
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "users.sqlite3")
    save_user_data("theo", "profiles", {"p1": {"name": "Théo", "source_text": "x" * 100}})
    save_user_data("theo", "mail_contacts", {"c1": {"name": "Cam", "role": "Sales", "company": "Bank"}})
    sent = []
    monkeypatch.setattr(mail_outreach, "draft_mail", lambda *args, **kwargs: ("Objet", "Bonjour", "Relance"))
    monkeypatch.setattr(mail_outreach, "_provider_send", lambda *args, **kwargs: sent.append(args))
    result = prepare_outreach("theo", "c1", "p1", "Français")
    assert result["subject"] == "Objet"
    assert load_user_data("theo", "mail_contacts")["c1"]["body"] == "Bonjour"
    assert sent == []


def test_standalone_city_authenticates_configured_account(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from internships_project import city_app, state_store
    from internships_project.marketdesk_city import CityStore, CityWorker
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "accounts.sqlite3")
    monkeypatch.setattr(city_app, "store", CityStore(state_store.USER_DB_PATH))
    monkeypatch.setenv("MARKETDESK_CITY_SESSION_KEY", "t" * 48)
    monkeypatch.setenv("INTERNSHIPS_USERS_JSON", '{"theo":"theo-password-123"}')
    monkeypatch.setattr(CityWorker, "start", lambda self: None)
    monkeypatch.setattr(CityWorker, "stop", lambda self: None)
    with TestClient(city_app.app) as client:
        assert client.get("/city/", follow_redirects=False).status_code == 401
        assert client.get("/city/pixelfloor.html").status_code == 401
        response = client.post("/login", json={"username": "theo", "password": "theo-password-123"})
        assert response.status_code == 200
        assert "marketdesk_city_session" in response.cookies
        assert client.get("/city/").status_code == 200
        assert client.get("/city/pixelfloor.html").status_code == 200
        assert client.get("/city/tower-robots.png").status_code == 404
        assert client.get("/city/api/state").status_code == 200
