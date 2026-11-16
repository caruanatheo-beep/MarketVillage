"""Murex extends Workday; public evidence and scope: SOURCES_MUREX.md."""
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


COMPANY = "Murex"
BOARD = ("murex.wd3.myworkdayjobs.com", "murex", "MurexCareerPage1")
TITLE = "Trading Domain Functional Intern"
TEXT = ("Support client-facing initiatives and client support activities for financial institutions. "
        "Work with Foreign Exchange and Fixed Income financial instruments, derivatives, swaps and bonds. "
        "Full-time 6-month internship. Proficient in advanced English. Start date: January 2027.")


def info(**changes):
    return detail(**{"title": TITLE, "location": "Toronto", "startDate": "2026-09-24",
                     "jobDescription": TEXT, **changes})


def setup(serve, **changes):
    values = {"pages": {0: {"total": 1, "jobPostings": [row("JR103273", TITLE)]}}, "info": info()}
    values.update(changes)
    return serve(**values)


def collect():
    return jobs._workday_jobs(COMPANY, BOARD)


def test_registry_source_card_category_date_and_official_png():
    assert jobs.WORKDAY[COMPANY] == BOARD
    assert [(fn, args) for name, fn, args in jobs._opportunity_source_tasks() if name == COMPANY] == [
        (jobs._workday_jobs, (COMPANY, BOARD))]
    source, = [s for s in public_source_catalog() if s["name"] == COMPANY]
    assert source == {"name": COMPANY, "category": "Information financière & relation clients",
        "url": f"https://{BOARD[0]}/en-US/{BOARD[2]}", "added_on": "2026-11-16",
        "feeds": [{"name": COMPANY, "url": f"https://{BOARD[0]}/en-US/{BOARD[2]}"}]}
    assert SOURCE_COVERAGE[COMPANY].status == "connected"
    path = jobs.COMPANY_LOGO_DIR / (jobs.COMPANY_ICON_HOSTS["murex"] + ".png")
    assert 0 < path.stat().st_size <= 512 * 1024
    with Image.open(path) as logo:
        assert logo.format == "PNG" and max(logo.size) <= 96
        logo.verify()
    assert jobs._company_icon(COMPANY).startswith("data:image/png;base64,")


def test_client_solutions_are_separate_from_markets_trading_and_keep_metadata(serve):
    calls = setup(serve)
    job, = collect()
    assert (job.company, job.kind, job.location, job.family) == (
        COMPANY, "Stage", "Toronto", "Client Service / Financial Solutions")
    assert (job.published, job.start_period, job.deadline) == ("2026-09-24", "January 2027", "")
    assert "6-month" in job.description and "English" in job.description
    assert "visa" not in job.description.casefold()  # No inferred sponsorship.
    assert jobs.is_trusted_offer_url(job.url) and jobs._eligible_offer(job)
    assert calls[0][2] == {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}


@pytest.mark.parametrize("title,kind", [("Trading Consultant Intern", "Stage"),
    (TITLE, "Stage"), ("Graduate Client Solutions", "Graduate"),
    ("VIE Fixed Income Client Solutions", "VIE"), ("Junior FX Analyst", "Graduate")])
def test_contract_and_role_synonyms_require_live_client_markets_evidence(serve, title, kind):
    setup(serve, pages={0: {"total": 1, "jobPostings": [row("JR1", title)]}}, info=info(title=title))
    job, = collect()
    assert (job.kind, job.family) == (kind, "Client Service / Financial Solutions")
    assert jobs._eligible_offer(job)


@pytest.mark.parametrize("title", ["Finance Intern", "Trading Senior Consultant", "Trading Consultant",
    "Test Engineering Intern", "INTERNSHIP 2027 - Software Engineer Java", "Operations Internship",
    "Undergraduate Internship Program 2027", "Trading Operations Intern", "Corporate FX Sales Intern",
    "Retail Sales Intern", "Graduate Risk Analyst", "Senior Client Solutions Intern"])
def test_no_generalist_technical_operations_senior_or_unproven_contract_fallback(serve, title):
    calls = setup(serve, pages={0: {"total": 1, "jobPostings": [row(title=title)]}})
    assert collect() == [] and len(calls) == 1


@pytest.mark.parametrize("text", ["Murex builds trading software. Administrative duties.",
    "Client support for payroll software.", "Financial instruments research only.",
    TEXT + " Minimum 5 years of experience required."])
def test_description_and_saved_snapshots_must_confirm_target_work(serve, text):
    setup(serve, info=info(jobDescription=text))
    assert collect() == []
    setup(serve)
    job, = collect()
    assert not jobs._eligible_offer(replace(job, description=text))


@pytest.mark.parametrize("status", [403, 429, 500])
def test_api_refusal_or_failure_stops_without_retry_or_html_fallback(serve, status):
    calls = setup(serve, status=status)
    with pytest.raises(requests.HTTPError):
        collect()
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [{}, [], {"total": 0}, {"total": "1", "jobPostings": []},
    {"total": 1, "jobPostings": []}, {"total": 1, "jobPostings": [{}]},
    {"total": 1, "jobPostings": [None]}, ValueError("invalid JSON"), requests.Timeout("offline")])
def test_invalid_or_incomplete_feed_is_not_an_empty_success(serve, payload):
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
def test_detail_failure_reports_partial_without_publishing_listing_only_offer(serve, payload, status):
    calls = setup(serve, info=payload, detail_status=status)
    with pytest.raises(jobs._PartialSourceError) as failure:
        collect()
    assert failure.value.jobs == [] and len(failure.value.failed_urls) == 1
    assert len(calls) == 2


@pytest.mark.parametrize("changes,status", [({"canApply": False}, 200), ({}, 404), ({}, 410),
    ({"validThrough": "2020-01-01"}, 200), ({"title": "Trading Senior Consultant"}, 200)])
def test_closed_expired_or_changed_offers_are_removed(serve, changes, status):
    setup(serve, info=info(**changes), detail_status=status)
    assert collect() == []


def test_unknown_publication_program_dates_and_explicit_locations(serve):
    setup(serve, info=info(startDate="", postedOn="Posted 30+ Days Ago", validThrough="2099-01-01",
        additionalLocations=["Santiago", "Toronto", "Santiago"]))
    job, = collect()
    assert job.published == "" and job.deadline == "2099-01-01"
    assert job.start_period == "January 2027" and job.location == "Toronto; Santiago"


def test_pagination_keeps_initial_total_and_deduplicates_repeated_requisitions(serve):
    first = [row("JR103273", TITLE)] + [row(str(i), "Accountant") for i in range(19)]
    calls = setup(serve, pages={0: {"total": 21, "jobPostings": first},
                               20: {"total": 0, "jobPostings": [row("JR103273", TITLE)]}})
    found = collect()
    assert len(found) == len(jobs._deduplicate_opportunities(found)) == 1
    assert [c[2]["offset"] for c in calls if c[0] == "POST"] == [0, 20]
    assert sum(c[0] == "GET" for c in calls) == 1


@pytest.mark.parametrize("second", [requests.HTTPError("429"), {"total": 40, "jobPostings": []}, "repeat"])
def test_failed_later_page_retains_verified_results_as_partial(serve, second):
    first = [row("JR103273", TITLE)] + [row(str(i), "Accountant") for i in range(19)]
    if second == "repeat":
        second = {"total": 40, "jobPostings": first}
    setup(serve, pages={0: {"total": 40, "jobPostings": first}, 20: second})
    with pytest.raises(jobs._PartialSourceError) as failure:
        collect()
    assert len(failure.value.jobs) == 1


def test_distinct_requisitions_survive_global_deduplication_and_all_are_verified(serve):
    pages = {offset: {"total": 51, "jobPostings": [row("JR" + str(i + 1), TITLE)
        for i in range(offset, min(offset + 20, 51))]} for offset in (0, 20, 40)}
    calls = setup(serve, pages=pages)
    found = collect()
    assert len(found) == len(jobs._deduplicate_opportunities(found + found)) == 51
    assert sum(c[0] == "GET" for c in calls) == 51


@pytest.mark.skipif(os.environ.get("INTERNSHIPS_MUREX_LIVE") != "1", reason="Public live audit is opt-in")
def test_live_collection(monkeypatch):
    monkeypatch.setattr(jobs, "_cached_detail", lambda job: pytest.fail("live details required"))
    started = perf_counter()
    found = collect()
    assert {TITLE, "Trading Consultant Intern"} <= {job.title for job in found}
    assert len(found) == len(jobs._deduplicate_opportunities(found))
    assert all(job.company == COMPANY and job.description and jobs._eligible_offer(job)
               and job.family == "Client Service / Financial Solutions" for job in found)
    print(f"Murex: {len(found)} verified offers, {perf_counter() - started:.3f}s, no duplicates")
    for job in found:
        print(json.dumps({"title": job.title, "url": job.url, "location": job.location,
            "published": job.published, "start": job.start_period, "family": job.family}, ensure_ascii=True))
