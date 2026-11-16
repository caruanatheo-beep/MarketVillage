"""Squarepoint reuses Greenhouse; no HTML fallback. See SOURCES_SQUAREPOINT.md."""
import html
import os
from datetime import datetime, timezone
from time import perf_counter
from unittest.mock import Mock

import pytest
import requests
from PIL import Image

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog

SLUG = 'squarepointcapital'
COMPANY = 'Squarepoint Capital'
TITLE = 'Intern Quant Researcher'


def row(identity=243853, **changes):
    return {'id': identity, 'title': TITLE,
            'location': {'name': 'London, Paris, New York, Singapore, Hong Kong'},
            'absolute_url': f'https://www.squarepoint-capital.com/open-opportunities?id={identity}&gh_jid={identity}',
            'content': html.escape('<p>Research trading strategies within the automated trading framework. '
                                   'Graduation in August 2028.</p>'),
            'first_published': '2023-07-06T04:50:24-04:00',
            'updated_at': '2026-11-15T08:00:00Z', **changes}


def collect():
    return jobs._greenhouse_jobs(SLUG, COMPANY)


@pytest.fixture
def serve(monkeypatch):
    clock = Mock(wraps=datetime)
    clock.now.return_value = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(jobs, 'datetime', clock)

    def install(payload, status=200):
        response = requests.Response()
        response.status_code = status
        response.url = f'https://boards-api.greenhouse.io/v1/boards/{SLUG}/jobs'
        response.json = Mock(side_effect=payload) if isinstance(payload, Exception) else Mock(return_value=payload)
        get = Mock(return_value=response)
        monkeypatch.setattr(jobs.requests, 'get', get)
        return get
    return install


def test_registered_once_with_category_date_and_official_bundled_logo():
    assert jobs.GREENHOUSE[SLUG] == COMPANY
    assert [(fn, args) for name, fn, args in jobs._opportunity_source_tasks() if name == COMPANY] == [
        (jobs._greenhouse_jobs, (SLUG, COMPANY))]
    source = next(s for s in public_source_catalog() if s['name'] == COMPANY)
    assert source['category'] == 'Courtage & trading'
    assert source['added_on'] == '2026-11-15'
    assert source['url'] == f'https://job-boards.greenhouse.io/{SLUG}'
    host = jobs.COMPANY_ICON_HOSTS[jobs._canonical_company(COMPANY)]
    assert host == 'www.squarepoint-capital.com'
    with Image.open(jobs.COMPANY_LOGO_DIR / f'{host}.png') as logo:
        assert logo.format == 'PNG' and 0 < logo.width <= 96 and 0 < logo.height <= 96
        logo.verify()
    assert jobs._company_icon(COMPANY).startswith('data:image/png;base64,')


def test_quant_intern_keeps_employer_locations_and_original_publication(serve):
    get = serve({'jobs': [row()]})
    job, = collect()
    assert (job.company, job.kind, job.family) == (COMPANY, 'Stage', 'Quant / Research')
    assert job.location == 'London, Paris, New York, Singapore, Hong Kong'
    assert job.published == '2023-07-06' and not job.published_inferred
    assert job.start_period == job.deadline == ''
    assert 'August 2028' in job.description and '<p>' not in job.description
    assert job.url == f'https://job-boards.greenhouse.io/{SLUG}/jobs/243853'
    get.assert_called_once_with(f'https://boards-api.greenhouse.io/v1/boards/{SLUG}/jobs',
                                params={'content': 'true'}, timeout=(8, 20))


@pytest.mark.parametrize('title', ['Graduate Quant Developer', 'Graduate Trading Applications Specialist',
                                  'Junior Commodities Fundamental Analyst'])
def test_related_early_career_roles_keep_existing_contract_rules(serve, title):
    serve({'jobs': [row(title=title)]})
    job, = collect()
    assert job.kind == 'Graduate' and jobs._eligible_offer(job)


@pytest.mark.parametrize('title', ['Trading Infrastructure Specialist – Graduate Program',
    'Junior Desktop Support Analyst', 'Graduate Trading Platform Engineer', 'Senior Quant Researcher',
    'Middle Office Trading Intern', 'Retail Sales Intern', 'Legal Intern', 'Corporate Finance Intern'])
def test_unrelated_it_experienced_and_non_market_roles_are_excluded(serve, title):
    serve({'jobs': [row(title=title)]})
    assert collect() == []


@pytest.mark.parametrize('status', [403, 429, 500])
def test_api_refusal_or_failure_stops_once_without_html_fallback(serve, status):
    get = serve({'jobs': [row()]}, status=status)
    with pytest.raises(requests.HTTPError):
        collect()
    get.assert_called_once()


@pytest.mark.parametrize('error', [requests.Timeout('offline'), ValueError('non JSON')])
def test_api_and_json_errors_are_not_empty_successes(serve, error):
    get = serve(error)
    with pytest.raises(type(error)):
        collect()
    get.assert_called_once()


@pytest.mark.parametrize('payload', [None, [], {}, {'jobs': None}, {'jobs': {}}, {'jobs': [None]}])
def test_invalid_catalogue_raises(serve, payload):
    serve(payload)
    with pytest.raises(ValueError):
        collect()


@pytest.mark.parametrize('changes', [{'id': None}, {'id': '../bad'}, {'title': ''}, {'content': ''},
                                   {'location': None}, {'location': []}, {'location': {}}])
def test_incomplete_rows_cannot_claim_success(serve, changes):
    serve({'jobs': [row(**changes)]})
    with pytest.raises(ValueError, match='Squarepoint incomplète|Localisation publique Greenhouse invalide'):
        collect()


def test_complete_empty_feed_succeeds(serve):
    get = serve({'jobs': []})
    assert collect() == []
    get.assert_called_once()


def test_entire_feed_is_read_without_a_pagination_cap(serve):
    # Greenhouse's public jobs endpoint returns all rows in one response.
    get = serve({'jobs': [row(i, title=f'Quant Trading Intern - Desk {i}') for i in range(1, 122)]})
    assert len(collect()) == 121
    get.assert_called_once()


def test_duplicate_rows_merge_but_distinct_jobs_and_cohorts_survive(serve):
    serve({'jobs': [row(), row(), row(2, title='Rates Trading Intern'),
                   row(3, content='Starting from January 2027. Quant research.'),
                   row(4, content='Starting from June 2027. Quant research.')]})
    found = collect()
    assert len(found) == 4
    assert len({job.url for job in found}) == 4
    assert {'January 2027', 'June 2027'} <= {job.start_period for job in found}


@pytest.mark.parametrize('published', ['', None, 'bad', '2026-02-30', '2099-01-01'])
def test_modification_and_detection_do_not_replace_unknown_publication(serve, published):
    serve({'jobs': [row(first_published=published)]})
    assert collect()[0].published == ''


def test_start_and_expiry_remain_separate_from_publication(serve):
    serve({'jobs': [row(content='Starting from January 2027. Graduation August 2028.',
                        application_deadline='2026-12-10T00:00:00Z')]})
    job, = collect()
    assert (job.published, job.start_period, job.deadline) == ('2023-07-06', 'January 2027', '2026-12-10')
    serve({'jobs': [row(application_deadline='2020-01-01')]})
    assert collect() == []


def test_public_row_cannot_redirect_collector_to_an_arbitrary_host(serve):
    get = serve({'jobs': [row(absolute_url='https://untrusted.invalid/job/1')]})
    assert collect()[0].url == f'https://job-boards.greenhouse.io/{SLUG}/jobs/243853'
    get.assert_called_once()


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_SQUAREPOINT_LIVE') != '1', reason='Public audit is opt-in')
def test_live_collection_and_public_employer_details():
    from playwright.sync_api import sync_playwright

    began = perf_counter()
    found = collect()
    elapsed = perf_counter() - began
    assert any(job.title == TITLE for job in found)
    assert len(found) == len(jobs._deduplicate_opportunities(found))
    print(f'Squarepoint: {len(found)} offers, {elapsed:.3f}s, no duplicates')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            for job in found:
                response = page.goto(job.url, timeout=25000)
                assert response.status == 200
                assert jobs.urlparse(page.url).hostname == 'www.squarepoint-capital.com'
                page.get_by_text(job.title, exact=True).first.wait_for(timeout=15000)
                assert jobs._eligible_offer(job)
                print(f'{job.title} | {job.location} | {job.kind} | publication={job.published} | '
                      f'start={job.start_period!r} | expiry={job.deadline!r} | {job.url} | HTTP 200')
        finally:
            browser.close()
