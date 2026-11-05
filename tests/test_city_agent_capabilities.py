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


@pytest.mark.parametrize("observed,age,status", [
    ("2026-01-03T00:30:00+02:00", 0, "dated"),
    ("2026-01-01T23:30:00-02:00", 0, "dated"),
    ("2026-01-02T23:30:00-02:00", -1, "future"),
    ("2026-01-02T00:30:00+02:00", 1, "dated"),
    ("2026-01-02T00:30:00Z", 0, "dated"),
    ("2026-01-02T00:30:00", 0, "dated"),
    ("2026-01-02 18:18 UTC", 0, "dated"),
    ("2026-01-02", 0, "dated"),
    ("0001-01-01T00:00:00+01:00", None, "unknown"),
    ("9999-12-31T23:30:00-01:00", None, "unknown"),
])
def test_mira_observation_age_uses_utc_calendar_dates(monkeypatch, observed, age, status):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 1, 2, 12, tzinfo=timezone.utc)

    monkeypatch.setattr(city_services, "datetime", FixedDatetime)
    result = city_services._observation_age(observed)
    assert result["age_days"] == age
    assert result["date_status"] == status


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


def test_mira_news_recognizes_provider_utc_dates_before_deduplication(monkeypatch):
    from src import news
    from src.models import NewsItem

    provider_date = "2026-11-05 18:18 UTC"
    monkeypatch.setattr(news, "load_news", lambda: ([
        NewsItem("older copy", "Fixture", "2026-11-05T18:00:00Z", "https://news.example/a"),
        NewsItem("unknown", "Fixture", "time unavailable", "https://news.example/b"),
        NewsItem("provider", "Fixture", provider_date, "https://news.example/a#latest"),
        NewsItem("offset", "Fixture", "2026-11-05T20:19:00+02:00", "https://news.example/c"),
        NewsItem("undated", "Fixture", "", "https://news.example/d"),
    ], []))

    result = city_services.market_news()

    assert [a["title"] for a in result["articles"]] == ["offset", "provider", "unknown", "undated"]
    assert [a["date_known"] for a in result["articles"]] == [True, True, False, False]
    assert result["articles"][1]["published"] == provider_date
    assert result["total_unique"] == 4


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


def test_manager_searches_next_internship_page_with_filters(monkeypatch):
    import asyncio
    from internships_project import internships
    from pydantic_ai.models.test import TestModel

    jobs = [internships.Opportunity(
        "FX Sales", "Banque Étude", "Paris", "Stage",
        f"https://example.com/{i:03}", "2026-10-01", 80,
        start_period="January 2027") for i in range(10)]
    jobs.extend([
        internships.Opportunity("FX Sales", company, location, contract,
                                f"https://example.com/excluded-{i}", "2026-10-01", 80,
                                start_period=start)
        for i, (company, location, contract, start) in enumerate([
            ("Other Bank", "Paris", "Stage", "January 2027"),
            ("Banque Étude", "London", "Stage", "January 2027"),
            ("Banque Étude", "Paris", "VIE", "January 2027"),
            ("Banque Étude", "Paris", "Stage", "June 2027"),
        ])
    ])
    refreshes = []

    def load(refresh=False):
        refreshes.append(refresh)
        return jobs, [], datetime.now(timezone.utc)

    monkeypatch.setattr(internships, "load_opportunities", load)
    tool = city_agents.build_agent("desk_manager", TestModel())._function_toolset.tools[
        "search_internship_cache"].function
    ctx = SimpleNamespace(deps=city_agents.ChatDeps("owner", None))
    result = asyncio.run(tool(ctx, "FX", bank="etude", location="Paris",
                              start="January", contract="internship", page=2))

    assert result["status"] == "completed"
    data = result["data"]
    assert data["total_matches"] == 10
    assert data["page"] == 2 and not data["has_more"]
    assert len(data["offers"]) == 2
    assert {offer["url"] for offer in data["offers"]} == {
        "https://example.com/001", "https://example.com/000"}
    assert refreshes == [False]

    # Existing callers can still search without supplying optional filters.
    result = asyncio.run(tool(ctx, "FX"))
    assert result["data"]["total_matches"] == 14
    assert result["data"]["page"] == 1
    assert result["data"]["has_more"]
    assert refreshes == [False, False]


def test_manager_recent_internships_require_confirmed_dates_and_preserve_pagination(monkeypatch):
    import asyncio
    from internships_project import internships
    from pydantic_ai.models.test import TestModel

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            # Already November 6 in Paris, still November 5 in UTC.
            return cls(2026, 11, 5, 23, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(city_agents, "datetime", FixedDatetime)

    def offer(index, published, inferred=False):
        return internships.Opportunity(
            "FX Sales", "Bank", "Paris", "Stage", f"https://example.com/{index:03}",
            published, 80, published_inferred=inferred)

    jobs = [offer(i, day) for i, day in enumerate([
        "2026-11-06", "2026-11-05", "2026-11-04", "2026-11-03", "2026-11-02",
        "2026-11-01", "2026-10-31", "2026-11-06", "2026-11-05", "2026-11-04",
    ])]
    excluded = [offer(20 + i, day) for i, day in enumerate([
        "2026-10-30", "2026-11-07", "", "unknown", "2026-11-00", "2026-11-31",
    ])] + [offer(30, "2026-11-06", inferred=True)]
    refreshes = []

    def load(refresh=False):
        refreshes.append(refresh)
        return jobs + excluded, [], FixedDatetime.now(timezone.utc)

    monkeypatch.setattr(internships, "load_opportunities", load)
    tool = city_agents.build_agent("desk_manager", TestModel())._function_toolset.tools[
        "search_internship_cache"].function
    ctx = SimpleNamespace(deps=city_agents.ChatDeps("owner", None))
    results = [asyncio.run(tool(ctx, "FX", recent_only=True, page=page)) for page in (1, 2)]

    assert all(result["status"] == "completed" for result in results)
    pages = [result["data"] for result in results]
    assert all(page["total_matches"] == 10 and page["recent_window_days"] == 7 for page in pages)
    assert [len(page["offers"]) for page in pages] == [8, 2]
    assert [page["has_more"] for page in pages] == [True, False]
    urls = [item["url"] for page in pages for item in page["offers"]]
    assert len(urls) == len(set(urls)) == 10
    assert set(urls) == {job.url for job in jobs}

    unfiltered = asyncio.run(tool(ctx, "FX"))["data"]
    assert unfiltered["total_matches"] == len(jobs + excluded)
    assert unfiltered["recent_window_days"] is None
    assert refreshes == [False, False, False]


@pytest.mark.parametrize("page", [0, -1, True, 1.5, "2"])
def test_manager_rejects_invalid_internship_page_without_loading(monkeypatch, page):
    import asyncio
    from internships_project import internships
    from pydantic_ai.models.test import TestModel

    monkeypatch.setattr(internships, "load_opportunities",
                        lambda **kwargs: pytest.fail("Invalid pages must not load offers"))
    tool = city_agents.build_agent("desk_manager", TestModel())._function_toolset.tools[
        "search_internship_cache"].function
    ctx = SimpleNamespace(deps=city_agents.ChatDeps("owner", None))

    result = asyncio.run(tool(ctx, page=page))

    assert result["status"] == "unavailable"
    assert "entier positif" in result["reason"]


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
