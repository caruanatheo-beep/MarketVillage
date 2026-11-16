"""Akuna source audit, 15 November 2026, using public employer data only.

Recent additions were checked in source_catalog and the Citi/NatWest/Pictet
regressions; SOURCES.md records the earlier investigations. No private mission
history is read. Akuna, Squarepoint and Maven were absent from both local source
registries and the public sources.json/offers.json checked before this addition.

Candidates checked:
* https://boards-api.greenhouse.io/v1/boards/mavensecurities/jobs?content=true
  returned 404: no working Maven source claimed.
* https://boards-api.greenhouse.io/v1/boards/squarepointcapital/jobs?content=true
  returned 90 postings, including Intern Quant Researcher (243853). Its employer
  page returned 200 but did not expose that title in the fetched HTML; not added.
* https://boards-api.greenhouse.io/v1/boards/akunacapital/jobs?content=true
  returned 31 postings. The two accepted quant internships (8021481, 8036614)
  have employer JobPosting data confirming Chicago and datePosted 2026-07-13.
  Both advertise Summer 2027 in their titles; no precise start or closing date
  is published. The August 2028 graduation requirement is not a start date.

Verified employer pages:
https://akunacapital.com/careers/job/8021481/?gh_jid=8021481
https://akunacapital.com/careers/job/8036614/?gh_jid=8036614
The existing junior-contract filter remains unchanged; no additional junior
roles are claimed. An opt-in live check below measures the actual collector
and verifies every retained employer page, without loading or writing caches.
Initial live runner result: 2 accepted postings in 0.350 seconds, 2 unique postings,
both employer details HTTP 200; 35 tests passed with the live audit enabled.
"""

import html
import os
from datetime import datetime, timezone
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog


def posting(identity=8036614, **overrides):
    return {
        'id': identity,
        'title': 'Quantitative Research Intern, Summer 2027',
        'absolute_url': f'https://www.akunacapital.com/careers/job/{identity}/?gh_jid={identity}',
        'location': {'name': 'Chicago, IL '},
        'first_published': '2026-07-13T14:28:45-04:00',
        'updated_at': '2026-09-18T05:34:31-04:00',
        'application_deadline': None,
        'content': html.escape('<p>Develop trading strategies and quantitative models. '
                               'Must graduate by August 2028.</p>'),
        **overrides,
    }


@pytest.fixture
def feed(monkeypatch):
    clock = Mock(wraps=datetime)
    clock.now.return_value = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(jobs, 'datetime', clock)

    def serve(payload):
        request = Mock(return_value=SimpleNamespace(json=lambda: payload, raise_for_status=lambda: None))
        monkeypatch.setattr(jobs.requests, 'get', request)
        return request
    return serve


def collect():
    return jobs._greenhouse_jobs('akunacapital', 'Akuna Capital')


def test_akuna_is_one_active_trading_source_with_stable_addition_date():
    assert jobs.GREENHOUSE['akunacapital'] == 'Akuna Capital'
    tasks = [(loader, args) for name, loader, args in jobs._opportunity_source_tasks()
             if name == 'Akuna Capital']
    assert tasks == [(jobs._greenhouse_jobs, ('akunacapital', 'Akuna Capital'))]
    source = next(s for s in public_source_catalog() if s['name'] == 'Akuna Capital')
    assert source['category'] == 'Courtage & trading'
    assert source['url'] == 'https://job-boards.greenhouse.io/akunacapital'
    assert source['added_on'] == '2026-11-15'


def test_akuna_keeps_both_quant_internships_and_distinct_date_meanings(feed):
    request = feed({'jobs': [posting(), posting(8021481,
        title='Quantitative Development & Strategy Intern, Summer 2027')]})
    found = collect()
    assert len(found) == 2
    request.assert_called_once_with('https://boards-api.greenhouse.io/v1/boards/akunacapital/jobs',
                                    params={'content': 'true'}, timeout=(8, 20))
    for job in found:
        assert job.company == 'Akuna Capital' and job.kind == 'Stage'
        assert job.location == 'Chicago, IL'
        assert job.published == '2026-07-13' and not job.published_inferred
        assert job.start_period == job.deadline == ''
        assert '<p>' not in job.description and '&lt;' not in job.description
        assert 'August 2028' in job.description
        assert jobs._eligible_offer(job)


@pytest.mark.parametrize('title', [
    'Middle Office Quant Intern', 'Back Office Trading Intern', 'Markets Operations Intern',
    'Retail Banking Sales Intern', 'Legal Counsel Intern', 'Corporate Finance Intern',
    'Corporate Treasury Intern', 'Senior Quantitative Researcher', 'Platform Engineer Intern',
    'Junior Trader',  # No broadened contract inference for the existing junior filter.
])
def test_akuna_excludes_other_functions_and_unconfirmed_contracts(feed, title):
    feed({'jobs': [posting(title=title)]})
    assert collect() == []


@pytest.mark.parametrize('published', [None, '', '2026-02-30', '2099-01-01', 'not a date'])
def test_greenhouse_never_substitutes_modification_for_unknown_publication(feed, published):
    feed({'jobs': [posting(first_published=published)]})
    assert collect()[0].published == ''


def test_greenhouse_explicit_start_stays_separate_from_publication_and_graduation(feed):
    feed({'jobs': [posting(content=html.escape(
        '<p>Starting from January 2027. Must graduate by August 2028.</p>'))]})
    job = collect()[0]
    assert job.published == '2026-07-13'
    assert job.start_period == 'January 2027'


@pytest.mark.parametrize('deadline,retained', [
    ('2026-11-14T23:59:59Z', False), ('2026-11-15T23:59:59Z', True),
    ('2026-11-16T23:59:59Z', True), (None, True), ('bad date', True),
])
def test_greenhouse_excludes_expired_postings_and_retains_deadline(feed, deadline, retained):
    feed({'jobs': [posting(application_deadline=deadline)]})
    found = collect()
    assert bool(found) is retained
    if retained:
        assert found[0].deadline == (deadline[:10] if deadline and deadline.startswith('2026-') else '')


def test_akuna_duplicate_rows_merge_but_different_internships_survive(feed):
    feed({'jobs': [posting(), posting(), posting(8021481,
        title='Quantitative Development & Strategy Intern, Summer 2027')]})
    assert len(jobs._deduplicate_opportunities(collect())) == 2


@pytest.mark.parametrize('url', [
    'http://akunacapital.com/careers/job/8036614/',
    'https://akunacapital.com.evil.invalid/careers/job/8036614/',
    'https://akunacapital.com@evil.invalid/careers/job/8036614/',
])
def test_akuna_rejects_unsafe_employer_links(feed, url):
    feed({'jobs': [posting(absolute_url=url)]})
    assert collect() == []


@pytest.mark.parametrize('payload', [None, [], {}, {'jobs': None}, {'jobs': {}}, {'jobs': [None]}])
def test_invalid_greenhouse_catalogue_is_not_an_empty_success(feed, payload):
    feed(payload)
    with pytest.raises(ValueError, match='Greenhouse invalide'):
        collect()


def test_empty_current_catalogue_does_not_keep_previous_offers(feed):
    feed({'jobs': [posting()]})
    assert len(collect()) == 1
    feed({'jobs': []})
    assert collect() == []


def test_greenhouse_connection_failure_is_not_a_working_empty_source(monkeypatch):
    monkeypatch.setattr(jobs.requests, 'get', Mock(side_effect=jobs.requests.Timeout))
    with pytest.raises(jobs.requests.Timeout):
        collect()


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_AKUNA_LIVE') != '1', reason='Public live audit is opt-in')
def test_akuna_live_collection_and_employer_pages():
    began = perf_counter()
    found = collect()
    duration = perf_counter() - began
    unique = jobs._deduplicate_opportunities(found)
    assert unique and len(found) == len(unique)
    print(f'Akuna: {len(found)} accepted offers, {duration:.3f}s collection, no duplicates')
    for job in unique:
        response = jobs.requests.get(job.url, timeout=(8, 20))
        response.raise_for_status()
        assert jobs.urlparse(response.url).hostname in {'akunacapital.com', 'www.akunacapital.com'}
        structured = jobs._jsonld_jobposting(response.text)
        assert structured and html.unescape(structured['title']) == job.title
        assert str(structured['identifier']['value']) == job.url.split('gh_jid=')[-1]
        assert structured['datePosted'][:10] == job.published
        assert structured['jobLocation']['address']['addressLocality'] in job.location
        assert not structured.get('validThrough') or structured['validThrough'][:10] >= datetime.now(timezone.utc).date().isoformat()
        assert jobs._eligible_offer(job)
        print(f'{job.title} | {job.location} | published={job.published} | '
              f'start={job.start_period!r} | deadline={job.deadline!r} | HTTP {response.status_code} | {response.url}')
