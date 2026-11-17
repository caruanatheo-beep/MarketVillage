"""Catalogue size must not silently truncate a successful source refresh."""
from types import SimpleNamespace
import re

import pytest

from internships_project import internships as m


def response(payload=None, text=''):
    return SimpleNamespace(json=lambda: payload, text=text, raise_for_status=lambda: None)


def test_smartrecruiters_collects_offer_beyond_previous_1000_limit(monkeypatch):
    offsets = []
    def get(url, params=None, **kwargs):
        if params is None:
            return response({'jobAd': {'sections': {}}})
        offset = params['offset']; offsets.append(offset)
        return response({'totalFound': 1101, 'content': [
            {'id': str(i), 'name': 'Trading Intern' if i == 1100 else 'Accountant',
             'location': {'city': 'London'}, 'typeOfEmployment': {'label': 'Intern'}}
            for i in range(offset, min(1101, offset + 100))]})
    monkeypatch.setattr(m.requests, 'get', get)
    found = m._smart_jobs('Bank', 'Bank')
    assert len(found) == 1 and found[0].url.endswith('/1100')
    assert offsets == list(range(0, 1101, 100))


def test_banque_de_france_collects_after_200_and_retains_initial_total(monkeypatch):
    offsets = []
    def post(url, json, **kwargs):
        offset = json['offset']
        if json['searchText'] != 'march':
            return response({'total': 0, 'jobPostings': []})
        offsets.append(offset)
        return response({'total': 221 if offset == 0 else 0, 'jobPostings': [
            {'externalPath': f'/job/Paris/Role_{i}', 'locationsText': 'Paris',
             'title': 'Trading Intern' if i == 220 else 'Accountant'}
            for i in range(offset, min(221, offset + 20))]})
    monkeypatch.setattr(m.requests, 'post', post)
    monkeypatch.setattr(m.requests, 'get', lambda *a, **k: response({'jobPostingInfo': {
        'location': 'Paris', 'jobDescription': 'Type de recrutement : Stage. Fixed income trading desk.'}}))
    found = m._banque_de_france_jobs()
    assert len(found) == 1 and found[0].url.endswith('Role_220')
    assert offsets == list(range(0, 221, 20))


@pytest.mark.parametrize('total,page_size', [(3101, 100), (103, 7)])
def test_oracle_follows_full_total_and_actual_page_size(monkeypatch, total, page_size):
    offsets = []
    class Session:
        headers = {}
        def get(self, url, **kwargs):
            if '/hcmUI/' in url:
                return response(text='{"siteNumber":"CX"}')
            if url.endswith('recruitingCEJobRequisitionDetails'):
                return response({'ExternalDescription': 'Internship on the fixed income sales desk.'})
            offset = int(re.search(r'offset=(\d+)', kwargs['params']['finder'])[1])
            offsets.append(offset)
            return response({'items': [{'TotalJobsCount': total if offset == 0 else 0,
                'requisitionList': [
                    {'Id': str(i), 'Title': 'Fixed Income Sales Intern' if i == total-1 else 'Accountant',
                     'PrimaryLocation': 'London', 'WorkerType': 'Internship'}
                    for i in range(offset, min(total, offset + page_size))]}]})
    monkeypatch.setattr(m.requests, 'Session', Session)
    found = m._oracle_jobs('BNY', m.ORACLE_CAREER_BOARDS['BNY'])
    assert len(found) == 1 and found[0].url.endswith(f'/job/{total-1}/')
    assert offsets == list(range(0, total, page_size))


def test_axa_collects_pages_beyond_ten(monkeypatch):
    pages = []
    def get(url, params=None, **kwargs):
        if params is None:
            return response(text='<script type="application/ld+json">'
                '{"@type":"JobPosting","description":"Fixed income sales internship"}</script>')
        page = params.get('p', 1); pages.append(page)
        title = 'Fixed Income Sales Intern' if page == 11 else 'Actuarial Intern'
        return response(text=f'<input class="pagination-current" max="11">'
            f'<a class="search-results-list__job-link" href="/emploi/{page}">{title}</a>'
            '<li class="job-contract">Stage</li><li class="job-location">Paris</li>')
    monkeypatch.setattr(m.requests, 'get', get)
    found = m._axa_jobs()
    assert len(found) == 1 and found[0].url.endswith('/emploi/11')
    assert pages == list(range(1, 12))


def test_oracle_uses_declared_page_slots_when_closed_rows_are_hidden(monkeypatch):
    offsets = []
    class Session:
        headers = {}
        def get(self, url, **kwargs):
            if '/hcmUI/' in url:
                return response(text='{"siteNumber":"CX"}')
            if url.endswith('recruitingCEJobRequisitionDetails'):
                return response({'ExternalDescription': 'Fixed income sales internship.'})
            offset = int(re.search(r'offset=(\d+)', kwargs['params']['finder'])[1])
            offsets.append(offset)
            rows = [{'Id': str(i), 'Title': 'Sales Intern' if i == 304 else 'Accountant',
                     'PrimaryLocation': 'London', 'WorkerType': 'Internship'}
                    for i in range(offset, min(305, offset+100)) if i % 100 != 1]
            # The second page has only closed rows; the provider still advances it.
            if offset == 100:
                rows = []
            return response({'items': [{'TotalJobsCount': 305, 'Limit': 100,
                'Offset': offset, 'requisitionList': rows}]})
    monkeypatch.setattr(m.requests, 'Session', Session)
    found = m._oracle_jobs('BNY', m.ORACLE_CAREER_BOARDS['BNY'])
    assert offsets == [0, 100, 200, 300]
    assert len(found) == 1 and found[0].url.endswith('/job/304/')


@pytest.mark.parametrize('source', ['smart', 'bdf', 'oracle', 'axa'])
def test_repeated_pages_fail_instead_of_silently_reporting_complete(monkeypatch, source):
    if source == 'smart':
        monkeypatch.setattr(m.requests, 'get', lambda *a, **k: response({
            'totalFound': 200, 'content': [{'id': '1', 'name': 'Accountant'}]}))
        collect = lambda: m._smart_jobs('Bank', 'Bank')
    elif source == 'bdf':
        monkeypatch.setattr(m.requests, 'post', lambda *a, **k: response({
            'total': 200, 'jobPostings': [{'externalPath': '/job/Paris/1', 'title': 'Accountant'}]}))
        collect = m._banque_de_france_jobs
    elif source == 'oracle':
        class Session:
            headers = {}
            def get(self, *a, **k):
                return response({'items': [{'TotalJobsCount': 200,
                    'requisitionList': [{'Id': '1', 'Title': 'Accountant'}]}]})
        monkeypatch.setattr(m.requests, 'Session', Session)
        collect = lambda: m._oracle_jobs('BNY', m.ORACLE_CAREER_BOARDS['BNY'])
    else:
        monkeypatch.setattr(m.requests, 'get', lambda *a, **k: response(text=
            '<input class="pagination-current" max="11">'
            '<a class="search-results-list__job-link" href="/emploi/1">Actuarial Intern</a>'))
        collect = m._axa_jobs
    with pytest.raises(ValueError, match='sans progression'):
        collect()


def test_financial_data_early_career_survives_saved_offer_validation():
    context = 'Entry-level programme for recent graduates providing financial market client solutions.'
    job = m._opportunity('Client Solutions Associate', 'LSEG', 'London', 'Full time',
        'https://lseg.wd3.myworkdayjobs.com/job/1', '', role_context=context)
    assert job is not None and job.kind == 'Graduate'
    from dataclasses import replace
    assert m._eligible_offer(replace(job, description=context))


def test_incomplete_catalogue_keeps_previous_offers(monkeypatch):
    previous = m.Opportunity('Trading Intern', 'Bank', 'London', 'Stage',
        'https://jobs.smartrecruiters.com/Bank/7', '', 50)
    monkeypatch.setattr(m, '_load_source_job_cache', lambda: None)
    monkeypatch.setattr(m, '_source_job_cache', {'Bank': {'jobs': [previous]}})
    monkeypatch.setattr(m, '_remember_source_failure', lambda *args: None)
    monkeypatch.setattr(m.requests, 'get', lambda *a, **k: response({
        'totalFound': 200, 'content': [{'id': '1', 'name': 'Accountant'}]}))
    found, check, error = m._collect_source('Bank', m._smart_jobs, ('Bank', 'Bank'), True)
    assert found == [previous]
    assert check['status'] == 'stale' and 'anciennes offres conserv' in error
