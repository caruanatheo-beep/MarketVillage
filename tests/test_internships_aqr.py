"""Public-source audit, 15 November 2026; no private caches or data are used.

https://caruanatheo-beep.github.io/Internships-Offres/sources.json : 63 sources
(30 banks, 18 asset managers, 9 trading/brokers, 6 others).
https://caruanatheo-beep.github.io/Internships-Offres/offers.json : 428 offers,
90 Sales, 111 Quant/Research, 93 Trading/Structuring, 84 Risk/Support,
37 Asset Management, 13 Capital Markets; 368 internships, 51 graduate, 9 VIE.
Paris 116, Singapore 49, New York 34, London 28, Frankfurt 23, Hong Kong 18.
No repeated URL; five company/title/location/contract groups require review
before merging (distinct cohorts/requisitions may be legitimate). 261 offers
have no start month and six no known location. No existing offer was altered.
Local collectors reuse contract, role, publication and cohort deduplication
rules; some feeds restrict geography, e.g. HSBC Paris. A listed source does
not prove a currently open job. AQR, BlackRock, Nomura and AllianceBernstein
are absent from the public catalogue and the active local registries.

Suggestions GET, read only, with the same public Origin as the site:
https://marketdesk-source-suggestions.source-suggestions.workers.dev/suggestions
200 with Origin https://caruanatheo-beep.github.io (403 without Origin).
One Bloomberg suggestion, empty reason; its text was treated as untrusted data.
https://bloomberg.avature.net/careers/SearchJobs/?1686=%5B55479%5D&1686_format=2312&listFilterMode=1&jobRecordsPerPage=12
200, six visible vacancies: five news/procurement roles and BloombergNEF
Summer Internship Singapore, 46133. Energy research is less targeted than the
institutional distribution role selected. This is not a claim about all jobs
on Bloomberg's entire portal.

Candidates verified by public GET:
* AQR, selected: https://www.aqr.com/Our-Firm/Careers and
  https://careers.aqr.com/ return 200 and identify Greenhouse board aqr.
  https://boards-api.greenhouse.io/v1/boards/aqr/jobs?content=true : 200,
  48 jobs. Business Development Analyst - US Institutional, 8288686,
  Greenwich CT, explicitly 1-2 years' experience, Institutional & Global
  Consultant Relations Team, pensions/sovereign funds/endowments, distribution
  and investor relationships. https://careers.aqr.com/jobs?gh_jid=8288686
  returns 200 after an employer-host redirect; title/location match.
  Published 2026-10-22; no explicit start or expiry. This is junior institutional
  asset-management distribution, not Sales Trading; displayed in the existing
  Graduate category, which already includes junior analysts. The mixed US
  Institutional/US Wealth summer internship 7926659 is deliberately excluded,
  as are experienced, ESG-only, retail and corporate roles. One read-only GET
  collects the structured catalogue; no geographic/nationality restrictions.
* BlackRock: https://careers.blackrock.com/students-and-graduates-emea : 200.
  https://careers.blackrock.com/job/london/2027-client-and-product-summer-internship-program-emea/45831/97150826736
  and https://careers.blackrock.com/job/london/2027-client-and-product-graduate-rotational-program-emea/45831/97150826688
  both 200. Client/product rotations include institutional clients but are
  broader than the AQR role. Many listed European locations closed Sep 30,
  Oct 30 or Nov 13; Abu Dhabi (and Riyadh for the internship) remain open until
  Jan 31, 2027. A naive London/multi-location collector would publish closed
  locations. More complex collection, not selected.
* Nomura: https://careers.nomura.com/Nomura/search/?q=sales : 200,
  116 results, including JP Equity Sales Singapore and Cash Equity Sales VP
  Hong Kong. No junior contract confirmed in the inspected Sales results.
  RSS intern/graduate keyword searches also match description text and return
  many experienced/unrelated roles, so no reliable junior Sales delta claimed.
* AllianceBernstein: https://www.alliancebernstein.com/corporate/en/careers/students.html
  and https://abglobal.wd1.myworkdayjobs.com/alliancebernsteincareers : 200.
  Employer page confirms campus board abcampuscareers, but the Client Group
  programme also includes US Retail distribution. No specifically institutional
  currently open junior requisition verified, so not selected.

Only AQR is added. Existing Greenhouse collection and shared eligibility are
reused; a narrow positive team/experience check prevents broadening generic BD
or experienced roles. Runtime tests below cover expiry, dates, links and
deduplication; the opt-in public live test measures collection and validates
the actual employer page, without loading/writing application caches.
"""

import html
import json
import os
import re
from datetime import datetime, timezone
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urlparse

import pytest

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog


COMPANY = 'AQR Capital Management'
TITLE = 'Business Development Analyst - US Institutional'
URL = 'https://careers.aqr.com/jobs?gh_jid=8288686'
DESCRIPTION = (
    'AQR is a systematic investment management firm. '
    'AQR is looking to hire a full-time analyst to join our Institutional & Global '
    'Consultant Relations Team within the Business Development group. '
    'Our clients include pension funds, sovereign wealth funds and endowments. '
    'Support senior relationship managers and institutional investors. '
    'Work closely with Compliance, Legal, Operations and Trading teams. '
    '1-2 years of relevant post-undergraduate experience at an asset management firm.'
)


def row(**overrides):
    return {'id': 8288686, 'title': TITLE, 'location': {'name': 'Greenwich, CT'},
            'absolute_url': URL + '&gh_jid=8288686',
            'first_published': '2026-10-22T13:03:22-04:00',
            'updated_at': '2026-11-14T12:00:00Z', 'application_deadline': None,
            'content': html.escape('<p>' + DESCRIPTION + '</p>'), **overrides}


@pytest.fixture
def feed(monkeypatch):
    clock = Mock(wraps=datetime)
    clock.now.return_value = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(jobs, 'datetime', clock)

    def serve(rows):
        request = Mock(return_value=SimpleNamespace(
            json=lambda: {'jobs': rows}, raise_for_status=lambda: None))
        monkeypatch.setattr(jobs.requests, 'get', request)
        return request
    return serve


def collect():
    return jobs._greenhouse_jobs('aqr', COMPANY)


def test_source_is_registered_once_with_employer_link_category_and_addition_date():
    assert jobs.GREENHOUSE['aqr'] == COMPANY
    assert [(loader, args) for name, loader, args in jobs._opportunity_source_tasks()
            if name == COMPANY] == [(jobs._greenhouse_jobs, ('aqr', COMPANY))]
    source, = [s for s in public_source_catalog() if s['name'] == COMPANY]
    assert source['category'] == 'Gestion d’actifs'
    assert source['url'] == 'https://careers.aqr.com/'
    assert source['added_on'] == '2026-11-15'


def test_institutional_junior_has_original_title_location_and_publication(feed):
    request = feed([row()])
    job, = collect()
    assert job.title == TITLE and job.company == COMPANY
    assert job.family == 'Sales' and job.kind == 'Graduate'
    assert job.location == 'Greenwich, CT' and job.url == URL
    assert job.published == '2026-10-22' and not job.published_inferred
    assert job.start_period == job.deadline == ''
    assert '1-2 years' in job.description and '<p>' not in job.description
    assert jobs._eligible_offer(job)
    assert request.call_count == 1
    assert request.call_args.kwargs['params'] == {'content': 'true'}


@pytest.mark.parametrize('title', [
    '2027 Business Development Summer Analyst', 'Business Development Analyst - US Wealth',
    'Internal Sales Representative - U.S. Wealth Analyst',
    'Business Development Associate, Middle East', 'ESG Business Development Analyst - EMEA',
    'Middle Office Sales Intern', 'Back Office Trading Intern', 'Markets Operations Intern',
    'Legal Counsel Intern', 'Corporate Finance Intern', 'Senior Institutional Sales',
])
def test_unrelated_retail_mixed_rotations_and_senior_roles_are_excluded(feed, title):
    feed([row(title=title)])
    assert collect() == []


@pytest.mark.parametrize('content', [
    DESCRIPTION.replace('1-2 years', '3-5 years'),
    DESCRIPTION.replace('1-2 years', 'At least 3 years'),
    DESCRIPTION.replace('1-2 years of relevant post-undergraduate experience', 'Some experience'),
    DESCRIPTION.replace('join our Institutional & Global Consultant Relations Team',
                        'join our US Wealth Team'),
    'We provide asset management to institutional clients. 1-2 years of relevant '
    'post-undergraduate experience. You will join our Operations team.',
])
def test_junior_and_own_institutional_team_need_positive_evidence(feed, content):
    feed([row(content=content)])
    assert collect() == []


@pytest.mark.parametrize('published', [None, '', 'invalid', '2026-02-30', '2099-01-01'])
def test_unknown_publication_does_not_use_modification_date(feed, published):
    feed([row(first_published=published)])
    job, = collect()
    assert job.published == ''
    assert job.start_period == ''


@pytest.mark.parametrize('deadline,retained', [
    ('2026-11-14', False), ('2026-11-15', True), ('2026-11-16', True),
    (None, True), ('invalid', True),
])
def test_expiration_and_unknown_deadlines(feed, deadline, retained):
    feed([row(application_deadline=deadline)])
    found = collect()
    assert bool(found) is retained
    if retained:
        assert found[0].deadline == (deadline if deadline and deadline != 'invalid' else '')


def test_duplicate_rows_and_tracking_urls_collapse_in_shared_deduplication(feed):
    feed([row(), row(absolute_url='https://untrusted.invalid/ignored')])
    found = jobs._deduplicate_opportunities(collect())
    assert len(found) == 1 and found[0].url == URL


@pytest.mark.parametrize('identity', ['../other', 'https://untrusted.invalid/', 0, None])
def test_invalid_feed_identity_is_a_failure(feed, identity):
    feed([row(id=identity)])
    with pytest.raises(ValueError, match='AQR'):
        collect()


def test_invalid_catalogue_and_network_failure_are_not_empty_success(monkeypatch):
    monkeypatch.setattr(jobs.requests, 'get', lambda *a, **k: SimpleNamespace(
        json=lambda: {'jobs': None}, raise_for_status=lambda: None))
    with pytest.raises(ValueError, match='Greenhouse'):
        collect()
    monkeypatch.setattr(jobs.requests, 'get', Mock(side_effect=jobs.requests.Timeout()))
    with pytest.raises(jobs.requests.Timeout):
        collect()


@pytest.mark.parametrize('url', ['http://careers.aqr.com/jobs',
    'https://careers.aqr.com.evil.invalid/jobs', 'https://careers.aqr.com@evil.invalid/jobs'])
def test_employer_links_require_exact_https_host(url):
    assert not jobs.is_trusted_offer_url(url)


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_AQR_LIVE') != '1', reason='Opt-in public audit')
def test_live_collection_and_actual_employer_pages():
    began = perf_counter()
    found = collect()
    elapsed = perf_counter() - began
    assert found and all(job.family == 'Sales' for job in found)
    assert len(found) == len(jobs._deduplicate_opportunities(found))
    print(f'AQR: {len(found)} institutional Sales offers in {elapsed:.3f}s, no duplicates')
    for job in found:
        response = jobs.requests.get(job.url, timeout=(8, 20))
        assert response.status_code == 200
        assert urlparse(response.url).hostname == 'careers.aqr.com'
        embedded = re.search(r'data-page="([^"]+)"', response.text)
        assert embedded, 'Employer job details missing'
        posting = json.loads(html.unescape(embedded[1]))['props']['job_object']
        assert posting['title'] == job.title
        assert str(posting['unique_identifier']) in job.url
        assert job.location == posting['address']
        assert job.published == posting['date'][:10]
        assert not job.deadline or job.deadline >= datetime.now(timezone.utc).date().isoformat()
        assert jobs._eligible_offer(job)
        print(f'{job.title} | {job.location} | published={job.published} | '
              f'start={job.start_period!r} | expiry={job.deadline!r} | HTTP 200 | {job.url}')
