"""Jump's official campus page publishes the Greenhouse endpoint used here.

Public audit: 2026-11-16 (Europe/Paris), 92 rows in the unpaginated API.
Official logo: https://www.jumptrading.com/cdn/68af4da447dcf4db12fcb35f/
68af4da447dcf4db12fcb4c2_favicon-32x32.png (linked by official careers HTML).
"""
import html
import os
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
import requests
from PIL import Image

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog
from internships_project.source_coverage import SOURCE_COVERAGE

SLUG = 'jumptrading'
COMPANY = 'Jump Trading'
BASE = f'https://job-boards.greenhouse.io/{SLUG}'
TITLE = 'Campus Quantitative Researcher (M1/M2 Intern)'


def row(identity=8059384, **changes):
    return {'id': identity, 'title': TITLE, 'location': {'name': 'London; Paris'},
            'absolute_url': f'https://www.jumptrading.com/hr/job?gh_jid={identity}',
            'content': html.escape('<p>Quantitative trading research. Graduating in 2027 or 2028.</p>'),
            'first_published': '2026-07-13T08:37:10-04:00',
            'updated_at': '2026-11-15T12:00:00Z', **changes}


def collect():
    return jobs._greenhouse_jobs(SLUG, COMPANY)


@pytest.fixture
def serve(monkeypatch):
    clock = Mock(wraps=datetime)
    clock.now.return_value = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(jobs, 'datetime', clock)

    def install(payload, status=200):
        response = requests.Response()
        response.status_code = status
        response.url = f'https://boards-api.greenhouse.io/v1/boards/{SLUG}/jobs'
        response.headers['Retry-After'] = '120'
        response.json = Mock(side_effect=payload) if isinstance(payload, Exception) else Mock(return_value=payload)
        get = Mock(side_effect=payload) if isinstance(payload, requests.RequestException) else Mock(return_value=response)
        monkeypatch.setattr(jobs.requests, 'get', get)
        return get
    return install


def test_source_card_date_registry_and_official_logo():
    assert [(fn, args) for name, fn, args in jobs._opportunity_source_tasks() if name == COMPANY] == [
        (jobs._greenhouse_jobs, (SLUG, COMPANY))]
    assert next(s for s in public_source_catalog() if s['name'] == COMPANY) == {
        'name': COMPANY, 'category': 'Courtage & trading', 'url': BASE,
        'added_on': '2026-11-16', 'feeds': [{'name': COMPANY, 'url': BASE}]}
    assert SOURCE_COVERAGE[COMPANY].status == 'connected'
    host = jobs.COMPANY_ICON_HOSTS[jobs._canonical_company(COMPANY)]
    assert host == 'www.jumptrading.com'
    with Image.open(jobs.COMPANY_LOGO_DIR / f'{host}.png') as logo:
        assert logo.format == 'PNG' and 0 < logo.width <= 96 and 0 < logo.height <= 96
        logo.verify()
    assert jobs._company_icon(COMPANY).startswith('data:image/png;base64,')


def test_nominal_dates_locations_and_contract_are_preserved(serve):
    get = serve({'jobs': [row()], 'meta': {'total': 1}})
    job, = collect()
    assert (job.company, job.title, job.location, job.kind) == (COMPANY, TITLE, 'London; Paris', 'Stage')
    assert job.published == '2026-07-13' and not job.published_inferred
    assert job.start_period == job.deadline == ''
    assert '<p>' not in job.description and '2028' in job.description
    assert job.url == f'{BASE}/jobs/8059384' and jobs._eligible_offer(job)
    get.assert_called_once_with(f'https://boards-api.greenhouse.io/v1/boards/{SLUG}/jobs',
                                params={'content': 'true'}, timeout=(8, 20))


@pytest.mark.parametrize('title,kind', [
    ('Campus Quantitative Trader (Full-Time)', 'Graduate'),
    ('Campus Quantitative Researcher (Full-Time)', 'Graduate'),
    ('Campus Quantitative Researcher | Trading Team PhD/Postdoc (Full-Time)', 'Graduate'),
    ('Campus Quantitative Trader (Intern)', 'Stage'),
    ('Rates Trading Intern', 'Stage'), ('Trading Assistant Intern', 'Stage'),
    ('Graduate Quantitative Trader', 'Graduate'),
])
def test_relevant_early_careers(serve, title, kind):
    serve({'jobs': [row(title=title)]})
    job, = collect()
    assert job.kind == kind and jobs._eligible_offer(job)


@pytest.mark.parametrize('title', ['Campus Software Engineer (Intern)', 'Campus AI Researcher (Intern)',
    'Campus Crypto Researcher (Full-Time)', 'Senior Quantitative Trader', 'Quantitative Trader',
    'Experienced Quantitative Researcher Intern', 'Campus Trading Operations Engineer (Intern)', 'Legal Intern'])
def test_unrelated_or_experienced_roles_are_excluded(serve, title):
    serve({'jobs': [row(title=title)]})
    assert collect() == []


@pytest.mark.parametrize('status', [403, 429, 500])
def test_refusal_or_api_failure_stops_without_retry_or_html_fallback(serve, status):
    get = serve({'jobs': [row()]}, status)
    with pytest.raises(requests.HTTPError):
        collect()
    get.assert_called_once()


@pytest.mark.parametrize('error', [requests.Timeout('offline'), ValueError('non JSON')])
def test_errors_are_not_empty_successes(serve, error):
    get = serve(error)
    with pytest.raises(type(error)):
        collect()
    get.assert_called_once()


@pytest.mark.parametrize('payload', [None, [], {}, {'jobs': None}, {'jobs': {}}, {'jobs': [None]},
    {'jobs': [], 'meta': {'total': 1}}, {'jobs': [], 'meta': None}, {'jobs': [], 'meta': {'total': '0'}}])
def test_incomplete_or_invalid_feed_raises(serve, payload):
    serve(payload)
    with pytest.raises(ValueError):
        collect()


@pytest.mark.parametrize('changes', [{'id': None}, {'id': '../bad'}, {'title': ''}, {'content': ''},
    {'location': None}, {'location': []}, {'location': {}}, {'location': {'name': ''}}])
def test_incomplete_rows_raise(serve, changes):
    serve({'jobs': [row(**changes)]})
    with pytest.raises(ValueError):
        collect()


def test_complete_empty_feed(serve):
    get = serve({'jobs': [], 'meta': {'total': 0}})
    assert collect() == []
    get.assert_called_once()


def test_unpaginated_feed_is_exhaustive_and_requisitions_remain_distinct(serve):
    get = serve({'jobs': [row(i) for i in range(1, 161)] + [row(1)], 'meta': {'total': 161}})
    found = collect()
    assert len(found) == len(jobs._deduplicate_opportunities(found)) == 160
    get.assert_called_once()


def test_untrusted_links_and_cohorts(serve):
    serve({'jobs': [row(), row(absolute_url='https://untrusted.invalid/job'), row(2),
                   row(3, content='Starting from January 2027. Quant trading.'),
                   row(4, content='Starting from June 2027. Quant trading.')]})
    found = collect()
    assert {j.url for j in found} == {f'{BASE}/jobs/{i}' for i in [8059384, 2, 3, 4]}
    assert {'January 2027', 'June 2027'} <= {j.start_period for j in found}


@pytest.mark.parametrize('published', ['', None, 'bad', '2026-02-30', '2099-01-01'])
def test_unknown_publication_is_not_replaced_by_update_or_detection(serve, published):
    serve({'jobs': [row(first_published=published)]})
    assert collect()[0].published == ''


def test_explicit_start_deadline_and_publication_are_distinct(serve):
    serve({'jobs': [row(content='Starting from January 2027. Graduation June 2028.',
                        application_deadline='2026-12-10')]})
    job, = collect()
    assert (job.published, job.start_period, job.deadline) == ('2026-07-13', 'January 2027', '2026-12-10')
    serve({'jobs': [row(application_deadline='2020-01-01')]})
    assert collect() == []


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_JUMP_LIVE') != '1', reason='Public audit is opt-in')
def test_live_official_portal_attribution():
    page = requests.get('https://www.jumptrading.com/hr/students-new-grads', timeout=(8, 20))
    page.raise_for_status()
    assert f'https://boards-api.greenhouse.io/v1/boards/{SLUG}/jobs' in page.text


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_JUMP_LIVE') != '1', reason='Public audit is opt-in')
def test_live_collection_and_official_details():
    found = collect()
    assert len(found) == len(jobs._deduplicate_opportunities(found))
    job = next(j for j in found if j.title == TITLE)
    assert 'Paris' in job.location
    detail = requests.get(job.url, timeout=(8, 20))
    detail.raise_for_status()
    # Greenhouse redirects to Jump's JS-rendered employer page. Its HTML is
    # a template, so verify the official permalink and public detail API.
    assert detail.url == 'https://www.jumptrading.com/hr/job?gh_jid=8059384'
    posting = requests.get(f'https://boards-api.greenhouse.io/v1/boards/{SLUG}/jobs/8059384',
                           timeout=(8, 20))
    posting.raise_for_status()
    data = posting.json()
    assert data['id'] == 8059384 and data['title'] == job.title
    assert data['location']['name'] == job.location
    assert jobs._plain_text(html.unescape(data['content']))[:12_000] == job.description
    assert any(j.title == 'Campus Quantitative Trader (Full-Time)' and j.kind == 'Graduate' for j in found)
    for job in found:
        assert jobs._eligible_offer(job)
        print(f'{job.title} | {job.location} | {job.kind} | publication={job.published} | {job.url}')
    print(f'Jump Trading: {len(found)} offres admissibles sans doublon ; fiche publique HTTP {detail.status_code}')
