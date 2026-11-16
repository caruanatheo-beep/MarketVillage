"""Fidelity Early Careers reuses CAREER_LISTINGS, without private persistence."""
import os

import pytest
import requests
from PIL import Image

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog
from internships_project.source_coverage import SOURCE_COVERAGE


COMPANY = "Fidelity International"
CONFIG = jobs.CAREER_LISTINGS[COMPANY]
TITLE = "Institutional Sales Intern Programme 2027 - Paris"
URL = f"https://{CONFIG[1]}{CONFIG[2]}1422-Institutional-Sales-Intern-Programme-2027-Paris/en-GB"


def listing(total=1, links=None):
    links = [(URL, TITLE), (URL, TITLE)] if links is None else links
    return f'<h2>{total} results match!</h2>' + ''.join(
        f'<a href="{url}">{title}</a>' for url, title in links)


def detail(title=TITLE, description=None, programme="Internship"):
    description = ("<p>Location</p><p>Paris</p><p>Join our Institutional sales team.</p>"
        "<p>Start date: January 2027. Graduation June 2028.</p>"
        if description is None else description)
    return (f'<h1>{title}</h1><span>Job description</span>{description}'
        f'<span>Programme</span><div>{programme}</div>')


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
        monkeypatch.setattr(jobs.requests, "post", lambda *a, **k: pytest.fail("No unverified API fallback"))
        monkeypatch.setattr(jobs, "_render_public_career_page", lambda *a, **k: pytest.fail("No browser fallback"))
        monkeypatch.setattr(jobs.time, "sleep", lambda *a: pytest.fail("No immediate retry"))
        return calls
    return setup


def collect():
    return jobs._career_page_jobs(COMPANY, CONFIG)


def test_registered_once_as_asset_manager_with_publication_date_and_official_logo():
    assert [(fn, args) for name, fn, args in jobs._opportunity_source_tasks() if name == COMPANY] == [
        (jobs._career_page_jobs, (COMPANY, CONFIG))]
    source, = [source for source in public_source_catalog() if source["name"] == COMPANY]
    assert source["category"] == "Gestion d’actifs"
    assert source["added_on"] == "2026-11-16"
    assert source["url"] == CONFIG[0] and len(source["feeds"]) == 1
    assert SOURCE_COVERAGE[COMPANY].status == "connected"
    with Image.open(jobs.COMPANY_LOGO_DIR / "careers.fidelityinternational.com.png") as logo:
        assert logo.format == "PNG" and 0 < logo.width <= 96 and 0 < logo.height <= 96
        logo.verify()
    assert jobs._company_icon(COMPANY).startswith("data:image/png;base64,")


def test_verified_paris_stage_dates_and_duplicate_tiles(serve):
    calls = serve()
    job, = collect()
    assert (job.company, job.kind, job.family, job.location) == (COMPANY, "Stage", "Sales", "Paris")
    assert (job.published, job.start_period, job.deadline) == ("", "January 2027", "")
    assert job.description and jobs.is_trusted_offer_url(job.url)
    assert calls == [CONFIG[0], URL]
    assert len(jobs._deduplicate_opportunities([job, job])) == 1


@pytest.mark.parametrize("status", [403, 429, 500])
def test_http_failure_stops_without_retry_or_fallback(serve, status):
    calls = serve(status=status)
    with pytest.raises(requests.HTTPError):
        collect()
    assert calls == [CONFIG[0]]


def test_network_failure_stops_without_unverified_api_fallback(serve):
    calls = serve(board=requests.Timeout("offline"))
    with pytest.raises(requests.Timeout):
        collect()
    assert calls == [CONFIG[0]]


@pytest.mark.parametrize("board", ["", "<h2>Careers</h2>", listing(2), listing(60), listing(0),
    listing(1, [(URL.replace("https:", "http:"), TITLE)]),
    listing(1, [("https://example.invalid/opp/1422-job/en-GB", TITLE)])])
def test_empty_incomplete_and_truncated_pagination_are_not_success(serve, board):
    calls = serve(board=board)
    with pytest.raises(ValueError, match="Catalogue Fidelity incomplet"):
        collect()
    assert calls == [CONFIG[0]]


def test_explicit_empty_catalogue(serve):
    calls = serve(board=listing(0, []))
    assert collect() == [] and calls == [CONFIG[0]]


@pytest.mark.parametrize("status", [403, 429, 500])
def test_failed_live_detail_never_publishes_listing_only(serve, status):
    calls = serve(detail_status=status)
    with pytest.raises(requests.HTTPError):
        collect()
    assert calls == [CONFIG[0], URL]


@pytest.mark.parametrize("offer", ["<h1>Careers</h1>", detail(description=""),
    detail(programme=""), detail(title="Institutional Sales Intern", description="No location")])
def test_incomplete_detail_is_reported(serve, offer):
    serve(offer=offer)
    with pytest.raises(ValueError):
        collect()


@pytest.mark.parametrize("text", ["This opportunity is closed", "No longer accepting applications"])
def test_closed_offer_is_excluded(serve, text):
    serve(offer=f"<h1>{TITLE}</h1><p>{text}</p>")
    assert collect() == []


@pytest.mark.parametrize("status", [404, 410])
def test_removed_offer_is_excluded(serve, status):
    serve(detail_status=status)
    assert collect() == []


@pytest.mark.parametrize("description,start", [
    ("This is a full time internship to join the Institutional Sales team specifically from early January 2027 till end of June 2027.", "January 2027"),
    ("Duration: 6 Months (June to December 2027)", "June 2027"),
    ("Graduation June 2028. Six months.", ""),
])
def test_only_explicit_programme_dates_supply_the_start(serve, description, start):
    serve(offer=detail(description=f"<p>Location</p><p>Paris</p><p>{description}</p>"))
    job, = collect()
    assert (job.published, job.start_period, job.deadline) == ("", start, "")


@pytest.mark.parametrize("title", ["Technology Graduate Programme 2027 - London",
    "Financial Marketing Internship Programme 2027 - Paris", "Senior Institutional Sales Manager - London"])
def test_non_markets_and_experienced_programmes_are_excluded(serve, title):
    serve(board=listing(1, [(URL, title)]), offer=detail(title=title))
    assert collect() == []


def test_global_fixed_income_and_no_inferred_publication_or_start(serve):
    title = "Fixed Income Off-Cycle Internship Programme 2027 - Hong Kong"
    serve(board=listing(1, [(URL, title)]), offer=detail(title=title,
        description="<p>Fixed Income team: trading, portfolio management, credit research.</p>"
        "<p>Graduation June 2028. Six months.</p>"))
    job, = collect()
    assert (job.location, job.kind, job.published, job.start_period) == ("Hong Kong", "Stage", "", "")


def test_partial_details_keep_verified_results(serve, monkeypatch):
    other = URL.replace("1422-", "1396-")
    serve(board=listing(2, [(URL, TITLE), (other, TITLE)]))
    original = jobs.requests.get
    def get(url, **kwargs):
        return Response("unavailable", 429) if url == other else original(url, **kwargs)
    monkeypatch.setattr(jobs.requests, "get", get)
    with pytest.raises(jobs._PartialSourceError) as failure:
        collect()
    assert len(failure.value.jobs) == 1 and failure.value.failed_urls == {other}


@pytest.mark.skipif(os.environ.get("INTERNSHIPS_FIDELITY_LIVE") != "1", reason="Public live audit is opt-in")
def test_live_collection():
    found = collect()
    assert any("Institutional Sales" in job.title and job.location == "Paris" for job in found)
    assert any("Fixed Income" in job.title and job.location == "Hong Kong" for job in found)
    assert all(job.company == COMPANY and job.description and jobs.is_trusted_offer_url(job.url) for job in found)
    assert len(found) == len(jobs._deduplicate_opportunities(found))
    print(f"Fidelity International: {len(found)} verified public offers")
    for job in found:
        print(f"{job.title} | {job.location} | publication={job.published!r} | start={job.start_period!r}")
