"""Five Rings uses Greenhouse's complete public feed, without HTML fallback."""
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

SLUG = 'fiveringsllc'
COMPANY = 'Five Rings'
BASE = f'https://job-boards.greenhouse.io/{SLUG}'
TITLE = 'Summer Intern 2027 - Quantitative Trader'


def row(identity=5139668008, **changes):
    return {'id': identity, 'title': TITLE, 'location': {'name': 'New York'},
            'absolute_url': f'{BASE}/jobs/{identity}',
            'content': html.escape('<p>Research and development with the trading team. '
                                   'Graduating in winter of 2027 or spring/summer of 2028.</p>'),
            'first_published': '2026-07-14T13:48:21-04:00',
            'updated_at': '2026-11-15T10:00:00Z', **changes}


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


def test_registry_source_card_date_and_bundled_official_logo():
    assert jobs.GREENHOUSE[SLUG] == COMPANY
    assert [(fn, args) for name, fn, args in jobs._opportunity_source_tasks() if name == COMPANY] == [
        (jobs._greenhouse_jobs, (SLUG, COMPANY))]
    source = next(s for s in public_source_catalog() if s['name'] == COMPANY)
    assert source == {'name': COMPANY, 'category': 'Courtage & trading', 'url': BASE,
                      'feeds': [{'name': COMPANY, 'url': BASE}], 'added_on': '2026-11-16'}
    assert SOURCE_COVERAGE[COMPANY].status == 'connected'
    assert jobs.COMPANY_ICON_HOSTS[jobs._canonical_company(COMPANY)] == 'fiverings.com'
    with Image.open(jobs.COMPANY_LOGO_DIR / 'fiverings.com.png') as logo:
        assert logo.format == 'PNG' and 0 < logo.width <= 96 and 0 < logo.height <= 96
        logo.verify()
    assert jobs._company_icon(COMPANY).startswith('data:image/png;base64,')


def test_publication_location_and_graduation_are_not_a_start_date(serve):
    get = serve({'jobs': [row()], 'meta': {'total': 1}})
    job, = collect()
    assert (job.title, job.company, job.location, job.kind) == (TITLE, COMPANY, 'New York', 'Stage')
    assert job.family == 'Trading / Structuring' and jobs._eligible_offer(job)
    assert job.published == '2026-07-14' and not job.published_inferred
    assert job.start_period == job.deadline == ''
    assert '2028' in job.description and '<p>' not in job.description
    get.assert_called_once_with(f'https://boards-api.greenhouse.io/v1/boards/{SLUG}/jobs',
                                params={'content': 'true'}, timeout=(8, 20))


@pytest.mark.parametrize('title,location,kind', [
    ('Campus Full Time 2027 - Quantitative Trader', 'New York', 'Graduate'),
    ('Campus Full Time 2027 - Quantitative Trader - London', 'London', 'Graduate'),
    ('Campus Full Time 2027 - Quantitative Trader - Amsterdam', 'Amsterdam', 'Graduate'),
    ('Recent Graduate - Trading Assistant (NYC)', 'New York', 'Graduate'),
    ('Summer Intern 2027 - Quantitative Researcher (PhD)', 'New York', 'Stage'),
])
def test_verified_early_career_title_categories(serve, title, location, kind):
    serve({'jobs': [row(title=title, location={'name': location})]})
    job, = collect()
    assert (job.title, job.location, job.kind) == (title, location, kind)
    assert jobs._eligible_offer(job)
    assert len(jobs._deduplicate_opportunities([job, job])) == 1


@pytest.mark.parametrize('title', ['Experienced/Lateral - Quantitative Researcher',
    'Experienced/Lateral - Trading Assistant', 'Campus Full Time 2027 - Trading Operations Engineer',
    'Summer 2027 - Trading Operations Engineer Intern', 'Summer Intern 2027 - Software Developer',
    'Legal Intern', 'Senior Quantitative Trader', 'Middle Office Trading Intern'])
def test_experienced_and_unrelated_jobs_are_excluded(serve, title):
    serve({'jobs': [row(title=title)]})
    assert collect() == []


@pytest.mark.parametrize('status', [403, 429, 500])
def test_refusal_or_api_failure_has_no_retry_or_html_fallback(serve, status):
    get = serve({'jobs': [row()]}, status)
    with pytest.raises(requests.HTTPError):
        collect()
    get.assert_called_once()


@pytest.mark.parametrize('error', [requests.Timeout('offline'), ValueError('non JSON')])
def test_errors_are_not_reported_as_an_empty_feed(serve, error):
    get = serve(error)
    with pytest.raises(type(error)):
        collect()
    get.assert_called_once()


@pytest.mark.parametrize('payload', [None, [], {}, {'jobs': None}, {'jobs': {}}, {'jobs': [None]},
    {'jobs': [], 'meta': {'total': 1}}, {'jobs': [], 'meta': None},
    {'jobs': [], 'meta': {'total': '0'}}])
def test_invalid_and_incomplete_catalogues_raise(serve, payload):
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


def test_unpaginated_feed_reads_all_rows_and_retains_distinct_requisitions(serve):
    get = serve({'jobs': [row(i) for i in range(1, 161)], 'meta': {'total': 160}})
    found = collect()
    assert len(found) == len(jobs._deduplicate_opportunities(found)) == 160
    get.assert_called_once()


def test_duplicate_identity_merges_and_feed_cannot_supply_an_arbitrary_link(serve):
    serve({'jobs': [row(), row(absolute_url='https://untrusted.invalid/job'), row(2),
                   row(3, content='Starting from January 2027. Quant trading.'),
                   row(4, content='Starting from June 2027. Quant trading.')]})
    found = collect()
    assert len(found) == 4
    assert {j.url for j in found} == {f'{BASE}/jobs/{i}' for i in [5139668008, 2, 3, 4]}
    assert {'January 2027', 'June 2027'} <= {j.start_period for j in found}


@pytest.mark.parametrize('published', ['', None, 'bad', '2026-02-30', '2099-01-01'])
def test_unknown_publication_is_never_replaced_by_update_or_detection(serve, published):
    serve({'jobs': [row(first_published=published)]})
    assert collect()[0].published == ''


def test_start_deadline_and_publication_remain_distinct(serve):
    serve({'jobs': [row(content='Starting from June 2027. Graduation in 2028.',
                        application_deadline='2026-12-10')]})
    job, = collect()
    assert (job.published, job.start_period, job.deadline) == ('2026-07-14', 'June 2027', '2026-12-10')
    serve({'jobs': [row(application_deadline='2020-01-01')]})
    assert collect() == []


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_FIVE_RINGS_LIVE') != '1', reason='Public audit is opt-in')
def test_live_collection_and_official_detail():
    found = collect()
    assert any(j.title == TITLE and j.location == 'New York' for j in found)
    assert len(found) == len(jobs._deduplicate_opportunities(found))
    for job in found:
        assert jobs._eligible_offer(job)
        print(f'{job.title} | {job.location} | {job.kind} | publication={job.published} | '
              f'debut={job.start_period!r} | {job.url}')
    job = next(j for j in found if j.title == TITLE)
    response = requests.get(job.url, timeout=(8, 20))
    response.raise_for_status()
    assert job.title in html.unescape(response.text)
    assert job.location in html.unescape(response.text)
    print(f'Five Rings: {len(found)} offres admissibles sans doublon, fiche stage HTTP {response.status_code}')
