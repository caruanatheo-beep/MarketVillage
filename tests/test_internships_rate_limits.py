"""Employer rate limits preserve offers and postpone collection without sleeping."""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

from internships_project import internships as jobs


@pytest.fixture
def source_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "CACHE_PATH", tmp_path / "offers.json")
    monkeypatch.setattr(jobs, "_source_job_cache_path", None)
    monkeypatch.setattr(jobs, "_source_job_cache", {})
    jobs._load_source_job_cache()
    return jobs._source_job_cache


def offer(url, title="Rates Sales Intern"):
    return jobs.Opportunity(title, "Test bank", "Paris", "Stage", url, "", 90)


def limited(status=429, retry_after="7200"):
    response = requests.Response()
    response.status_code = status
    response.headers["Retry-After"] = retry_after
    return response


@pytest.mark.parametrize("company", ["Deutsche Bank", "Capital Group"])
@pytest.mark.parametrize("status,header", [(403, ""), (429, ""), (429, "7200"), (503, "7200")])
def test_workday_stops_at_refusal_or_server_pause(monkeypatch, company, status, header):
    calls = []
    def post(*args, **kwargs):
        calls.append(kwargs)
        return limited(status, header)
    monkeypatch.setattr(jobs.requests, "post", post)
    monkeypatch.setattr(jobs.time, "sleep", lambda _: pytest.fail("must defer without sleeping"))
    with pytest.raises(requests.HTTPError):
        jobs._workday_jobs(company, jobs.WORKDAY[company])
    assert len(calls) == 1


@pytest.mark.parametrize("header", ["7200", "http-date"])
@pytest.mark.parametrize("cached", [False, True])
def test_server_pause_survives_restart_manual_refresh_and_version_change(source_cache, monkeypatch, header, cached):
    now = datetime.now(timezone.utc)
    expected = (now + timedelta(hours=2)).replace(microsecond=0)
    header = format_datetime(expected, usegmt=True) if header == "http-date" else header
    old = offer("https://example.invalid/sales-intern")
    if cached:
        source_cache["Test bank"] = {"updated": now.isoformat(), "jobs": [old], "check": {}}
    calls = []
    def collect():
        calls.append(True)
        limited(retry_after=header).raise_for_status()
    found, check, error = jobs._collect_source("Test bank", collect, (), True)
    assert found == ([old] if cached else []) and "HTTP 429" in error
    assert datetime.fromisoformat(check["next_retry_at"]) >= expected
    jobs._write_source_job_cache()
    monkeypatch.setattr(jobs, "_source_job_cache", {})
    monkeypatch.setattr(jobs, "_source_job_cache_path", None)
    monkeypatch.setitem(jobs.SOURCE_CONNECTOR_VERSIONS, "Test bank", 99)
    for force in (False, True):
        found, check, _ = jobs._collect_source("Test bank", collect, (), force)
        assert found == ([old] if cached else []) and check["cache_status"] == "backoff"
    assert calls == [True]


@pytest.mark.parametrize("header", ["", "nonsense", "-5", "Wed, 01 Jan 2020 00:00:00 GMT", "9" * 100])
def test_invalid_retry_after_keeps_normal_backoff(source_cache, header):
    def collect():
        limited(retry_after=header).raise_for_status()
    _, check, _ = jobs._collect_source("Test bank", collect, (), True)
    elapsed = (datetime.fromisoformat(check["next_retry_at"]) - datetime.fromisoformat(check["checked_at"])).total_seconds()
    assert elapsed == jobs.SOURCE_RETRY_BASE_SECONDS


def test_later_page_limit_skips_details_and_preserves_cached_offers(source_cache, monkeypatch):
    company = "Capital Group"
    old = offer("https://example.invalid/cached")
    source_cache[company] = {"updated": "2026-01-01T00:00:00+00:00", "jobs": [old], "check": {}}
    calls = []
    def post(url, json, **kwargs):
        calls.append(json["offset"])
        if json["offset"]:
            return limited()
        class Response:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {"total": 40, "jobPostings": [dict(title="Fixed Income Sales Intern",
                    externalPath=f"/job/London/Sales_{i}", locationsText="London") for i in range(20)]}
        return Response()
    monkeypatch.setattr(jobs.requests, "post", post)
    monkeypatch.setattr(jobs.requests, "get", lambda *a, **k: pytest.fail("server pause applies to details too"))
    collect = lambda: jobs._workday_jobs(company, jobs.WORKDAY[company])
    found, check, _ = jobs._collect_source(company, collect, (), True)
    assert found == [old] and check["cache_status"] == "partial"
    assert calls == [0, 20]
    assert datetime.fromisoformat(check["next_retry_at"]) >= datetime.fromisoformat(check["checked_at"]) + timedelta(seconds=7199)


def test_detail_limit_stops_queued_requests_and_keeps_only_known_offers(source_cache, monkeypatch):
    company = "Capital Group"
    rows = [dict(title="Fixed Income Sales Intern", externalPath=f"/job/London/Sales_{i}",
                 locationsText="London") for i in range(3)]
    old = offer(f"https://{jobs.WORKDAY[company][0]}/en-US/{jobs.WORKDAY[company][2]}{rows[0]['externalPath']}")
    source_cache[company] = {"updated": "2026-01-01T00:00:00+00:00", "jobs": [old], "check": {}}
    # Serial execution makes requests queued behind the refusal deterministic.
    monkeypatch.setattr(jobs, 'ThreadPoolExecutor', lambda **kwargs: ThreadPoolExecutor(max_workers=1))
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"total": 3, "jobPostings": rows}
    monkeypatch.setattr(jobs.requests, 'post', lambda *a, **k: Response())
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return limited()
    monkeypatch.setattr(jobs.requests, 'get', get)
    collect = lambda: jobs._workday_jobs(company, jobs.WORKDAY[company])
    found, check, _ = jobs._collect_source(company, collect, (), True)
    assert len(calls) == 1 and found == [old]
    assert check['cache_status'] == 'partial' and check['retry_not_before']


def test_collection_resumes_after_server_pause_and_clears_failure(source_cache):
    now = datetime.now(timezone.utc)
    source_cache['Test bank'] = {'updated': now.isoformat(), 'jobs': [], 'check': {
        'status': 'error', 'failure_count': 2,
        'retry_not_before': (now - timedelta(seconds=2)).isoformat(),
        'next_retry_at': (now - timedelta(seconds=1)).isoformat()}}
    fresh = offer('https://example.invalid/fresh')
    found, check, error = jobs._collect_source('Test bank', lambda: [fresh], (), False)
    assert found == [fresh] and check['status'] == 'ok' and not error
    assert 'retry_not_before' not in check and 'failure_count' not in check


def test_workday_keeps_reading_when_one_listing_row_is_incomplete(monkeypatch):
    title = "Fixed Income Sales Intern"
    complete = dict(title=title, externalPath="/job/London/Sales_1", locationsText="London")

    class Listing:
        def raise_for_status(self):
            pass

        def json(self):
            return {"total": 2, "jobPostings": [{"title": "Truncated row"}, complete]}

    class Detail(Listing):
        def json(self):
            return {"jobPostingInfo": {
                "title": title, "canApply": True, "location": "London",
                "jobDescription": "Internship supporting an institutional fixed income sales desk.",
            }}

    monkeypatch.setattr(jobs.requests, "post", lambda *a, **k: Listing())
    monkeypatch.setattr(jobs.requests, "get", lambda *a, **k: Detail())
    with pytest.raises(jobs._PartialSourceError, match="Annonce Workday incomplète") as partial:
        jobs._workday_jobs("LSEG", jobs.WORKDAY["LSEG"])
    assert [item.title for item in partial.value.jobs] == [title]
    assert partial.value.preserve_cached


def test_banque_de_france_preserves_rate_limited_details(source_cache, monkeypatch):
    company = "Banque de France"
    url = "https://bdf.wd103.myworkdayjobs.com/fr-FR/recrutement-banque-de-France/job/Paris/Trading_1"
    old = offer(url, "Trading Intern")
    source_cache[company] = {"updated": "2026-01-01T00:00:00+00:00", "jobs": [old], "check": {}}

    class Listing:
        def raise_for_status(self):
            pass

        def json(self):
            return {"total": 1, "jobPostings": [
                {"title": "Trading Intern", "externalPath": "/job/Paris/Trading_1"},
            ]}

    monkeypatch.setattr(jobs.requests, "post", lambda *a, **k: Listing())
    monkeypatch.setattr(jobs.requests, "get", lambda *a, **k: limited())
    found, check, error = jobs._collect_source(company, jobs._banque_de_france_jobs, (), True)
    assert found == [old]
    assert check["cache_status"] == "partial" and check["retry_not_before"]
    assert "HTTP 429" in error
