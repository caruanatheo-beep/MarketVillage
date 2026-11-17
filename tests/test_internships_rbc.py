"""RBC public campus board: audit, scope and limitations in SOURCES_RBC.md."""
import json
import os
from dataclasses import replace
from time import perf_counter

import pytest
import requests
from PIL import Image

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog
from internships_project.source_coverage import SOURCE_COVERAGE
from tests.test_internships_tp_icap import serve, row, detail


COMPANY = "RBC Capital Markets"
BOARD = ("rbc.wd3.myworkdayjobs.com", "rbc", "RBCEARLYTALENT1")
TITLE = "2028 Capital Markets, Global Markets Sales & Trading Summer Analyst"
TEXT = ("Global Markets Summer Program. Institutional clients, Fixed Income and Currencies & Commodities. "
        "10 weeks internship. English required. No visa sponsorship. "
        "Posted Date: 2026-11-02. Application Deadline: 2027-01-01. "
        "Applications will be accepted until 11:59 PM on the day prior to the application deadline date above.")


def info(**changes):
    return detail(**{"title": TITLE, "location": "New York, New York, United States of America",
        "startDate": "2026-11-10", "endDate": "2027-01-01", "jobDescription": TEXT, **changes})


def setup(serve, **changes):
    values = {"pages": {0: {"total": 1, "jobPostings": [row("R-0000191757-1", TITLE)]}},
              "info": info()}
    values.update(changes)
    return serve(**values)


def collect():
    return jobs._workday_jobs(COMPANY, BOARD)


def test_source_is_registered_once_with_card_category_date_and_official_png():
    assert jobs.WORKDAY[COMPANY] == BOARD
    assert [(fn, args) for name, fn, args in jobs._opportunity_source_tasks() if name == COMPANY] == [
        (jobs._workday_jobs, (COMPANY, BOARD))]
    source, = [source for source in public_source_catalog() if source["name"] == COMPANY]
    assert source["category"] == "Banques & services titres"
    assert source["url"] == f"https://{BOARD[0]}/en-US/{BOARD[2]}"
    assert source["added_on"] == "2026-11-17"
    assert SOURCE_COVERAGE[COMPANY].status == "connected"
    path = jobs.COMPANY_LOGO_DIR / (jobs.COMPANY_ICON_HOSTS["rbccapitalmarkets"] + ".png")
    assert 0 < path.stat().st_size <= 512 * 1024
    with Image.open(path) as logo:
        assert logo.format == "PNG"
        logo.verify()
    assert jobs._company_icon(COMPANY).startswith("data:image/png;base64,")


def test_unfiltered_global_collection_uses_original_date_actual_closure_and_season(serve):
    calls = setup(serve)
    job, = collect()
    assert (job.company, job.kind, job.family) == (COMPANY, "Stage", "Sales")
    assert job.location == "New York, New York, United States of America"
    assert (job.published, job.deadline, job.start_period) == ("2026-11-02", "2026-12-31", "Summer 2028")
    assert "10 weeks" in job.description and "English required" in job.description
    assert "No visa sponsorship" in job.description
    assert jobs.is_trusted_offer_url(job.url) and jobs._eligible_offer(job)
    assert calls[0][2] == {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}


def test_debt_origination_is_distinct_from_sales(serve):
    title = "2028 Capital Markets, Global Markets Origination Summer Analyst"
    setup(serve, pages={0: {"total": 1, "jobPostings": [row(title=title)]}},
          info=info(title=title, jobDescription=TEXT + " Fixed Income Origination; debt transactions."))
    job, = collect()
    assert job.family == "Capital Markets" and job.kind == "Stage"


@pytest.mark.parametrize("title,kind", [("Rates Sales Intern", "Stage"), ("FX Trading VIE", "VIE"),
    ("Global Markets Sales Graduate", "Graduate"), ("Junior Credit Sales Analyst", "Graduate"),
    ("Repo Sales Off-cycle Analyst", "Stage"), ("Treasury Solutions Summer Analyst", "Stage")])
def test_role_and_contract_synonyms(serve, title, kind):
    setup(serve, pages={0: {"total": 1, "jobPostings": [row(title=title)]}}, info=info(title=title))
    job, = collect()
    assert job.kind == kind and jobs._eligible_offer(job)


@pytest.mark.parametrize("title", ["2028 Global Markets Summer Associate, Equity Research",
    "2028 Capital Markets, Global Investment Banking Summer Analyst", "Quant Trading Intern",
    "Software Engineer Intern", "Finance Intern, US Regulatory Reporting and Financial Control",
    "2027 Global Markets Summer Analyst, Securitization Financing Portfolio Management",
    "Retail Sales Intern", "Corporate Sales Intern", "Senior Rates Sales Analyst",
    "Rates Trading Analyst", "Account Manager Apprentice (24-Month Apprenticeship)"])
def test_no_research_technical_operations_retail_or_unproven_contract_fallback(serve, title):
    calls = setup(serve, pages={0: {"total": 1, "jobPostings": [row(title=title)]}})
    assert collect() == [] and len(calls) == 1


@pytest.mark.parametrize("text", ["Administrative reporting duties.",
    TEXT + " Minimum 5 years of experience required."])
def test_live_detail_and_saved_snapshot_require_target_role_evidence(serve, text):
    setup(serve, info=info(jobDescription=text))
    assert collect() == []
    setup(serve)
    job, = collect()
    assert not jobs._eligible_offer(replace(job, description=text))


@pytest.mark.parametrize("status", [403, 429, 500])
def test_api_failure_or_refusal_stops_without_retry_or_html_fallback(serve, status):
    calls = setup(serve, status=status)
    with pytest.raises(requests.HTTPError):
        collect()
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [{}, [], {"total": 0}, {"total": "1", "jobPostings": []},
    {"total": 1, "jobPostings": []}, {"total": 1, "jobPostings": [{}]},
    {"total": 1, "jobPostings": [None]}, ValueError("invalid JSON"), requests.Timeout("offline")])
def test_invalid_incomplete_or_failed_feed_is_not_an_empty_success(serve, payload):
    calls = setup(serve, pages={0: payload})
    with pytest.raises((ValueError, requests.RequestException)):
        collect()
    assert len(calls) == 1


def test_confirmed_empty_feed(serve):
    calls = setup(serve, pages={0: {"total": 0, "jobPostings": []}})
    assert collect() == [] and len(calls) == 1


@pytest.mark.parametrize("payload,status", [({}, 200), ({"jobPostingInfo": None}, 200),
    (info(canApply=None), 200), (info(jobDescription=""), 200), (info(location=""), 200),
    (info(title=""), 200), (info(), 403), (info(), 429), (info(), 500)])
def test_unverified_detail_reports_partial_without_listing_only_offer(serve, payload, status):
    calls = setup(serve, info=payload, detail_status=status)
    with pytest.raises(jobs._PartialSourceError) as failure:
        collect()
    assert failure.value.jobs == [] and len(failure.value.failed_urls) == 1
    assert len(calls) == 2


@pytest.mark.parametrize("changes,status", [({"canApply": False}, 200), ({}, 404), ({}, 410),
    ({"jobDescription": TEXT.replace("2027-01-01", "2020-01-01")}, 200),
    ({"title": "Senior Rates Sales Analyst"}, 200)])
def test_closed_expired_or_changed_roles_are_removed(serve, changes, status):
    setup(serve, info=info(**changes), detail_status=status)
    assert collect() == []


def test_unknown_dates_languages_visa_and_multiple_locations_are_not_invented(serve):
    setup(serve, info=info(startDate="", postedOn="Posted 30+ Days Ago", endDate="",
        jobDescription="Institutional clients and Fixed Income; 10 weeks internship.",
        additionalLocations=["Toronto, Canada", "New York, New York, United States of America"]))
    job, = collect()
    assert job.published == job.deadline == ""
    assert job.start_period == "Summer 2028"
    assert job.location.endswith("; Toronto, Canada")
    assert "visa" not in job.description.lower() and "English" not in job.description


def test_end_date_fallback_is_closure_not_programme_end(serve):
    setup(serve, info=info(jobDescription="Fixed Income; 10 weeks internship.", endDate="2099-01-01"))
    job, = collect()
    assert job.deadline == "2099-01-01" and job.start_period == "Summer 2028"
    assert jobs._rbc_posting_dates({"endDate": "invalid"}, "Fixed Income") == ("", "")


def test_pagination_preserves_initial_total_and_deduplicates_repeated_paths(serve):
    first = [row("R-0000191757-1", TITLE)] + [row(str(i), "Accountant") for i in range(19)]
    calls = setup(serve, pages={0: {"total": 21, "jobPostings": first},
        20: {"total": 0, "jobPostings": [row("R-0000191757-1", TITLE)]}})
    found = collect()
    assert len(found) == len(jobs._deduplicate_opportunities(found)) == 1
    assert [c[2]["offset"] for c in calls if c[0] == "POST"] == [0, 20]
    assert sum(c[0] == "GET" for c in calls) == 1


@pytest.mark.parametrize("second", [requests.HTTPError("429"), {"total": 40, "jobPostings": []}, "repeat"])
def test_failed_later_page_keeps_verified_results_as_partial(serve, second):
    first = [row("R-0000191757", TITLE)] + [row(str(i), "Accountant") for i in range(19)]
    if second == "repeat":
        second = {"total": 40, "jobPostings": first}
    setup(serve, pages={0: {"total": 40, "jobPostings": first}, 20: second})
    with pytest.raises(jobs._PartialSourceError) as failure:
        collect()
    assert len(failure.value.jobs) == 1


def test_all_details_verified_and_different_requisitions_survive_deduplication(serve):
    pages = {offset: {"total": 51, "jobPostings": [row("R-" + str(i + 1), TITLE)
        for i in range(offset, min(offset + 20, 51))]} for offset in (0, 20, 40)}
    calls = setup(serve, pages=pages)
    found = collect()
    assert len(found) == len(jobs._deduplicate_opportunities(found + found)) == 51
    assert sum(c[0] == "GET" for c in calls) == 51
    first = found[0]
    repost = replace(first, url=first.url + "-1")
    assert len(jobs._deduplicate_opportunities([first, repost])) == 1


@pytest.mark.skipif(os.environ.get("INTERNSHIPS_RBC_LIVE") != "1", reason="Public live audit is opt-in")
def test_live_collection(monkeypatch):
    monkeypatch.setattr(jobs, "_cached_detail", lambda job: pytest.fail("live details required"))
    started = perf_counter()
    found = collect()
    assert len(found) == len(jobs._deduplicate_opportunities(found)) == 2
    assert {job.family for job in found} == {"Sales", "Capital Markets"}
    assert all(job.company == COMPANY and jobs._eligible_offer(job) and job.description
               and job.published == "2026-11-02" and job.deadline == "2026-12-31" for job in found)
    print(f"RBC: {len(found)} verified offers, {perf_counter() - started:.3f}s, no duplicates")
    for job in found:
        print(json.dumps({"title": job.title, "url": job.url, "location": job.location,
            "published": job.published, "deadline": job.deadline, "start": job.start_period,
            "family": job.family}, ensure_ascii=True))
