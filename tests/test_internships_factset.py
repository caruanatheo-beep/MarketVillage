"""FactSet uses the existing Workday connector; HTML fallback is not enabled."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone

import pytest
import requests
from PIL import Image

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog
from tests.test_internships_tp_icap import serve, row, detail


COMPANY = "FactSet"
BOARD = ("factset.wd108.myworkdayjobs.com", "factset", "FactSetCareers")
TITLE = "Client Solutions Associate (Internship) - France Feb 2027"


def info(**changes):
    values = dict(title=TITLE, location="France, Paris, 32 rue Blanche",
        jobDescription="<p>20-week paid Client Solutions internship. Financial markets. "
        "Fluency in French. Currently completing an M2. February - July.</p>")
    return detail(**{**values, **changes})


def setup(serve, **kwargs):
    return serve(pages={0: {"total": 1, "jobPostings": [row(title=TITLE)]}},
                 info=info(), **kwargs)


def collect():
    return jobs._workday_jobs(COMPANY, BOARD)


def test_registry_catalogue_and_official_logo():
    assert jobs.WORKDAY[COMPANY] == BOARD
    tasks = [(fn, args) for name, fn, args in jobs._opportunity_source_tasks() if name == COMPANY]
    assert tasks == [(jobs._workday_jobs, (COMPANY, BOARD))]
    source, = [s for s in public_source_catalog() if s['name'] == COMPANY]
    assert source['category'] == 'Information financière & relation clients'
    assert source['added_on'] == '2026-11-15'
    assert source['url'] == 'https://factset.wd108.myworkdayjobs.com/en-US/FactSetCareers'
    with Image.open(jobs.COMPANY_LOGO_DIR / 'www.factset.com.png') as logo:
        assert logo.format == 'PNG' and max(logo.size) <= 96
        logo.verify()


def test_nominal_metadata_and_global_query(serve):
    calls = setup(serve)
    job, = collect()
    assert (job.company, job.kind, job.family) == (COMPANY, 'Stage', 'Client Service / Financial Solutions')
    assert job.location == 'France, Paris, 32 rue Blanche'
    assert job.published == '2026-11-13' and job.deadline == ''
    assert job.start_period == 'February 2027'
    assert 'Fluency in French' in job.description
    assert calls[0][2] == {'appliedFacets': {}, 'limit': 20, 'offset': 0, 'searchText': ''}
    assert jobs._eligible_offer(job)
    assert not jobs._opportunity(TITLE, 'Other employer', 'Paris', '', job.url, '')


@pytest.mark.parametrize('status', [403, 429, 500])
def test_api_failures_have_no_retry_or_html_fallback(serve, status):
    calls = setup(serve, status=status)
    with pytest.raises(requests.HTTPError):
        collect()
    assert len(calls) == 1


@pytest.mark.parametrize('payload', [{}, [], {'total': 1}, {'total': '1', 'jobPostings': []},
    {'total': 1, 'jobPostings': []}, {'total': 1, 'jobPostings': [{}]},
    {'total': 1, 'jobPostings': [None]}, ValueError('invalid JSON'), requests.Timeout('offline')])
def test_invalid_catalogue_cannot_claim_empty_success(serve, payload):
    serve(pages={0: payload})
    with pytest.raises((ValueError, requests.RequestException)):
        collect()


def test_confirmed_empty(serve):
    serve(pages={0: {'total': 0, 'jobPostings': []}})
    assert collect() == []


@pytest.mark.parametrize('payload,status', [({}, 200), ([], 200), ({'jobPostingInfo': []}, 200),
    (info(jobDescription=''), 200), (info(canApply=None), 200), (info(location=''), 200), (info(title=''), 200),
    (info(), 403), (info(), 429), (info(), 500)])
def test_detail_failures_are_partial_and_never_listing_only(serve, payload, status):
    serve(pages={0: {'total': 1, 'jobPostings': [row(title=TITLE)]}},
          info=payload, detail_status=status)
    with pytest.raises(jobs._PartialSourceError) as failure:
        collect()
    assert not failure.value.jobs and len(failure.value.failed_urls) == 1


@pytest.mark.parametrize('text,retained', [
    ('A 6-month long foundational training program. Financial markets.', True),
    ('Entry-level position. Financial markets.', True),
    ('Financial markets. Bachelor degree.', False),
    ('At least 5 years of experience required. Entry-level position.', False),
])
def test_associate_requires_verified_early_career_evidence(serve, text, retained):
    title = 'Client Solutions Associate - San Francisco (February 2027)'
    serve(pages={0: {'total': 1, 'jobPostings': [row(title=title)]}},
          info=detail(title=title, jobDescription=text))
    found = collect()
    assert bool(found) == retained
    if found:
        assert found[0].kind == 'Graduate' and jobs._eligible_offer(found[0])
        assert jobs._deduplicate_opportunities(found) == found


def test_pagination_deduplicates_identical_paths_and_preserves_total(serve):
    first = [row(title=TITLE)] + [row(str(i), 'Accountant') for i in range(19)]
    calls = serve(pages={0: {'total': 21, 'jobPostings': first},
                         20: {'total': 0, 'jobPostings': [row(title=TITLE)]}}, info=info())
    assert len(collect()) == 1
    assert [c[2]['offset'] for c in calls if c[0] == 'POST'] == [0, 20]
    assert sum(c[0] == 'GET' for c in calls) == 1


@pytest.mark.parametrize('second', [requests.HTTPError('429'), {'total': 40, 'jobPostings': []}, 'repeat'])
def test_later_page_failure_preserves_verified_results_as_partial(serve, second):
    first = [row(title=TITLE)] + [row(str(i), 'Accountant') for i in range(19)]
    if second == 'repeat':
        second = {'total': 40, 'jobPostings': first}
    serve(pages={0: {'total': 40, 'jobPostings': first}, 20: second}, info=info())
    with pytest.raises(jobs._PartialSourceError) as failure:
        collect()
    assert len(failure.value.jobs) == 1


def test_unknown_dates_stay_unknown(serve):
    serve(pages={0: {'total': 1, 'jobPostings': [row(title='Client Solutions Internship')]}},
          info=detail(title='Client Solutions Internship', startDate='', postedOn='Posted 30+ Days Ago',
                      jobDescription='Client Solutions internship. Graduation June 2028.'))
    job, = collect()
    assert (job.published, job.start_period, job.deadline) == ('', '', '')


@pytest.mark.parametrize('title', ['Client Solutions Internship', 'Client Solutions Associate'])
@pytest.mark.parametrize('changes,status', [({'canApply': False}, 200), ({}, 404), ({}, 410),
    ({'validThrough': '2020-01-01'}, 200),
    ({'jobDescription': 'At least 5 years of experience required.'}, 200)])
def test_closed_expired_and_experienced_offers_are_excluded(serve, title, changes, status):
    serve(pages={0: {'total': 1, 'jobPostings': [row(title=title)]}},
          info=info(**{'title': title, **changes}), detail_status=status)
    assert collect() == []


def test_distinct_requisitions_survive_deduplication(serve):
    serve(pages={0: {'total': 3, 'jobPostings': [row('R1', TITLE), row('R2', TITLE), row('R1', TITLE)]}},
          info=info())
    found = collect()
    assert len(found) == len(jobs._deduplicate_opportunities(found)) == 2
    assert len(jobs._deduplicate_opportunities(found + found)) == 2


def test_all_candidates_are_verified_even_above_fifty(serve):
    pages = {offset: {'total': 51 if offset == 0 else 0,
                     'jobPostings': [row(f'R{i}', TITLE) for i in range(offset, min(offset + 20, 51))]}
             for offset in (0, 20, 40)}
    calls = serve(pages=pages, info=info())
    assert len(collect()) == 51
    assert sum(c[0] == 'GET' for c in calls) == 51


def test_abbreviated_cohort_month_is_not_a_graduation_or_publication_date():
    assert jobs._title_period(TITLE) == 'February 2027'
    assert jobs._title_period('Client Solutions Internship - Milan, Feb. 2027') == 'February 2027'
    assert jobs._title_period('Client Solutions Internship - Summer 2027') == ''


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_FACTSET_LIVE') != '1', reason='Public audit opt-in')
def test_live_public_collection():
    controls = Path('.sacha-source-controls.json')
    if controls.exists():
        data = json.loads(controls.read_text(encoding='utf-8-sig'))
        # A selection text mentioning the priority is not a pause.
        assert not any(p.get('source') == COMPANY for p in data.get('paused_sources', []))
    print('Public collection UTC', datetime.now(timezone.utc).isoformat())
    found = collect()
    assert found and any('Internship' in job.title and 'Paris' in job.location for job in found)
    assert all(jobs._eligible_offer(job) and job.description for job in found)
    assert len({job.url for job in found}) == len(found)
    assert len(jobs._deduplicate_opportunities(found)) == len(found)
    print('Verified offers:', len(found))
    for job in found:
        print(job.title, '|', job.location, '|', job.kind, '| publication=', job.published,
              '| start=', job.start_period, '| expiry=', job.deadline, '|', job.url)
