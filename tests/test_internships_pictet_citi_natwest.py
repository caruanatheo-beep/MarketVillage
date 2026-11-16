"""Public source coverage, independent posting/start dates and scope guards."""
from types import SimpleNamespace

import pytest

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog


def reply(payload=None, text='', status=200):
    return SimpleNamespace(status_code=status, content=text.encode(), json=lambda: payload,
                           raise_for_status=lambda: None)


def test_sources_registered_and_pictet_classified_as_asset_manager():
    catalog = {source['name']: source for source in public_source_catalog()}
    assert {'Citi', 'NatWest Markets', 'Pictet Asset Management'} <= catalog.keys()
    assert catalog['Pictet Asset Management']['category'] == 'Gestion d’actifs'


def test_citi_scans_every_family_beyond_capped_global_catalogue(monkeypatch):
    calls = []
    def post(url, json, **kwargs):
        facet = json['appliedFacets'].get('jobFamilyGroup', [''])[0]
        offset = json['offset']; calls.append((facet, offset))
        if not facet:
            return reply({'total': 2000, 'jobPostings': [], 'facets': [{
                'facetParameter': 'jobFamilyGroup', 'values': [{'id': 'campus'}, {'id': 'sales'}]}]})
        rows = [dict(title='Accountant', locationsText='Paris', externalPath=f'/job/Paris/{facet}_{i}')
                for i in range(offset, min(21, offset + 20))]
        if offset == 20:
            rows[0]['title'] = 'Markets Sales Off-Cycle Internship'
        return reply({'total': 21 if offset == 0 else 0, 'jobPostings': rows})
    monkeypatch.setattr(jobs.requests, 'post', post)
    monkeypatch.setattr(jobs.requests, 'get', lambda *a, **k: reply({'jobPostingInfo': {
        'startDate': '2026-10-19', 'location': 'Paris',
        'jobDescription': 'Internship starting from January 2027 on the institutional sales desk.'}}))
    monkeypatch.setattr(jobs, '_cached_detail', lambda job: None)
    found = jobs._workday_jobs('Citi', jobs.WORKDAY['Citi'])
    assert set(calls) == {('', 0), ('campus', 0), ('campus', 20), ('sales', 0), ('sales', 20)}
    assert len(found) == 2
    assert all(j.published == '2026-10-19' and j.start_period == 'January 2027' for j in found)


@pytest.mark.parametrize('payload', [
    {'total': 2000, 'jobPostings': []},
    {'total': 2000, 'jobPostings': [], 'facets': [{'facetParameter': 'jobFamilyGroup', 'values': [{'id': 'sales'}]}]},
])
def test_citi_missing_facets_or_capped_family_is_not_success(monkeypatch, payload):
    monkeypatch.setattr(jobs.requests, 'post', lambda *a, **k: reply(payload))
    with pytest.raises(ValueError):
        jobs._workday_jobs('Citi', jobs.WORKDAY['Citi'])


@pytest.mark.parametrize('team,role', [('Your team','Your role'), ('Votre équipe','Votre rôle')])
def test_pictet_reads_explicit_internship_metadata_without_session_link(monkeypatch, team, role):
    text = f'<h2>{team}</h2><p>Pictet Asset Management. Ce stage est basé à Paris.</p><h2>{role}</h2>'
    text += '<p>Institutional fund sales. Date d’entrée: 1er janvier 2027</p>'
    monkeypatch.setattr(jobs.requests, 'get', lambda *a, **k: reply(text=text))
    job = jobs._pictet_detail({'id':'125048','title':'Assistant Sales & Marketing',
                             'meta':['125048','Posted on 18/09/2026','France','Paris']})
    assert job and job.kind == 'Stage' and job.location == 'Paris, France'
    assert job.published == '2026-09-18' and job.start_period == '1er janvier 2027'
    assert '_s.crb' not in job.url and job.url.endswith('career_job_req_id=125048')


@pytest.mark.parametrize('team,title', [
    ('Pictet Wealth Management', 'Sales Intern'),
    ('FundPartner Solutions', 'Internship - Private Assets'),
    ('Pictet Asset Management', 'Middle Office Intern'),
    ('Pictet Asset Management', 'Corporate Finance Intern'),
    ('Pictet Asset Management', 'Senior Institutional Sales'),
])
def test_pictet_rejects_other_businesses_and_out_of_scope_roles(monkeypatch, team, title):
    monkeypatch.setattr(jobs.requests, 'get', lambda *a, **k: reply(text=(
        f'<h2>Your team</h2>{team}<h2>Your role</h2>Institutional fund sales.')))
    assert jobs._pictet_detail({'id':'1','title':title,
                               'meta':['1','Posted on 18/09/2026','France','Paris']}) is None


def test_pictet_expired_and_unreadable_are_distinguished(monkeypatch):
    row = {'id':'125048','title':'Sales Intern','meta':[]}
    monkeypatch.setattr(jobs.requests, 'get', lambda *a, **k: reply(text='This job cannot be viewed at the moment.'))
    assert jobs._pictet_detail(row) is None
    monkeypatch.setattr(jobs.requests, 'get', lambda *a, **k: reply(text='Loading...'))
    with pytest.raises(ValueError, match='illisible'):
        jobs._pictet_detail(row)


def test_pictet_detail_failure_preserves_partial_status(monkeypatch):
    monkeypatch.setattr(jobs, '_pictet_listing', lambda: [{'id':'1'}])
    def broken(row): raise ValueError('unreadable')
    monkeypatch.setattr(jobs, '_pictet_detail', broken)
    with pytest.raises(jobs._PartialSourceError):
        jobs._pictet_jobs()


def test_natwest_paris_start_is_not_the_posting_date():
    text = 'Our Paris office offers a 6 month internship starting from January 2027.'
    assert jobs._start_period(text) == 'January 2027'


def test_citi_filters_operations_and_reads_city_instead_of_office_name(monkeypatch):
    titles = ['Banking, Debt Capital Markets, Placement Analyst Internship, Frankfurt - Germany 2027',
              'Market Operations Junior Analyst Program Hybrid',
              'Reference Data Services Junior Analyst - Securities and Pricing',
              'Finance Product Control Junior Analyst - Markets Treasury', 'Senior Markets Sales']
    def post(url, json, **kwargs):
        return reply({'total':len(titles), 'facets':[{'facetParameter':'jobFamilyGroup','values':[{'id':'markets'}]}],
            'jobPostings':[{'title':title,'externalPath':f'/job/TAURUS/Role_{i}','locationsText':'TAURUS'}
                           for i,title in enumerate(titles)]})
    monkeypatch.setattr(jobs.requests,'post',post)
    monkeypatch.setattr(jobs.requests,'get',lambda *a,**k:reply({'jobPostingInfo':{
        'location':'TAURUS','country':{'descriptor':'Germany'},'startDate':'2026-09-16',
        'jobDescription':'Debt capital markets placement starting from January 2027.'}}))
    monkeypatch.setattr(jobs,'_cached_detail',lambda job:None)
    found = jobs._workday_jobs('Citi',jobs.WORKDAY['Citi'])
    assert len(found)==1 and found[0].location=='Frankfurt, Germany'
    assert found[0].start_period=='January 2027'


def test_pictet_other_business_with_reversed_sections_is_valid_empty(monkeypatch):
    monkeypatch.setattr(jobs.requests,'get',lambda *a,**k:reply(text=(
        '<h2>Your role</h2>Bank Pictet Internal Auditor.<h2>Your team</h2>Internal Audit.')))
    assert jobs._pictet_detail({'id':'125136','title':'Internal Auditor','meta':[]}) is None
