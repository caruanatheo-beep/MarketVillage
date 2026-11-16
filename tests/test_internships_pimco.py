"""PIMCO extends Workday; public evidence and limits: SOURCES_PIMCO.md."""
import os
import json
from time import perf_counter
from collections import Counter

import pytest
import requests
from PIL import Image

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog
from internships_project.source_coverage import SOURCE_COVERAGE
from tests.test_internships_tp_icap import serve, row, detail


COMPANY = "PIMCO"
BOARD = ("pimco.wd1.myworkdayjobs.com", "pimco", "pimco-careers")
TITLE = "2027 Summer Intern - Account Analyst, London"
TEXT = ("Support client relationships and client service, evaluate portfolio structures "
        "and attribution analyses. Financial markets and investment strategies. "
        "A 10-week internship from early June to mid-August. Fluent in English; "
        "French advantageous. Visa sponsorship is not specified. "
        "Graduation December 2027 to June 2028. Available to begin full time "
        "employment between January 2028 and August 2028.")


def info(**changes):
    return detail(**{"title": TITLE, "location": "London, GBR",
                     "startDate": "2026-10-28", "jobDescription": TEXT, **changes})


def setup(serve, **changes):
    values = {"pages": {0: {"total": 1, "jobPostings": [row(title=TITLE)]}}, "info": info()}
    values.update(changes)
    return serve(**values)


def collect():
    return jobs._workday_jobs(COMPANY, BOARD)


def test_registered_once_with_asset_management_card_date_and_official_png():
    assert jobs.WORKDAY[COMPANY] == BOARD
    assert [(fn, args) for name, fn, args in jobs._opportunity_source_tasks() if name == COMPANY] == [
        (jobs._workday_jobs, (COMPANY, BOARD))]
    source, = [source for source in public_source_catalog() if source["name"] == COMPANY]
    assert source["category"] == "Gestion d’actifs"
    assert source["url"] == f"https://{BOARD[0]}/en-US/{BOARD[2]}"
    assert source["added_on"] == "2026-11-16"
    assert SOURCE_COVERAGE[COMPANY].status == "connected"
    path = jobs.COMPANY_LOGO_DIR / (jobs.COMPANY_ICON_HOSTS["pimco"] + ".png")
    assert 0 < path.stat().st_size <= 512 * 1024
    with Image.open(path) as logo:
        assert logo.format == "PNG" and max(logo.size) <= 96
        logo.verify()


def test_client_service_is_distinct_from_markets_sales_and_preserves_employer_metadata(serve):
    calls = setup(serve)
    job, = collect()
    assert (job.company, job.kind, job.location, job.family) == (
        COMPANY, "Stage", "London, GBR", "Client Service / Financial Solutions")
    assert job.published == "2026-10-28" and job.deadline == ""
    assert "2028" not in job.start_period  # A subsequent permanent job is not the internship.
    assert all(text in job.description for text in ("10-week", "Fluent in English", "French", "Visa"))
    assert jobs.is_trusted_offer_url(job.url) and jobs._eligible_offer(job)
    assert calls[0][2] == {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}


@pytest.mark.parametrize("title,family", [
    ("2027 MBA Summer Intern - Account Manager, Munich (German Speaking)", "Client Service / Financial Solutions"),
    ("2027 Summer Internship - PSG Product Analyst, APAC", "Asset Management"),
    ("Graduate Fixed Income Product Specialist", "Asset Management"),
    ("Junior Institutional Sales Analyst", "Sales"),
    ("2027 Summer Intern - Trading Analyst, US", "Trading / Structuring"),
])
def test_role_and_contract_synonyms_are_verified_from_details(serve, title, family):
    setup(serve, pages={0: {"total": 1, "jobPostings": [row(title=title)]}}, info=info(title=title))
    job, = collect()
    assert job.family == family and jobs._eligible_offer(job)
    if "Account" in title:
        assert jobs._opportunity(title, "Other employer", "London", "", job.url, "") is None


@pytest.mark.parametrize("title", ["2027 Summer Intern - Global Wealth Management, Internal Sales Analyst",
    "2027 Summer Intern - Alternatives Investment Operations Intern", "2027 Summer Intern - Trade Floor Operations Analyst",
    "2027 Summer Intern - Trade Support Analyst", "2027 Summer Intern - Private Strategies Analyst",
    "2027 Summer Intern - Technology Analyst, Software Engineering", "Retail Sales Intern", "Corporate Sales Intern",
    "Senior Account Manager", "Account Analyst", "Fund Accounting Intern", "Account Analyst Fund Accounting Intern"])
def test_non_target_roles_and_unproven_junior_contracts_are_excluded(serve, title):
    calls = setup(serve, pages={0: {"total": 1, "jobPostings": [row(title=title)]}})
    assert collect() == [] and len(calls) == 1


def test_generic_account_title_requires_own_client_and_investment_evidence(serve):
    setup(serve, info=info(jobDescription="PIMCO is a global leader in fixed income. Administrative duties."))
    assert collect() == []


@pytest.mark.parametrize("status", [403, 429, 500])
def test_api_failure_stops_without_retry_or_html_fallback(serve, status):
    calls = setup(serve, status=status)
    with pytest.raises(requests.HTTPError):
        collect()
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [{}, [], {"total": 0}, {"total": "1", "jobPostings": []},
    {"total": 1, "jobPostings": []}, {"total": 1, "jobPostings": [{}]},
    {"total": 1, "jobPostings": [None]}, ValueError("invalid JSON"), requests.Timeout("offline")])
def test_invalid_catalogue_does_not_report_empty_success(serve, payload):
    calls = setup(serve, pages={0: payload})
    with pytest.raises((ValueError, requests.RequestException)):
        collect()
    assert len(calls) == 1


def test_confirmed_empty_catalogue(serve):
    calls = setup(serve, pages={0: {"total": 0, "jobPostings": []}})
    assert collect() == [] and len(calls) == 1


@pytest.mark.parametrize("payload,status", [({}, 200), ([], 200), ({"jobPostingInfo": []}, 200),
    (info(jobDescription=""), 200), (info(canApply=None), 200), (info(location=""), 200),
    (info(title=""), 200), (info(), 403), (info(), 429), (info(), 500)])
def test_failed_details_are_partial_without_listing_only_offers(serve, payload, status):
    calls = setup(serve, info=payload, detail_status=status)
    with pytest.raises(jobs._PartialSourceError) as failure:
        collect()
    assert not failure.value.jobs and len(failure.value.failed_urls) == 1 and len(calls) == 2


@pytest.mark.parametrize("changes,status", [({"canApply": False}, 200), ({}, 404), ({}, 410),
    ({"validThrough": "2020-01-01"}, 200), ({"title": "Senior Account Manager"}, 200)])
def test_closed_expired_and_changed_offers_are_removed(serve, changes, status):
    setup(serve, info=info(**changes), detail_status=status)
    assert collect() == []


def test_only_explicit_dates_and_locations_are_preserved(serve):
    setup(serve, info=info(startDate="", postedOn="Posted 30+ Days Ago", validThrough="2099-01-01",
        additionalLocations=["New York, NY USA", "Austin, TX USA", "New York, NY USA"],
        jobDescription=TEXT + " Start date: June 2027."))
    job, = collect()
    assert job.published == "" and job.deadline == "2099-01-01"
    assert job.start_period == "June 2027"
    assert job.location == "London, GBR; New York, NY USA; Austin, TX USA"


def test_pagination_preserves_first_total_and_deduplicates_details(serve):
    first = [row(title=TITLE)] + [row(str(i), "Accountant") for i in range(19)]
    calls = setup(serve, pages={0: {"total": 21, "jobPostings": first},
                               20: {"total": 0, "jobPostings": [row(title=TITLE)]}})
    found = collect()
    assert len(found) == len(jobs._deduplicate_opportunities(found)) == 1
    assert [c[2]["offset"] for c in calls if c[0] == "POST"] == [0, 20]
    assert sum(c[0] == "GET" for c in calls) == 1


@pytest.mark.parametrize("second", [requests.HTTPError("429"), {"total": 40, "jobPostings": []}, "repeat"])
def test_failed_later_page_preserves_verified_results_as_partial(serve, second):
    first = [row(title=TITLE)] + [row(str(i), "Accountant") for i in range(19)]
    if second == "repeat":
        second = {"total": 40, "jobPostings": first}
    setup(serve, pages={0: {"total": 40, "jobPostings": first}, 20: second})
    with pytest.raises(jobs._PartialSourceError) as failure:
        collect()
    assert len(failure.value.jobs) == 1


def test_every_candidate_is_verified_beyond_enrichment_limit(serve):
    pages = {offset: {"total": 51, "jobPostings": [row(str(i), TITLE)
        for i in range(offset, min(offset + 20, 51))]} for offset in (0, 20, 40)}
    calls = setup(serve, pages=pages)
    assert len(collect()) == sum(c[0] == "GET" for c in calls) == 51


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("INTERNSHIPS_PIMCO_LIVE") != "1", reason="Public live audit is opt-in")
def test_live_collection(monkeypatch):
    # Public HTTP only. No persistence, profile, cache or private data.
    monkeypatch.setattr(jobs, "_cached_detail", lambda job: pytest.fail("live details required"))
    started = perf_counter()
    found = collect()
    assert any("Account Analyst" in job.title for job in found)
    assert any("PSG Product Analyst" in job.title for job in found)
    assert all(job.company == COMPANY and job.description and jobs.is_trusted_offer_url(job.url)
               and jobs._eligible_offer(job) for job in found)
    assert len(found) == len(jobs._deduplicate_opportunities(found))
    print(f"PIMCO: {len(found)} verified offers, {perf_counter() - started:.3f}s, no duplicates")
    for job in found:
        print(json.dumps({"title": job.title, "location": job.location, "family": job.family,
                          "published": job.published, "start": job.start_period}, ensure_ascii=True))


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("INTERNSHIPS_PIMCO_LIVE") != "1", reason="Public live audit is opt-in")
def test_live_public_inventory_comparison():
    base = "https://caruanatheo-beep.github.io/Internships-Offres/"
    response = requests.get(base + "sources.json", timeout=(8, 20))
    response.raise_for_status()
    sources = response.json()["sources"]
    response = requests.get(base + "offers.json", timeout=(8, 20))
    response.raise_for_status()
    offers = response.json()["offers"]
    local = {source["name"] for source in public_source_catalog()}
    published = {source["name"] for source in sources}
    assert "Bloomberg" in published and "PIMCO" in local
    assert all(jobs.is_trusted_offer_url(offer["url"]) or
               offer["url"].startswith("https://www.jobteaser.com/") for offer in offers)
    urls = Counter(offer["url"] for offer in offers)
    identities = Counter((offer["company"], offer["title"], offer["location"]) for offer in offers)
    print(json.dumps({"public_sources": len(sources), "local_sources": len(local),
        "local_only": sorted(local - published), "published_only": sorted(published - local),
        "offers": len(offers), "duplicate_urls": sum(count - 1 for count in urls.values() if count > 1),
        "duplicate_title_company_location_groups": sum(count > 1 for count in identities.values()),
        "registries": {name: len(getattr(jobs, name)) for name in (
            "GREENHOUSE", "LEVER", "ASHBY", "WORKDAY", "SMARTRECRUITERS", "ORACLE_CAREER_BOARDS", "CAREER_LISTINGS")}},
        ensure_ascii=True))
