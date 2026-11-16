"""DRW reuses the public Greenhouse connector; no HTML fallback or cache reads."""
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

SLUG = 'drweng'
COMPANY = 'DRW'
TITLE = 'Quantitative Trading Analyst Intern'
BASE = f'https://job-boards.greenhouse.io/{SLUG}'


def row(identity=7668776, **changes):
    return {'id': identity, 'title': TITLE, 'location': {'name': 'Chicago, Illinois'},
            'absolute_url': f'{BASE}/jobs/{identity}',
            'content': html.escape('<p>Research quantitative trading strategies. '
                                   'Expected graduation December 2027 to June 2028.</p>'),
            'first_published': '2026-07-13T10:34:56-04:00',
            'updated_at': '2026-11-09T19:49:00-05:00', **changes}


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
        get = Mock(return_value=response)
        monkeypatch.setattr(jobs.requests, 'get', get)
        return get
    return install


def test_registry_catalog_date_and_official_logo():
    assert jobs.GREENHOUSE[SLUG] == COMPANY
    assert [(fn, args) for name, fn, args in jobs._opportunity_source_tasks() if name == COMPANY] == [
        (jobs._greenhouse_jobs, (SLUG, COMPANY))]
    source = next(s for s in public_source_catalog() if s['name'] == COMPANY)
    assert source == {'name': COMPANY, 'category': 'Courtage & trading', 'url': BASE,
                      'added_on': '2026-11-16', 'feeds': [{'name': COMPANY, 'url': BASE}]}
    host = jobs.COMPANY_ICON_HOSTS[jobs._canonical_company(COMPANY)]
    assert host == 'www.drw.com'
    with Image.open(jobs.COMPANY_LOGO_DIR / f'{host}.png') as logo:
        assert logo.format == 'PNG' and 0 < logo.width <= 96 and 0 < logo.height <= 96
        logo.verify()
    assert jobs._company_icon(COMPANY).startswith('data:image/png;base64,')


def test_quant_intern_keeps_employer_location_publication_and_unknown_start(serve):
    get = serve({'jobs': [row()], 'meta': {'total': 1}})
    job, = collect()
    assert (job.company, job.title, job.kind, job.family) == (COMPANY, TITLE, 'Stage', 'Trading / Structuring')
    assert job.location == 'Chicago, Illinois'
    assert job.published == '2026-07-13' and not job.published_inferred
    assert job.start_period == job.deadline == ''
    assert 'December 2027' in job.description and '<p>' not in job.description
    assert jobs._eligible_offer(job)
    get.assert_called_once_with(f'https://boards-api.greenhouse.io/v1/boards/{SLUG}/jobs',
                                params={'content': 'true'}, timeout=(8, 20))


@pytest.mark.parametrize('title', ['Quantitative Research Intern', 'Rates Trading Intern',
                                  'Trading Assistant Intern', 'Graduate Quant Trader'])
def test_related_early_career_roles(serve, title):
    serve({'jobs': [row(title=title, location={'name': 'Singapore'})]})
    job, = collect()
    assert job.location == 'Singapore' and jobs._eligible_offer(job)


@pytest.mark.parametrize('title', ['Software Developer Intern', 'Venture Capital Analyst Intern',
                                  'Senior Quantitative Trader', 'Legal Intern', 'Middle Office Trading Intern'])
def test_unrelated_and_experienced_roles_are_excluded(serve, title):
    serve({'jobs': [row(title=title)]})
    assert collect() == []


@pytest.mark.parametrize('status', [403, 429, 500])
def test_api_refusal_or_failure_stops_without_retry_or_html_fallback(serve, status):
    get = serve({'jobs': [row()]}, status)
    with pytest.raises(requests.HTTPError):
        collect()
    get.assert_called_once()


@pytest.mark.parametrize('error', [requests.Timeout('offline'), ValueError('non JSON')])
def test_request_and_json_errors_are_not_empty_successes(serve, error):
    get = serve(error)
    with pytest.raises(type(error)):
        collect()
    get.assert_called_once()


@pytest.mark.parametrize('payload', [None, [], {}, {'jobs': None}, {'jobs': {}}, {'jobs': [None]},
    {'jobs': [], 'meta': {'total': 1}}, {'jobs': [], 'meta': None},
    {'jobs': [], 'meta': {'total': '0'}}])
def test_invalid_or_truncated_feed_raises(serve, payload):
    serve(payload)
    with pytest.raises(ValueError):
        collect()


@pytest.mark.parametrize('changes', [{'id': None}, {'id': '../bad'}, {'title': ''}, {'content': ''},
    {'location': None}, {'location': []}, {'location': {}}, {'location': {'name': ''}}])
def test_incomplete_rows_cannot_claim_success(serve, changes):
    serve({'jobs': [row(**changes)]})
    with pytest.raises(ValueError):
        collect()


def test_empty_complete_feed(serve):
    get = serve({'jobs': [], 'meta': {'total': 0}})
    assert collect() == []
    get.assert_called_once()


def test_all_rows_are_read_in_one_unpaginated_response(serve):
    get = serve({'jobs': [row(i, title=f'Quant Trading Intern - Desk {i}') for i in range(1, 160)],
                 'meta': {'total': 159}})
    assert len(collect()) == 159
    get.assert_called_once()


def test_duplicates_merge_but_distinct_requisitions_and_cohorts_survive(serve):
    serve({'jobs': [row(), row(absolute_url='https://untrusted.invalid/job'), row(2),
                   row(3, content='Starting from January 2027. Quant trading.'),
                   row(4, content='Starting from June 2027. Quant trading.')]})
    found = collect()
    assert len(found) == 4 and len({j.url for j in found}) == 4
    assert {'January 2027', 'June 2027'} <= {j.start_period for j in found}
    assert {j.url for j in found} == {f'{BASE}/jobs/{i}' for i in [7668776, 2, 3, 4]}


@pytest.mark.parametrize('published', ['', None, 'bad', '2026-02-30', '2099-01-01'])
def test_modification_and_detection_never_replace_unknown_publication(serve, published):
    serve({'jobs': [row(first_published=published)]})
    assert collect()[0].published == ''


def test_explicit_start_and_expiry_are_separate_from_publication(serve):
    serve({'jobs': [row(content='Starting from January 2027. Graduation June 2028.',
                        application_deadline='2026-12-10')]})
    job, = collect()
    assert (job.published, job.start_period, job.deadline) == ('2026-07-13', 'January 2027', '2026-12-10')
    serve({'jobs': [row(application_deadline='2020-01-01')]})
    assert collect() == []


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_DRW_LIVE') != '1', reason='Public audit is opt-in')
def test_live_collection_and_public_details():
    began = perf_counter()
    found = collect()
    assert any(j.title == TITLE and j.location == 'Chicago, Illinois' for j in found)
    assert len(found) == len(jobs._deduplicate_opportunities(found))
    print(f'DRW: {len(found)} offres en {perf_counter() - began:.3f}s, aucun doublon')
    for job in found:
        response = requests.get(job.url, timeout=(8, 20))
        response.raise_for_status()
        assert response.status_code == 200
        assert job.title in html.unescape(response.text)
        assert job.location in html.unescape(response.text)
        assert jobs._eligible_offer(job)
        print(f'{job.title} | {job.location} | {job.kind} | publication={job.published} | '
              f'debut={job.start_period!r} | echeance={job.deadline!r} | {job.url} | HTTP 200')
