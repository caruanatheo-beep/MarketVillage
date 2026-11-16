"""Maven's official careers page embeds mavensecuritiesholdingltd on Greenhouse.

Only the existing public, unpaginated API is used: no HTML fallback is claimed.
The opt-in audit reads public pages and never loads or writes offer caches.
"""
import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog

COMPANY = 'Maven Securities'
SLUG = 'mavensecuritiesholdingltd'
BASE = f'https://job-boards.greenhouse.io/{SLUG}'


def row(identity=8048591, **changes):
    return dict({
        'id': identity, 'title': 'Amsterdam Trader Summer Internship 2027',
        'absolute_url': f'{BASE}/jobs/{identity}', 'location': {'name': 'Amsterdam'},
        'first_published': '2026-09-01T10:49:24-04:00',
        'updated_at': '2026-11-14T12:00:00Z',
        'content': html.escape('<p>Options market making and trading simulation.</p>'
            '<p>Programme dates: 21st June – 20th August 2027.</p>'
            '<p>You must be graduating in 2028.</p>'),
    }, **changes)


def collect():
    return jobs._greenhouse_jobs(SLUG, COMPANY)


@pytest.fixture
def feed(monkeypatch):
    clock = Mock(wraps=datetime)
    clock.now.return_value = datetime(2026, 11, 15, tzinfo=timezone.utc)
    monkeypatch.setattr(jobs, 'datetime', clock)

    def serve(payload):
        request = Mock(return_value=SimpleNamespace(json=lambda: payload, raise_for_status=lambda: None))
        monkeypatch.setattr(jobs.requests, 'get', request)
        return request
    return serve


def test_one_active_source_category_date_and_official_png():
    assert [(fn, args) for name, fn, args in jobs._opportunity_source_tasks() if name == COMPANY] == [
        (jobs._greenhouse_jobs, (SLUG, COMPANY))]
    source, = [s for s in public_source_catalog() if s['name'] == COMPANY]
    assert source['category'] == 'Courtage & trading'
    assert source['url'] == BASE and source['added_on'] == '2026-11-15'
    assert source['feeds'] == [{'name': COMPANY, 'url': BASE}]
    host = jobs.COMPANY_ICON_HOSTS[jobs._canonical_company(COMPANY)]
    assert host == 'www.mavensecurities.com'
    with Image.open(jobs.COMPANY_LOGO_DIR / f'{host}.png') as logo:
        assert logo.format == 'PNG' and min(logo.size) >= 32
        logo.verify()


@pytest.mark.skipif(not all(
    (Path(__file__).resolve().parents[1] / 'deploy/github-pages/site' / asset).is_file()
    for asset in ('index.html', 'site.css', 'app.js', 'sources.js', 'marketdesk-icon.svg')),
    reason='Static Pages assets are absent from this isolated checkout')
def test_source_and_offer_export_share_the_bundled_official_logo(feed, tmp_path, monkeypatch):
    from scripts import build_internships_pages as builder

    feed({'jobs': [row()]})
    current = collect()
    monkeypatch.setattr(jobs, 'CACHE_PATH', tmp_path / 'unused-cache.json')
    monkeypatch.setattr(jobs, 'load_opportunities', lambda **_: (
        current, [], datetime(2026, 11, 15, tzinfo=timezone.utc)))
    monkeypatch.setattr(jobs, 'source_checks', lambda: {})
    monkeypatch.setenv('SOURCE_REQUEST_ENDPOINT', '')
    output = tmp_path / 'site'
    assert builder.build_site(output) == 1
    catalog = json.loads((output / 'sources.json').read_bytes())
    source, = [s for s in catalog['sources'] if s['name'] == COMPANY]
    offer, = json.loads((output / 'offers.json').read_bytes())['offers']
    assert source['logo'] == offer['logo'] == 'logos/www.mavensecurities.com.png'
    assert (output / source['logo']).read_bytes() == (
        jobs.COMPANY_LOGO_DIR / 'www.mavensecurities.com.png').read_bytes()


def test_nominal_international_internships_and_graduate_keep_date_meanings(feed):
    request = feed({'jobs': [row(), row(7806970,
        title='London Trader Summer Internship 2027', location={'name': 'London'}),
        row(8352763, title='Graduate Floor Trader 2027', location={'name': 'Chicago'},
            first_published='2026-11-11T09:38:33-05:00',
            content='Options market making. Training beginning on 6th September 2027.')],
        'meta': {'total': 3}})
    found = collect()
    assert [(j.location, j.kind, j.start_period) for j in found] == [
        ('Amsterdam', 'Stage', '2027-06-21'), ('London', 'Stage', '2027-06-21'),
        ('Chicago', 'Graduate', '6th September 2027')]
    assert [j.published for j in found] == ['2026-09-01', '2026-09-01', '2026-11-11']
    assert all(j.company == COMPANY and not j.published_inferred and not j.deadline
               and jobs._eligible_offer(j) for j in found)
    assert all('<p>' not in j.description for j in found)
    request.assert_called_once_with(
        f'https://boards-api.greenhouse.io/v1/boards/{SLUG}/jobs',
        params={'content': 'true'}, timeout=(8, 20))


@pytest.mark.parametrize('text,expected', [
    ('Programme dates: 21st June – 20th August 2027', '2027-06-21'),
    ('Program dates: 1 June - 3 August 2027', '2027-06-01'),
    ('Programme dates: 31st June – 20th August 2027', ''),
    ('Programme dates: 21st September – 20th August 2027', ''),
    ('Graduation dates: 21st June – 20th August 2028', ''),
    ('Application dates: 21st June – 20th August 2026', ''),
    ('Summer 2027. Graduating June 2028. Nine weeks.', ''),
])
def test_explicit_programme_dates_are_not_graduation_or_deadline(text, expected):
    assert jobs._start_period(text) == expected


@pytest.mark.parametrize('published', [None, '', 'bad', '2026-02-30', '2099-01-01'])
def test_unknown_publication_never_uses_update_or_graduation(feed, published):
    feed({'jobs': [row(first_published=published, content='Graduating June 2028. Summer 2027.')]})
    job, = collect()
    assert job.published == job.start_period == job.deadline == ''


@pytest.mark.parametrize('deadline,retained', [('2026-11-14', False), ('2026-11-15', True),
    ('2026-11-16', True), (None, True)])
def test_expired_postings_are_removed(feed, deadline, retained):
    feed({'jobs': [row(application_deadline=deadline)]})
    found = collect()
    assert bool(found) is retained
    if retained:
        assert found[0].deadline == (deadline or '')


@pytest.mark.parametrize('title', ['Senior Trader', 'Quantitative Developer',
    'Platform Engineer Intern', 'Middle Office Trading Intern', 'Operations Intern'])
def test_unrelated_and_unconfirmed_contracts_are_excluded(feed, title):
    feed({'jobs': [row(title=title)]})
    assert collect() == []


@pytest.mark.parametrize('status', [403, 429, 500])
def test_http_failure_stops_without_retry_or_html_fallback(monkeypatch, status):
    response = jobs.requests.Response()
    response.status_code = status
    response.headers['Retry-After'] = '120'
    request = Mock(return_value=response)
    monkeypatch.setattr(jobs.requests, 'get', request)
    with pytest.raises(jobs.requests.HTTPError):
        collect()
    assert request.call_count == 1


def test_timeout_does_not_become_empty_success_or_trigger_fallback(monkeypatch):
    request = Mock(side_effect=jobs.requests.Timeout)
    monkeypatch.setattr(jobs.requests, 'get', request)
    with pytest.raises(jobs.requests.Timeout):
        collect()
    assert request.call_count == 1


def test_invalid_json_remains_a_reported_failure(monkeypatch):
    request = Mock(return_value=SimpleNamespace(
        raise_for_status=lambda: None, json=Mock(side_effect=ValueError('invalid JSON'))))
    monkeypatch.setattr(jobs.requests, 'get', request)
    with pytest.raises(ValueError, match='invalid JSON'):
        collect()
    assert request.call_count == 1


@pytest.mark.parametrize('payload', [None, [], {}, {'jobs': None}, {'jobs': [None]},
    {'jobs': [], 'meta': {'total': 1}}, {'jobs': [], 'meta': None},
    {'jobs': [], 'meta': {'total': True}}, {'jobs': [row(location='Amsterdam')]}])
def test_invalid_or_truncated_response_reports_failure(feed, payload):
    feed(payload)
    with pytest.raises(ValueError, match='Greenhouse'):
        collect()


def test_empty_and_incomplete_rows_do_not_invent_offers(feed):
    feed({'jobs': [], 'meta': {'total': 0}})
    assert collect() == []
    feed({'jobs': [{}, row(title=''), row(absolute_url=''), row(location=None)]})
    assert collect() == []


def test_unpaginated_api_keeps_results_past_usual_page_boundaries_and_deduplicates(feed):
    rows = [row(i, title=f'Trading Desk {chr(65 + i // 26)}{chr(65 + i % 26)} Intern')
            for i in range(1, 102)]
    request = feed({'jobs': rows + [rows[0]], 'meta': {'total': 102}})
    found = collect()
    assert len(found) == 102 and len(jobs._deduplicate_opportunities(found)) == 101
    assert request.call_count == 1


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_MAVEN_LIVE') != '1', reason='Opt-in public audit')
def test_live_api_and_each_official_public_detail():
    began = perf_counter()
    found = collect()
    elapsed = perf_counter() - began
    assert found and len(found) == len(jobs._deduplicate_opportunities(found))
    assert all(jobs._eligible_offer(j) and j.company == COMPANY for j in found)
    print(f'Maven: {len(found)} offres, {elapsed:.3f}s, aucun doublon')
    for job in found:
        assert job.url.startswith(BASE + '/jobs/')
        response = jobs.requests.get(job.url, timeout=(8, 20))
        response.raise_for_status()
        title = html.escape(job.title, quote=False)
        assert re.search(rf'<h1\b[^>]*>{re.escape(title)}</h1>', response.text)
        assert re.search(rf'<div class="job__location">.*?{re.escape(job.location)}</div>',
                         response.text, re.S)
        print(f'{job.title} | {job.location} | {job.kind} | publication={job.published} | '
              f'début={job.start_period!r} | échéance={job.deadline!r} | HTTP {response.status_code}')
