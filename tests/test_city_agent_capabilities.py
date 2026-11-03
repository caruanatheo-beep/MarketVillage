"""Agent capability regressions: isolated accounts, mocked providers, no paid calls."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from internships_project import city_agents, city_services, state_store
from internships_project.marketdesk_city import CityError, CityStore


@pytest.fixture
def account(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "USER_DB_PATH", tmp_path / "users.sqlite3")
    state_store.save_user_data("owner", "profiles", {
        "p": {"name": "Candidate Example", "source_text": "Experienced rates sales candidate."}})
    state_store.save_user_data("owner", "mail_contacts", {
        "c": {"name": "Recipient Example", "role": "FX Sales", "company": "Bank"}})
    return CityStore(state_store.USER_DB_PATH)


def test_mira_preserves_observation_age_and_unknown_dates():
    today = datetime.now(timezone.utc).date().isoformat()
    assert city_services._observation_age(today)["age_days"] == 0
    assert city_services._observation_age(today + " 18:18 UTC")["age_days"] == 0
    assert city_services._observation_age("")["date_status"] == "unknown"
    assert city_services._observation_age("2999-01-01")["date_status"] == "future"
    from tests.sample_data import sample_points
    readings = city_services._market_readings(sample_points())
    assert readings and all("observed_at" in p and "date_status" in p for p in readings)


def test_mira_news_sorted_deduplicated_with_unknown_dates_last(monkeypatch):
    from src import news
    def article(title, date, url):
        return SimpleNamespace(title=title, published=date, url=url, source="Fixture")
    monkeypatch.setattr(news, "load_news", lambda: ([
        article("old", "2026-10-01", "https://news.example/a"),
        article("unknown", "", "https://news.example/b"),
        article("new", "2026-10-03T12:00:00Z", "https://news.example/a#section"),
        article("middle", "2026-10-02", "https://news.example/c"),
    ], ["api_key=private-value"]))
    result = city_services.market_news()
    assert [a["title"] for a in result["articles"]] == ["new", "middle", "unknown"]
    assert result["total_unique"] == 3
    assert not result["articles"][-1]["date_known"]
    assert "private-value" not in str(result)


@pytest.mark.parametrize("dates,values", [
    (("", ""), (3, 4)),
    (("2026-10-01", "2026-10-02"), (3, 4)),
    (("2026-10-01", "2026-10-01"), (float("nan"), 4)),
])
def test_noe_rejects_incomparable_observations(monkeypatch, dates, values):
    from src import data
    points = [SimpleNamespace(series_id=s, date=d, value=v)
              for s, d, v in zip(("DGS2", "DGS10"), dates, values)]
    monkeypatch.setattr(data, "load_snapshot", lambda: (points, {}))
    with pytest.raises(CityError):
        city_services.market_exercise()


@pytest.mark.parametrize("question,answer,correct", [
    ("yield_curve", "50 bp", True), ("yield_curve", "0,5 pp", True),
    ("yield_curve", "50%", False), ("basis_points", "100 bp", True),
    ("basis_points", "1 point de pourcentage", True),
])
def test_noe_grades_units_without_silently_discarding_them(account, question, answer, correct):
    ctx = SimpleNamespace(deps=city_agents.ChatDeps("owner", account, current_message=f"Ma réponse est {answer}"))
    assert city_agents._grade_quiz(ctx, question, answer)["correct"] is correct


def test_noe_cannot_grade_a_number_invented_or_stripped_by_model(account):
    ctx = SimpleNamespace(deps=city_agents.ChatDeps("owner", account, current_message="Je propose 50%"))
    with pytest.raises(CityError):
        city_agents._grade_quiz(ctx, "yield_curve", "50")
    with pytest.raises(CityError):
        city_agents._grade_quiz(ctx, "yield_curve", "0.5 pp")


def test_jules_filters_contract_and_searches_all_pages_and_description(monkeypatch):
    from internships_project import internships
    jobs = [internships.Opportunity("Sales", "Banque Étude", "Paris", "Stage" if i < 25 else "VIE",
             f"https://example.com/{i:03}", "2026-10-01", 80,
             description="x" * 1100 + " FX derivatives") for i in range(30)]
    refreshes = []
    def load(refresh=False):
        refreshes.append(refresh)
        return list(reversed(jobs)), [], datetime.now(timezone.utc)
    monkeypatch.setattr(internships, "load_opportunities", load)
    pages = [city_agents._cached_jobs("FX", bank="etude", contract="internship", page=p) for p in range(1, 5)]
    urls = [o["url"] for page in pages for o in page["offers"]]
    assert len(urls) == len(set(urls)) == 25
    assert all(page["total_matches"] == 25 for page in pages)
    assert [len(page["offers"]) for page in pages] == [8, 8, 8, 1]
    assert not pages[-1]["has_more"]
    assert all(o["contract"] == "Stage" for page in pages for o in page["offers"])
    assert city_agents._cached_jobs("FX", bank="etude", contract="Stage")["offers"] == pages[0]["offers"]
    assert not any(refreshes)


def test_lina_paginates_accent_insensitive_fx_matches_with_evidence(account):
    state_store.save_user_data("owner", "mail_contacts", {
        str(i): {"name": f"Contact {i:03}", "role": "FX", "company": "Crédit Banque"} for i in range(29)})
    pages = [city_services.network_contacts("owner", "credit FX", p) for p in (1, 2, 3)]
    ids = [c["id"] for p in pages for c in p["contacts"]]
    assert len(ids) == len(set(ids)) == 29
    assert all(p["total_matches"] == 29 for p in pages)
    assert set(pages[0]["contacts"][0]["matched_fields"]) == {"company", "role"}
    assert city_services.network_contacts("other")["total_matches"] == 0
    assert not pages[-1]["has_more"]


def test_iris_reuses_unchanged_draft_but_protects_manual_edits(account, monkeypatch):
    from internships_project import mail_outreach
    calls = []
    def draft(*args, **kwargs):
        calls.append(kwargs)
        return "Subject", "Body", "Follow-up"
    monkeypatch.setattr(mail_outreach, "draft_mail", draft)
    monkeypatch.setattr(mail_outreach, "_provider_send", lambda *a, **k: pytest.fail("Must never send"))
    assert not city_services.prepare_outreach("owner", "c", "p", "English")["reused"]
    assert city_services.prepare_outreach("owner", "c", "p", "English")["reused"]
    assert len(calls) == 1
    mail_outreach.update_contact("owner", "c", {"body": "My edited draft"})
    with pytest.raises(CityError, match="brouillon"):
        city_services.prepare_outreach("owner", "c", "p", "English")
    assert len(calls) == 1
    assert state_store.load_user_data("owner", "mail_contacts")["c"]["body"] == "My edited draft"


def test_iris_preserves_changes_made_during_generation(account, monkeypatch):
    from internships_project import mail_outreach
    def draft(*a, **k):
        mail_outreach.update_contact("owner", "c", {"body": "Concurrent edit"})
        return "Subject", "Generated body", "Follow-up"
    monkeypatch.setattr(mail_outreach, "draft_mail", draft)
    with pytest.raises(CityError, match="changé"):
        city_services.prepare_outreach("owner", "c", "p", "English")
    assert state_store.load_user_data("owner", "mail_contacts")["c"]["body"] == "Concurrent edit"


@pytest.mark.parametrize("state", [{"attempted_at": "2026-10-01"}, {"conversation": "Réponse"},
                                   {"delivery": "résultat incertain"}, {"delivery": "en attente"}])
def test_iris_will_not_restart_engaged_conversations(account, monkeypatch, state):
    from internships_project import mail_outreach
    contacts = state_store.load_user_data("owner", "mail_contacts")
    contacts["c"].update(state)
    state_store.save_user_data("owner", "mail_contacts", contacts)
    monkeypatch.setattr(mail_outreach, "draft_mail", lambda *a, **k: pytest.fail("No LLM expected"))
    with pytest.raises(CityError):
        city_services.prepare_outreach("owner", "c", "p", "English")


def test_axel_redacts_secrets_and_identifies_slow_healthy_connectors(monkeypatch):
    from internships_project import internships
    secret = 'OPENAI_API_KEY="sk-testsecret12345" password=private token=abc Bearer xyz https://me:pwd@example.com/'
    cleaned = city_services.redact_diagnostic(secret)
    for value in ("sk-testsecret12345", "private", "abc", "xyz", "me:pwd"):
        assert value not in cleaned
    monkeypatch.setattr(internships, "load_opportunities", lambda refresh=False: ([], [secret], datetime.now(timezone.utc)))
    monkeypatch.setattr(internships, "opportunities_loading", lambda: False)
    monkeypatch.setattr(internships, "source_checks", lambda: {
        "slow": {"status": "ok", "duration_ms": 9000},
        "broken": {"status": "error", "duration_ms": 200, "error": secret}})
    result = city_services.technical_report()
    assert result["slowest_sources"][0]["source"] == "slow"
    assert result["status_counts"] == {"ok": 1, "error": 1}
    assert "testsecret" not in str(result)


def test_manager_reuses_active_request_and_reads_persistent_scoped_details(account):
    original = account.create_workflow("owner", "source_review", "Review sources", "FX")
    repeat = account.create_workflow("owner", "source_review", "Review sources", "FX")
    assert repeat["id"] == original["id"] and repeat["reused"]
    assert len(account.snapshot("owner")["tasks"]) == 1
    # A repository audit has no legacy job-search focus; it reuses the same review.
    assert account.create_workflow("owner", "source_review", "Review sources", "Credit")['reused']
    with pytest.raises(CityError):
        account.workflow_details("other", original["id"])
    task = account.claim_next()
    account.finish(task["id"], result={"text": "Source result"})
    detail = CityStore(account.path).workflow_details("owner", original["id"])
    assert detail["completed_steps"] == 1 and detail["total_steps"] == 1
    assert any(s["result"].get("text") == "Source result" for s in detail["steps"])
