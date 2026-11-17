"""Nomura extends CAREER_LISTINGS; public evidence is in SOURCES_NOMURA.md."""
import json
import os
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

import pytest
import requests
from PIL import Image

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog
from internships_project.source_coverage import SOURCE_COVERAGE


COMPANY = "Nomura"
CONFIG = jobs.CAREER_LISTINGS[COMPANY]
TITLE = "2027 - Global Markets - Structured Solution Sales - Off Cycle Internship - Paris"
URL = f"https://{CONFIG[1]}{CONFIG[2]}1518-Structured-Solution-Sales/en-GB"
TEXT = ("Join the Structured Solutions Sales team in Paris on a 6-month contract. "
        "Work on fixed income, interest rates and credit derivatives for institutional clients. "
        "Start date: January 2027. Fluent English and French required. No visa sponsorship.")


def listing(total=1, links=None):
    links = [(URL, TITLE), (URL, TITLE)] if links is None else links
    return f'<h2>{total} results match!</h2>' + ''.join(
        f'<a href="{url}">{title}</a>' for url, title in links)


def detail(title=TITLE, description=TEXT, location="Paris", programme="Off-cycle internship",
           expiry="01/12/2026", apply=True):
    fields = {"Region": "EMEA", "Division": "Global Markets", "Location": location,
              "Program type": programme, "Level": "Analyst", "Job description": description}
    body = ''.join(f'<span class="hform_lbl_text">{key}</span><div>{value}</div>'
                   for key, value in fields.items())
    application = (f'<form action="https://{CONFIG[1]}{CONFIG[2]}1518/apply/en-GB">'
                   '<input value="Apply"></form>') if apply else ""
    return (f'<head><meta content="Application Deadline: {expiry}, 23:55"></head>'
            f'<h1>{title}</h1><form class="form-view form-horizontal">{body}</form>'
            + application + '<aside><h2>Institutional Sales Intern - Tokyo</h2>'
            '<p>Start date: February 2028. Location London. Graduate.</p></aside>')


class Response:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status
        self.headers = {"Retry-After": "120"} if status == 429 else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code), response=self)


@pytest.fixture
def serve(monkeypatch):
    calls = []

    def setup(board=None, offer=None, status=200, detail_status=200):
        def get(url, **kwargs):
            calls.append(url)
            if url == CONFIG[0]:
                if isinstance(board, Exception):
                    raise board
                return Response(listing() if board is None else board, status)
            return Response(detail() if offer is None else offer, detail_status)
        monkeypatch.setattr(jobs.requests, "get", get)
        monkeypatch.setattr(jobs.requests, "post", lambda *a, **k: pytest.fail("No API fallback"))
        monkeypatch.setattr(jobs, "_render_public_career_page", lambda *a, **k: pytest.fail("No browser fallback"))
        monkeypatch.setattr(jobs.time, "sleep", lambda *a: pytest.fail("No immediate retry"))
        return calls
    return setup


def collect():
    return jobs._career_page_jobs(COMPANY, CONFIG)


def test_source_card_category_pending_publication_and_verified_official_logo():
    assert [(fn, args) for name, fn, args in jobs._opportunity_source_tasks() if name == COMPANY] == [
        (jobs._career_page_jobs, (COMPANY, CONFIG))]
    source, = [s for s in public_source_catalog() if s["name"] == COMPANY]
    assert source["category"] == "Banques & services titres"
    assert source["url"] == CONFIG[0] and len(source["feeds"]) == 1
    assert source["added_on"] == ""  # Actual publication belongs to the controller.
    assert SOURCE_COVERAGE[COMPANY].status == "connected"
    path = jobs.COMPANY_LOGO_DIR / (jobs.COMPANY_ICON_HOSTS["nomura"] + ".png")
    assert 0 < path.stat().st_size <= 512 * 1024
    with Image.open(path) as logo:
        assert logo.format == "PNG" and max(logo.size) <= 96
        logo.verify()


def test_live_fields_dates_language_visa_duration_and_duplicate_tiles(serve):
    calls = serve()
    job, = collect()
    assert (job.company, job.kind, job.family, job.location) == (COMPANY, "Stage", "Sales", "Paris")
    assert (job.published, job.start_period, job.deadline) == ("", "January 2027", "2026-12-01")
    assert job.description == TEXT and jobs.is_trusted_offer_url(job.url)
    assert calls == [CONFIG[0], URL] and jobs._eligible_offer(job)
    assert len(jobs._deduplicate_opportunities([job, job])) == 1


@pytest.mark.parametrize("status", [403, 429, 500])
@pytest.mark.parametrize("where", ["board", "detail"])
def test_http_failure_without_retry_or_unverified_fallback(serve, status, where):
    calls = serve(**({"status": status} if where == "board" else {"detail_status": status}))
    with pytest.raises(requests.HTTPError):
        collect()
    assert calls == ([CONFIG[0]] if where == "board" else [CONFIG[0], URL])


def test_network_failure_is_reported(serve):
    calls = serve(board=requests.Timeout("offline"))
    with pytest.raises(requests.Timeout):
        collect()
    assert calls == [CONFIG[0]]


@pytest.mark.parametrize("board", ["", "<h2>Careers</h2>", listing(2), listing(24), listing(0),
    listing(1, [(URL.replace("https:", "http:"), TITLE)]),
    listing(1, [(URL.replace(CONFIG[1], "example.invalid"), TITLE)])])
def test_unverified_empty_incomplete_or_paginated_board_is_not_success(serve, board):
    calls = serve(board=board)
    with pytest.raises(ValueError, match="Catalogue Nomura incomplet"):
        collect()
    assert calls == [CONFIG[0]]


def test_explicit_empty_board(serve):
    calls = serve(board=listing(0, []))
    assert collect() == [] and calls == [CONFIG[0]]


@pytest.mark.parametrize("changes", [{"description": ""}, {"location": ""}, {"programme": ""},
    {"apply": False}, {"expiry": "32/12/2026"}])
def test_incomplete_detail_is_reported(serve, changes):
    serve(offer=detail(**changes))
    with pytest.raises(ValueError):
        collect()


@pytest.mark.parametrize("status", [404, 410])
def test_removed_detail_is_excluded(serve, status):
    serve(detail_status=status)
    assert collect() == []


@pytest.mark.parametrize("offer", [detail(expiry="01/01/2020"),
    '<h1>Nomura</h1><p>This opportunity is closed</p>'])
def test_expired_and_closed_details_are_excluded(serve, offer):
    serve(offer=offer)
    assert collect() == []


@pytest.mark.parametrize("title", ["Global Markets Operations Internship", "Global Markets FSOPS Internship",
    "Global Markets Digital Office Summer Internship Quants Strats", "Retail Sales Internship",
    "Corporate Treasury Internship", "Senior Global Markets Sales Intern", "Software Engineer Intern"])
def test_no_operations_retail_corporate_or_technical_fallback(serve, title):
    serve(board=listing(1, [(URL, title)]), offer=detail(title=title))
    assert collect() == []


@pytest.mark.parametrize("programme", ["Insight Programme", "Apprenticeship", "Event"])
def test_only_requested_contracts(serve, programme):
    serve(offer=detail(programme=programme))
    assert collect() == []


def test_conflicting_cohorts_keep_employer_text_without_misleading_start(serve):
    text = ("Looking for an intern for the following start dates: January to June 2027. "
            "July to December 2027. " + TEXT.replace("January 2027", "July 2026"))
    serve(offer=detail(description=text))
    job, = collect()
    assert job.start_period == "" and job.description == text


def test_changed_slug_of_same_requisition_is_collected_once(serve):
    calls = serve(board=listing(1, [(URL, TITLE), (URL.replace("Solution-Sales", "Sales-Paris"), TITLE)]))
    assert len(collect()) == 1 and calls == [CONFIG[0], URL]


def test_redirected_or_mismatched_detail_is_not_published(serve):
    serve(offer=detail(title="Graduate Global Markets Sales - Tokyo"))
    with pytest.raises(ValueError, match="correspondante"):
        collect()


@pytest.mark.parametrize("title,expected", [(TITLE, "2026-11-01"), ("Other Sales Intern", "")])
def test_only_this_offers_structured_publication_date_is_used(serve, title, expected):
    structured = '<script type="application/ld+json">' + json.dumps({
        "@type": "JobPosting", "title": title, "datePosted": "2026-11-01"}) + '</script>'
    serve(offer=detail() + structured)
    job, = collect()
    assert job.published == expected


def test_generic_global_markets_title_uses_explicit_own_sales_team(serve):
    title = "2027 - Global Markets - Off-Cycle Internship - Frankfurt"
    text = "Work with Nomura’s Structured Sales team in Frankfurt for 3 months. German and English required."
    serve(board=listing(1, [(URL, title)]), offer=detail(title=title, description=text, location="Frankfurt"))
    job, = collect()
    assert job.family == "Sales" and job.location == "Frankfurt"


@pytest.mark.parametrize("title,programme,kind", [
    ("Graduate Global Markets Sales - London", "Graduate", "Graduate"),
    ("VIE Rates Sales - Paris", "VIE", "VIE"),
    ("Global Markets Rates Trading Summer Internship - London", "Summer internship", "Stage")])
def test_contract_and_desk_synonyms_without_location_filter(serve, title, programme, kind):
    serve(board=listing(1, [(URL, title)]), offer=detail(title=title, programme=programme, location="London"))
    job, = collect()
    assert job.kind == kind and job.location == "London"


@pytest.mark.skipif(os.environ.get("INTERNSHIPS_NOMURA_LIVE") != "1", reason="Public live audit opt-in")
def test_live_global_board_and_verified_details():
    started = perf_counter()
    found = collect()
    assert found and len(found) == len(jobs._deduplicate_opportunities(found))
    assert all(job.company == COMPANY and job.description and jobs._eligible_offer(job) for job in found)
    assert any(job.family == "Sales" for job in found)
    output = Path("artifacts/source-audit")
    output.mkdir(parents=True, exist_ok=True)
    (output / "nomura-collected.json").write_text(json.dumps({
        "seconds": round(perf_counter() - started, 3),
        "offers": [asdict(job) for job in found]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Nomura: {len(found)} verified offers, {perf_counter() - started:.3f}s, no duplicates")
    for job in found:
        print(f"{job.title} | {job.location} | {job.family} | published={job.published!r} | "
              f"start={job.start_period!r} | deadline={job.deadline!r} | {job.url}")
