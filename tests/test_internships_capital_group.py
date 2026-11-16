"""Capital Group reuses Workday; public evidence is in SOURCES_CAPITAL_GROUP.md."""
import os

import pytest
import requests
from PIL import Image

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog
from internships_project.source_coverage import SOURCE_COVERAGE


COMPANY = "Capital Group"
BOARD = ("capgroup.wd1.myworkdayjobs.com", "capgroup", "capitalgroupcareers")
TITLE = "MBA Fixed Income Investment Analyst Summer Associate (Europe)"


def row(identity="JR5922", title=TITLE):
    return {"title": title, "locationsText": "London",
            "externalPath": f"/job/London/Fixed-Income_{identity}"}


def detail(**changes):
    return {"jobPostingInfo": {"title": TITLE, "location": "London",
        "canApply": True, "timeType": "Full time", "startDate": "2026-10-22",
        "jobDescription": "<p>Fixed Income Investment Analyst internship in London.</p>"
            "<p>Conduct fundamental research and present an investment thesis.</p>",
        **changes}}


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status
        self.headers = {"Retry-After": "120"} if status == 429 else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code), response=self)

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


@pytest.fixture
def serve(monkeypatch):
    calls = []

    def setup(pages=None, info=None, status=200, detail_status=200):
        pages = {0: {"total": 1, "jobPostings": [row()]}} if pages is None else pages

        def post(url, **kwargs):
            calls.append(("POST", url, kwargs["json"]))
            payload = pages[kwargs["json"]["offset"]]
            if isinstance(payload, requests.RequestException):
                raise payload
            return Response(payload, status)

        def get(url, **kwargs):
            calls.append(("GET", url, kwargs))
            return Response(detail() if info is None else info, detail_status)

        monkeypatch.setattr(jobs.requests, "post", post)
        monkeypatch.setattr(jobs.requests, "get", get)
        monkeypatch.setattr(jobs, "_cached_detail", lambda job: pytest.fail("live detail required"))
        monkeypatch.setattr(jobs.time, "sleep", lambda seconds: pytest.fail("no immediate retry"))
        return calls

    return setup


def collect():
    return jobs._workday_jobs(COMPANY, BOARD)


def test_registered_once_with_asset_management_category_date_and_official_logo():
    assert jobs.WORKDAY[COMPANY] == BOARD
    assert [(fn, args) for name, fn, args in jobs._opportunity_source_tasks() if name == COMPANY] == [
        (jobs._workday_jobs, (COMPANY, BOARD))]
    source, = [s for s in public_source_catalog() if s["name"] == COMPANY]
    assert source["category"] == "Gestion d’actifs"
    assert source["added_on"] == "2026-11-15"
    assert source["url"] == f"https://{BOARD[0]}/en-US/{BOARD[2]}"
    assert SOURCE_COVERAGE[COMPANY].status == "connected"
    with Image.open(jobs.COMPANY_LOGO_DIR / "www.capitalgroup.com.png") as logo:
        assert logo.format == "PNG" and 0 < logo.width <= 96 and 0 < logo.height <= 96
        logo.verify()
    assert jobs._company_icon(COMPANY).startswith("data:image/png;base64,")


def test_verified_fixed_income_internship_and_unfiltered_global_scan(serve):
    calls = serve()
    job, = collect()
    assert (job.company, job.kind, job.location, job.family) == (COMPANY, "Stage", "London", "Quant / Research")
    assert job.published == "2026-10-22"
    assert job.start_period == job.deadline == ""
    assert "fundamental research" in job.description
    assert jobs.is_trusted_offer_url(job.url)
    assert calls[0][2] == {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}


@pytest.mark.parametrize("title", ["Senior Fixed Income Product Manager", "Compliance Analyst Intern",
    "Fund Accounting Intern", "Software Engineering Intern"])
def test_unrelated_and_experienced_titles_are_excluded(serve, title):
    calls = serve(pages={0: {"total": 1, "jobPostings": [row(title=title)]}})
    assert collect() == [] and len(calls) == 1


@pytest.mark.parametrize("status", [403, 429, 500])
def test_api_failure_stops_without_retry_or_unverified_html_fallback(serve, status):
    calls = serve(status=status)
    with pytest.raises(requests.HTTPError):
        collect()
    assert len(calls) == 1 and calls[0][0] == "POST"


@pytest.mark.parametrize("payload", [{}, [], {"total": 0}, {"total": "1", "jobPostings": []},
    {"total": 1, "jobPostings": []}, {"total": 1, "jobPostings": [{}]},
    {"total": 1, "jobPostings": [None]}, ValueError("invalid JSON"), requests.Timeout("offline")])
def test_invalid_or_incomplete_catalogue_is_not_empty_success(serve, payload):
    calls = serve(pages={0: payload})
    with pytest.raises((ValueError, requests.RequestException)):
        collect()
    assert len(calls) == 1


def test_verified_empty_catalogue(serve):
    calls = serve(pages={0: {"total": 0, "jobPostings": []}})
    assert collect() == [] and len(calls) == 1


@pytest.mark.parametrize("info,status", [({}, 200), ([], 200), ({"jobPostingInfo": []}, 200),
    (detail(jobDescription=""), 200), (detail(canApply=None), 200), (detail(location=""), 200),
    (detail(), 403), (detail(), 429), (detail(), 500)])
def test_unverified_detail_reports_partial_without_publishing_listing_only(serve, info, status):
    calls = serve(info=info, detail_status=status)
    with pytest.raises(jobs._PartialSourceError) as failure:
        collect()
    assert not failure.value.jobs and len(failure.value.failed_urls) == 1
    assert len(calls) == 2


@pytest.mark.parametrize("changes,status", [({"canApply": False}, 200), ({}, 404), ({}, 410),
    ({"validThrough": "2020-01-01"}, 200), ({"title": "Senior Fixed Income Analyst"}, 200)])
def test_closed_expired_and_changed_roles_are_excluded(serve, changes, status):
    serve(info=detail(**changes), detail_status=status)
    assert collect() == []


def test_dates_never_inferred_from_detection_or_graduation(serve):
    serve(info=detail(startDate="", postedOn="Posted 30+ Days Ago",
        jobDescription="Fixed Income internship. Graduation June 2028. Ten weeks."))
    job, = collect()
    assert (job.published, job.start_period, job.deadline) == ("", "", "")


def test_explicit_program_start_and_deadline_stay_separate_from_publication(serve):
    serve(info=detail(validThrough="2099-01-01", jobDescription=
        "Fixed Income internship. Start date: January 2027."))
    job, = collect()
    assert (job.published, job.start_period, job.deadline) == ("2026-10-22", "January 2027", "2099-01-01")


def test_pagination_keeps_initial_total_and_deduplicates_details(serve):
    first = [row()] + [row(str(i), "Accountant") for i in range(19)]
    calls = serve(pages={0: {"total": 21, "jobPostings": first},
                         20: {"total": 0, "jobPostings": [row()]}})
    found = collect()
    assert len(found) == len(jobs._deduplicate_opportunities(found)) == 1
    assert [c[2]["offset"] for c in calls if c[0] == "POST"] == [0, 20]
    assert sum(c[0] == "GET" for c in calls) == 1


def test_every_candidate_is_verified_even_beyond_default_enrichment_limit(serve):
    pages = {offset: {"total": 51, "jobPostings": [row(str(i))
        for i in range(offset, min(offset + 20, 51))]} for offset in (0, 20, 40)}
    calls = serve(pages=pages)
    found = collect()
    assert len(found) == sum(c[0] == "GET" for c in calls) == 51
    assert all(job.description and job.published == "2026-10-22" for job in found)


@pytest.mark.parametrize("second", [requests.HTTPError("429"), {"total": 40, "jobPostings": []}, "repeat"])
def test_failed_later_page_preserves_verified_results_as_partial(serve, second):
    first = [row()] + [row(str(i), "Accountant") for i in range(19)]
    if second == "repeat":
        second = {"total": 40, "jobPostings": first}
    serve(pages={0: {"total": 40, "jobPostings": first}, 20: second})
    with pytest.raises(jobs._PartialSourceError) as failure:
        collect()
    assert len(failure.value.jobs) == 1


@pytest.mark.skipif(os.environ.get("INTERNSHIPS_CAPITAL_GROUP_LIVE") != "1", reason="Public live audit is opt-in")
def test_live_collection(monkeypatch):
    # No cache, user files, browser profile or persistence is read.
    monkeypatch.setattr(jobs, "_cached_detail", lambda job: None)
    found = collect()
    assert any("Fixed Income" in job.title and job.location == "London" for job in found)
    assert all(job.company == COMPANY and job.description and jobs.is_trusted_offer_url(job.url) for job in found)
    assert len(found) == len(jobs._deduplicate_opportunities(found))
    print(f"Capital Group: {len(found)} verified public offers")
    for job in found:
        print(f"{job.title} | {job.location} | published={job.published}")
