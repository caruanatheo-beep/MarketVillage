"""Source recovery without network or repository data."""
from datetime import datetime, timedelta, timezone
from threading import Lock

import pytest
from internships_project import internships as m


@pytest.fixture
def source_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "CACHE_PATH", tmp_path / "offers.json")
    monkeypatch.setattr(m, "_source_job_cache_path", None)
    monkeypatch.setattr(m, "_source_job_cache", {})
    m._load_source_job_cache()
    return m._source_job_cache


def offer(url, title="Rates Sales Intern"):
    return m.Opportunity(title, "Test bank", "Paris", "Stage", url, "", 90)


def test_manual_refresh_bypasses_backoff_but_background_waits(source_cache):
    old = offer("https://example.invalid/old")
    now = datetime.now(timezone.utc).isoformat()
    source_cache["Test bank"] = {"updated": now, "jobs": [old], "connector_version": 1,
        "check": {"status": "stale", "error": "timeout", "next_retry_at":
                  (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}}
    calls = []
    def collect():
        calls.append(True)
        return [offer("https://example.invalid/new")]
    jobs, check, error = m._collect_source("Test bank", collect, (), False)
    assert jobs == [old] and check["cache_status"] == "backoff" and not calls
    jobs, check, error = m._collect_source("Test bank", collect, (), True)
    assert len(calls) == 1 and jobs[0].url.endswith("/new")
    assert check["status"] == "ok" and not error


def test_partial_search_keeps_cached_offers_and_prefers_fresh_details(source_cache):
    old = offer("https://example.invalid/old")
    updated = offer(old.url, "Updated Rates Sales Intern")
    retained = offer("https://example.invalid/retained")
    source_cache["Test bank"] = {"updated": "2026-01-01T00:00:00+00:00",
        "jobs": [old, retained], "connector_version": 1, "check": {}}
    def collect():
        raise m._PartialSourceError([updated], [], search_failures=1)
    jobs, check, error = m._collect_source("Test bank", collect, (), True)
    assert len(jobs) == 2 and {j.url: j.title for j in jobs}[old.url] == updated.title
    assert check["status"] == "stale" and check["cache_status"] == "partial"
    assert "requête(s) source" in error
    assert source_cache["Test bank"]["jobs"] == [updated, retained]
    assert source_cache["Test bank"]["updated"] == "2026-01-01T00:00:00+00:00"


def test_first_partial_collection_survives_restart_and_backoff(source_cache, monkeypatch):
    found = offer("https://example.invalid/new")
    def collect():
        raise m._PartialSourceError([found], [], search_failures=1)
    m._collect_source("Test bank", collect, (), True)
    m._write_source_job_cache()
    monkeypatch.setattr(m, "_source_job_cache", {})
    monkeypatch.setattr(m, "_source_job_cache_path", None)
    def unexpected_fetch():
        pytest.fail("backoff should reuse the partial result")
    jobs, check, error = m._collect_source("Test bank", unexpected_fetch, (), False)
    assert jobs == [found] and check["cache_status"] == "backoff"
    assert check["last_success"] == "" and error


def test_expired_backoff_retries_even_with_recent_successful_cache(source_cache):
    now = datetime.now(timezone.utc)
    old = offer("https://example.invalid/old")
    source_cache["Test bank"] = {"updated": now.isoformat(), "jobs": [old],
        "check": {"status": "stale", "next_retry_at": (now - timedelta(seconds=1)).isoformat()}}
    calls = []
    def collect():
        calls.append(True)
        return [offer("https://example.invalid/new")]
    jobs, check, error = m._collect_source("Test bank", collect, (), False)
    assert calls == [True] and jobs[0].url.endswith("/new")
    assert check["status"] == "ok" and not error
    m._collect_source("Test bank", collect, (), False)
    assert calls == [True]  # Healthy sources keep their normal cache interval.


@pytest.mark.parametrize("due", [True, False])
def test_retry_deadline_triggers_refresh_before_snapshot_expires(monkeypatch, due):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(m, "_cache", (now, [], []))
    monkeypatch.setattr(m, "_last_attempt", None)
    monkeypatch.setattr(m, "_refresh_worker", None)
    monkeypatch.setattr(m, "_source_checks", {"Test bank": {
        "status": "stale", "next_retry_at": (now + timedelta(minutes=-1 if due else 10)).isoformat()}})
    started = []
    class Thread:
        def __init__(self, **kwargs): pass
        def start(self): started.append(True)
        def is_alive(self): return True
    monkeypatch.setattr(m.threading, "Thread", Thread)
    m.load_opportunities()
    assert started == ([True] if due else [])


def test_board_distinguishes_partial_cached_and_unreachable_sources(monkeypatch):
    monkeypatch.setattr(m, "source_checks", lambda: {
        "Partial": {"status": "stale", "cache_status": "partial", "count": 2},
        "Cached": {"status": "stale", "cache_status": "backoff", "count": 3},
        "Unavailable": {"status": "error", "count": None}})
    board = m.render_opportunities([], ["Partial: timeout", "Cached: timeout",
        "Unavailable: timeout", "Unavailable: timeout"], datetime.now(timezone.utc))
    assert "1 source inaccessible" in board
    assert "1 collecte partielle" in board
    assert "1 source avec offres conservées" in board
    assert "sources indisponibles" not in board


def test_progressive_refresh_uses_bounded_parallel_source_collection(monkeypatch):
    workers = []
    real_pool = m.ThreadPoolExecutor

    def recording_pool(*, max_workers, **kwargs):
        workers.append(max_workers)
        return real_pool(max_workers=max_workers, **kwargs)

    for mapping in ("SMARTRECRUITERS", "GREENHOUSE", "LEVER", "ASHBY", "WORKDAY",
                    "ORACLE_CAREER_BOARDS", "CAREER_LISTINGS"):
        monkeypatch.setattr(m, mapping, {})
    monkeypatch.setattr(m, "_collect_source", lambda *args: ([], {"status": "empty"}, ""))
    monkeypatch.setattr(m, "_publish_refresh_progress", lambda *args: None)
    monkeypatch.setattr(m, "_write_source_job_cache", lambda: None)
    monkeypatch.setattr(m, "_force_source_refresh", False)
    monkeypatch.setattr(m, "ThreadPoolExecutor", recording_pool)

    m._fetch_opportunities_progressive()

    assert workers == [m.SOURCE_COLLECTION_WORKERS]


@pytest.mark.parametrize("permanent", [False, True])
def test_workday_retries_invalid_json_without_accepting_empty_success(monkeypatch, permanent):
    calls = []
    monkeypatch.setattr(m.time, 'sleep', lambda seconds: None)
    class Response:
        def raise_for_status(self): pass
        def json(self):
            if permanent or len(calls) == 1: raise ValueError('empty transient response')
            return {'total':1,'jobPostings':[{'title':'Rates Sales Intern','locationsText':'Paris','externalPath':'/job/Paris/Sales_R1'}]}
    def post(*args, **kwargs): calls.append(kwargs); return Response()
    monkeypatch.setattr(m.requests, 'post', post)
    monkeypatch.setattr(m, '_cached_detail', lambda job: job)
    monkeypatch.setattr(m.requests, 'get', lambda *a, **k: type('R',(),{'raise_for_status':lambda self:None,'json':lambda self:{'jobPostingInfo':{}}})())
    if permanent:
        with pytest.raises(ValueError, match='non JSON'):
            m._workday_jobs('Deutsche Bank',m.WORKDAY['Deutsche Bank'])
    else:
        assert len(m._workday_jobs('Deutsche Bank',m.WORKDAY['Deutsche Bank'])) == 1
    assert len(calls) == (3 if permanent else 2)


def test_workday_all_searches_failed_stays_an_error(monkeypatch):
    def post(*args, **kwargs): raise m.requests.Timeout("unreachable")
    monkeypatch.setattr(m.requests, "post", post)
    with pytest.raises(m.requests.Timeout):
        m._workday_jobs("Deutsche Bank", ("db.wd3.myworkdayjobs.com", "db", "DBWebsite"))


@pytest.mark.parametrize("detail_error", [False, True])
def test_bnp_readable_nonmatching_offers_are_empty_not_unavailable(monkeypatch, detail_error):
    import sys
    import types
    class Locator:
        @property
        def first(self): return self
        @property
        def last(self): return self
        def wait_for(self, **kwargs): pass
        def evaluate_all(self, *args): return []
        def is_visible(self, **kwargs): return False
    class Page:
        def goto(self, *args, **kwargs): return types.SimpleNamespace(status=200)
        def locator(self, *args): return Locator()
        def get_by_text(self, *args): return Locator()
        def content(self): return '<a href="/emploi-carriere/offre-emploi/trading-analyst">Trading analyst</a>'
    browser = types.SimpleNamespace(new_page=lambda: Page(), close=lambda: None)
    class Playwright:
        chromium = types.SimpleNamespace(launch=lambda **kwargs: browser)
        def __enter__(self): return self
        def __exit__(self, *args): pass
    fake = types.ModuleType("playwright.sync_api")
    fake.TimeoutError = TimeoutError
    fake.sync_playwright = Playwright
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake)
    def detail(*args, **kwargs):
        if detail_error: raise ValueError("unreadable detail")
        return None
    monkeypatch.setattr(m, "_career_detail", detail)
    if detail_error:
        with pytest.raises(m._PartialSourceError) as failure:
            m._bnp_group_jobs_browser("BNP Paribas Asset Management", "https://group.bnpparibas/listing")
        assert failure.value.failed_urls == {"https://group.bnpparibas/emploi-carriere/offre-emploi/trading-analyst"}
    else:
        assert m._bnp_group_jobs_browser("BNP Paribas Asset Management", "https://group.bnpparibas/listing") == []
