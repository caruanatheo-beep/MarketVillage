"""TP ICAP extends the existing Workday connector; no HTML fallback is claimed.

Public audit and candidate comparison: see internships_project/SOURCES_TP_ICAP.md.
Fixtures are synthetic. The live check reads public career/catalogue data only.
"""
import os
from collections import Counter
from time import perf_counter

import pytest
import requests
from PIL import Image

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog


BOARD = ("tp.wd107.myworkdayjobs.com", "tp", "TP-ICAP")
TITLE = "Liquidnet Equities Sales & Trading Summer Internship"


def row(identity="R1", title=TITLE):
    return {"title": title, "locationsText": "New York",
            "externalPath": f"/job/New-York/Sales_{identity}", "postedOn": "Posted 2 Days Ago"}


def detail(**changes):
    return {"jobPostingInfo": {
        "title": TITLE, "canApply": True, "location": "New York",
        "timeType": "Full time", "startDate": "2026-11-13",
        "jobDescription": "<p>Institutional equities Sales team; 10-week internship.</p>"
            "<p>Program dates: Tuesday, June 1 – Friday, August 6, 2027</p>"
            "<p>Graduation date June 2028. We do not offer visa sponsorship.</p>"
            "<p>English required.</p>", **changes}}


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

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
            if isinstance(payload, Exception):
                raise payload
            return Response(payload, status)
        def get(url, **kwargs):
            calls.append(("GET", url, kwargs))
            return Response(detail() if info is None else info, detail_status)
        monkeypatch.setattr(jobs.requests, "post", post)
        monkeypatch.setattr(jobs.requests, "get", get)
        monkeypatch.setattr(jobs, "_cached_detail", lambda job: pytest.fail("must verify live detail"))
        monkeypatch.setattr(jobs.time, "sleep", lambda seconds: pytest.fail("no immediate retry"))
        return calls
    return setup


def collect():
    return jobs._workday_jobs("TP ICAP", BOARD)


def test_registered_once_with_category_date_employer_link_and_verified_png():
    assert jobs.WORKDAY["TP ICAP"] == BOARD
    tasks = [(fn, args) for name, fn, args in jobs._opportunity_source_tasks() if name == "TP ICAP"]
    assert tasks == [(jobs._workday_jobs, ("TP ICAP", BOARD))]
    source = next(s for s in public_source_catalog() if s["name"] == "TP ICAP")
    assert source["category"] == "Courtage & trading"
    assert source["added_on"] == "2026-11-15"
    assert source["url"] == "https://tp.wd107.myworkdayjobs.com/en-US/TP-ICAP"
    logo = jobs.COMPANY_LOGO_DIR / (jobs.COMPANY_ICON_HOSTS[jobs._canonical_company("TP ICAP")] + ".png")
    assert 0 < logo.stat().st_size <= 512 * 1024
    with Image.open(logo) as image:
        assert image.format == "PNG"
        image.verify()


def test_realistic_sales_metadata_and_unfiltered_global_query(serve):
    calls = serve()
    found = collect()
    assert len(found) == 1
    job = found[0]
    assert (job.company, job.kind, job.family, job.location) == ("TP ICAP", "Stage", "Sales", "New York")
    assert job.published == "2026-11-13"
    assert job.start_period == "2027-06-01"
    assert job.deadline == ""
    assert "10-week" in job.description and "English required" in job.description
    assert "do not offer visa sponsorship" in job.description
    assert job.url.startswith("https://tp.wd107.myworkdayjobs.com/en-US/TP-ICAP/job/")
    assert calls[0][2] == {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}


@pytest.mark.parametrize("title", ["Trainee Broker, Forward FX", "Junior Broker, Rates Execution", "Broker Trainee"])
def test_junior_brokers_are_graduates_instead_of_internships(serve, title):
    serve(pages={0: {"total": 1, "jobPostings": [row(title=title)]}}, info=detail(title=title))
    job, = collect()
    assert (job.kind, job.family) == ("Graduate", "Sales")
    assert jobs._eligible_offer(job)
    # New source rules cannot reclassify other employers' trainees.
    assert jobs._kind(title) != "Graduate"


@pytest.mark.parametrize("title", [
    "Quantitative Research Intern", "Junior Software Developer", "Proprietary Trading Intern",
    "ETD Operations Internship", "Brokerage Accounts Receivable Internship", "Retail Sales Intern",
    "Corporate Sales Intern", "Senior Broker", "Trainee Broker - Italian Gas", "Trade Support Internship",
])
def test_no_technical_operations_retail_corporate_or_proprietary_fallback(serve, title):
    calls = serve(pages={0: {"total": 1, "jobPostings": [row(title=title)]}})
    assert collect() == []
    assert len(calls) == 1


@pytest.mark.parametrize("status", [403, 429, 500])
def test_api_failure_stops_without_retry_or_unverified_html_fallback(serve, status):
    calls = serve(status=status)
    with pytest.raises(requests.HTTPError):
        collect()
    assert len(calls) == 1 and calls[0][0] == "POST"


@pytest.mark.parametrize("payload", [{}, [], {"total": 0}, {"total": "1", "jobPostings": []},
    {"total": 1, "jobPostings": []}, {"total": 1, "jobPostings": [{}]},
    {"total": 1, "jobPostings": [None]}, ValueError("invalid JSON"), requests.Timeout("offline")])
def test_incomplete_or_failed_catalogue_cannot_claim_empty_success(serve, payload):
    calls = serve(pages={0: payload})
    with pytest.raises((ValueError, requests.RequestException)):
        collect()
    assert len(calls) == 1


def test_verified_empty_catalogue_is_success(serve):
    calls = serve(pages={0: {"total": 0, "jobPostings": []}})
    assert collect() == [] and len(calls) == 1


@pytest.mark.parametrize("info,status", [({}, 200), ([], 200), ({"jobPostingInfo": []}, 200),
    (detail(jobDescription=""), 200), (detail(canApply=None), 200), (detail(location=""), 200),
    (detail(), 403), (detail(), 429), (detail(), 500)])
def test_unverified_detail_reports_partial_instead_of_listing_only_offer(serve, info, status):
    calls = serve(info=info, detail_status=status)
    with pytest.raises(jobs._PartialSourceError) as failure:
        collect()
    assert not failure.value.jobs
    assert len(failure.value.failed_urls) == 1
    assert len(calls) == 2


@pytest.mark.parametrize("changes,status", [({"canApply": False}, 200), ({}, 404), ({}, 410),
    ({"validThrough": "2020-01-01"}, 200),
    ({"title": "Junior Broker", "jobDescription": "At least 5 years of experience required."}, 200)])
def test_closed_expired_and_experienced_jobs_are_excluded(serve, changes, status):
    serve(info=detail(**changes), detail_status=status)
    assert collect() == []


def test_unknown_dates_stay_unknown_instead_of_using_graduation_or_detection(serve):
    serve(info=detail(startDate="", postedOn="Posted 30+ Days Ago",
        jobDescription="Institutional Sales. Graduation June 2028. Ten weeks. English required."))
    job, = collect()
    assert (job.published, job.start_period, job.deadline) == ("", "", "")


def test_explicit_employer_expiry_is_kept(serve):
    serve(info=detail(validThrough="2099-01-01T00:00:00Z"))
    assert collect()[0].deadline == "2099-01-01"


def test_pagination_keeps_initial_total_and_loads_duplicate_details_once(serve):
    first = [row()] + [row(str(i), "Accountant") for i in range(19)]
    calls = serve(pages={0: {"total": 21, "jobPostings": first},
                         20: {"total": 0, "jobPostings": [row()]}})
    found = collect()
    assert len(found) == len(jobs._deduplicate_opportunities(found)) == 1
    assert [c[2]["offset"] for c in calls if c[0] == "POST"] == [0, 20]
    assert sum(c[0] == "GET" for c in calls) == 1


@pytest.mark.parametrize("second", [requests.HTTPError("429"), {"total": 40, "jobPostings": []}, "repeat"])
def test_failed_or_repeating_later_page_keeps_verified_results_as_partial(serve, second):
    first = [row()] + [row(str(i), "Accountant") for i in range(19)]
    if second == "repeat":
        second = {"total": 40, "jobPostings": first}
    serve(pages={0: {"total": 40, "jobPostings": first}, 20: second})
    with pytest.raises(jobs._PartialSourceError) as failure:
        collect()
    assert len(failure.value.jobs) == 1


@pytest.mark.skipif(os.environ.get("INTERNSHIPS_TP_ICAP_LIVE") != "1", reason="Public employer audit is opt-in")
def test_live_collection_and_published_catalogue_comparison(monkeypatch):
    monkeypatch.setattr(jobs, "_cached_detail", lambda job: None)
    began = perf_counter()
    found = collect()
    assert any("Sales" in job.title for job in found)
    assert len(found) == len(jobs._deduplicate_opportunities(found))
    assert all(jobs._eligible_offer(job) for job in found)
    print(f"TP ICAP: {len(found)} offers, {perf_counter()-began:.3f}s, no duplicates")
    for job in found:
        print(f"{job.title} | {job.location} | {job.kind} | {job.family} | publication={job.published} | "
              f"start={job.start_period} | expiry={job.deadline} | {job.url}")
    documents = {}
    for name in ("sources", "offers"):
        response = requests.get(f"https://caruanatheo-beep.github.io/Internships-Offres/{name}.json", timeout=20)
        response.raise_for_status()
        documents[name] = response.json()
    public = {source["name"] for source in documents["sources"]["sources"]}
    local = {source["name"] for source in public_source_catalog()}
    offers = documents["offers"]["offers"]
    print(f"Public updated={documents['sources']['updated']}; {len(public)} sources; {len(offers)} offers")
    print(f"Local only={sorted(local-public)}; public only={sorted(public-local)}")
    print(f"Families={dict(Counter(job['family'] for job in offers))}")
    print(f"Contracts={dict(Counter(job['kind'] for job in offers))}")
    print(f"Locations={Counter(job['location'] for job in offers).most_common(7)}")
    print(f"Duplicate URLs={len(offers)-len({job['url'] for job in offers})}; "
          f"ambiguous title/company/location/contract groups="
          f"{sum(n > 1 for n in Counter((j['title'], j['company'], j['location'], j['kind']) for j in offers).values())}")
