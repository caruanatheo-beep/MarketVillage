from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from internships_project import internships as m
from internships_project.source_coverage import SOURCE_COVERAGE


def ubs_row(number, title='2027 Internship – Global Markets Sales'):
    fields = {'jobtitle':title, 'formtext23':'France - Paris',
              'jobdescription':'Work with the rates trading desk. Start date: January 2027.',
              'lastupdated':'10-Nov-2026', 'reqid':str(number)}
    return {'Link':f'https://jobs.ubs.com/TGnewUI/Search/home/HomeWithPreLoad?partnerid=25008&siteid=5176&PageType=JobDetails&jobid={number}',
            'Questions':[{'QuestionName':key,'Value':value} for key,value in fields.items()]}


def test_ubs_uses_structured_location_start_and_real_link_not_updated_date():
    row=ubs_row(1,'2027 Intern – Advisory &amp; Sales')
    job=m._ubs_opportunity(row)
    assert job.company=='UBS' and job.kind=='Stage'
    assert job.title=='2027 Intern – Advisory & Sales'
    assert job.location=='France - Paris'
    assert job.start_period=='January 2027' and job.published==''
    assert job.url==row['Link']
    row['Link']='https://example.invalid/job'
    assert m._ubs_opportunity(row) is None


@pytest.mark.parametrize('title',[
    'Internship Middle Office Global Markets', 'Internship Corporate Finance M&A',
    'Stagiaire Corporate Lending - Origination & Execution / Credit Analyst',
    'Intern, Transaction Services Sales', 'Senior Global Markets Sales',
])
def test_new_sources_reject_support_corporate_and_permanent_roles(title):
    assert m._ubs_opportunity(ubs_row(1,title)) is None


@pytest.mark.parametrize('company', ['BBVA','ING'])
def test_workday_new_banks_include_internship_search_and_metadata(monkeypatch,company):
    terms=[]
    def post(url,json,**kwargs):
        assert url.endswith('/jobs')
        terms.append(json['searchText'])
        if company == 'BBVA' and not json['searchText'] and not json['appliedFacets']:
            return SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'total':0,'jobPostings':[],
                'facets':[{'facetParameter':'workerSubType','values':[{'id':'intern-contract','descriptor':'Trainees / Interns'}]}]})
        rows=[dict(title='Internship Rates Sales',locationsText='Paris',externalPath='/job/Paris/Sales_1')]
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'total':1,'jobPostings':rows})
    monkeypatch.setattr(m.requests,'post',post)
    monkeypatch.setattr(m.requests,'get',lambda *a,**kw:SimpleNamespace(raise_for_status=lambda:None,
        json=lambda:{'jobPostingInfo':{'location':'Paris','jobDescription':'Start date: January 2027.'}}))
    monkeypatch.setattr(m,'_cached_detail',lambda j:None)
    job,=m._workday_jobs(company,m.WORKDAY[company],_client=m.requests)
    assert set(terms) == {''}
    assert job.company==company and job.start_period=='January 2027'
    assert m.is_trusted_offer_url(job.url)


def test_bbva_reuses_session_and_collects_contract_only_internships(monkeypatch):
    calls=[]
    response=lambda payload:SimpleNamespace(raise_for_status=lambda:None,json=lambda:payload)
    class Session:
        def __enter__(self):return self
        def __exit__(self,*args):calls.append('closed')
        def post(self,url,json,**kwargs):
            calls.append(json)
            if json['appliedFacets']:
                assert json['appliedFacets']=={'workerSubType':['intern-contract']}
                return response({'total':2,'jobPostings':[
                    {'title':'Rates Sales','locationsText':'Paris','externalPath':'/job/Paris/Sales_1'},
                    {'title':'Middle Office','locationsText':'Paris','externalPath':'/job/Paris/MO_2'}]})
            return response({'total':0,'jobPostings':[], 'facets':[
                {'facetParameter':'workerSubType','values':[
                    {'id':'permanent','descriptor':'Regular (Undefined)'},
                    {'id':'intern-contract','descriptor':'Trainees / Interns'}]}]})
        def get(self,*args,**kwargs):return response({'jobPostingInfo':{'jobDescription':'Start date: January 2027.'}})
    monkeypatch.setattr(m.requests,'Session',Session)
    monkeypatch.setattr(m,'_cached_detail',lambda j:None)
    job,=m._workday_jobs('BBVA',m.WORKDAY['BBVA'])
    assert job.title=='Rates Sales' and job.kind=='Stage'
    assert job.employment=='Internship' and m._eligible_offer(job)
    assert calls[-1]=='closed'
    assert len([c for c in calls if isinstance(c,dict)])==2


def test_workday_second_page_failure_keeps_first_page(monkeypatch):
    monkeypatch.setattr(m.time, 'sleep', lambda seconds: None)
    def post(url,json,**kwargs):
        if json['offset'] >= 20: raise m.requests.Timeout('temporary')
        rows=[dict(title='Rates Sales Intern', locationsText='Paris', externalPath=f'/job/Paris/Sales_{i}') for i in range(20)]
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'total':40,'jobPostings':rows})
    monkeypatch.setattr(m.requests,'post',post)
    monkeypatch.setattr(m.requests,'get',lambda *a,**kw:SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'jobPostingInfo':{}}))
    monkeypatch.setattr(m,'_cached_detail',lambda job:None)
    with pytest.raises(m._PartialSourceError) as error:
        m._workday_jobs('ING',m.WORKDAY['ING'])
    assert len(error.value.jobs)==20 and error.value.preserve_cached


def test_bbva_missing_contract_filter_is_not_successfully_empty():
    client=SimpleNamespace(post=lambda *a,**k:SimpleNamespace(raise_for_status=lambda:None,
                           json=lambda:{'total':0,'jobPostings':[]}))
    with pytest.raises(ValueError,match='Filtre de stages BBVA'):
        m._workday_jobs('BBVA',m.WORKDAY['BBVA'],_client=client)


@pytest.mark.parametrize('failure',[False,True])
def test_ubs_paginates_without_visible_browser_and_keeps_partial_results(monkeypatch,failure):
    from playwright import sync_api
    first={'JobsCount':2,'Jobs':{'Job':[ubs_row(1)]}}
    second={'JobsCount':2,'Jobs':{'Job':[ubs_row(2,'Internship Quantitative Research')]}}
    class Pending:
        def __init__(self,payload):
            self.value=SimpleNamespace(json=lambda:payload)
        def __enter__(self):return self
        def __exit__(self,*args):pass
    page=Mock()
    page.goto.return_value=SimpleNamespace(status=200)
    page.expect_response.side_effect=[Pending(first),TimeoutError('second page') if failure else Pending(second)]
    browser=Mock();browser.new_page.return_value=page
    chromium=Mock();chromium.launch.return_value=browser
    class Playwright:
        def __enter__(self):return SimpleNamespace(chromium=chromium)
        def __exit__(self,*args):pass
    monkeypatch.setattr(sync_api,'sync_playwright',Playwright)
    if failure:
        with pytest.raises(m._PartialSourceError) as error:m._ubs_jobs()
        assert len(error.value.jobs)==1 and error.value.preserve_cached
    else:
        assert len(m._ubs_jobs())==2
        page.locator.assert_called_with('#showMoreJobs')
    chromium.launch.assert_called_once_with(headless=True)
    browser.close.assert_called_once()


def test_ubs_overlapping_pages_do_not_duplicate_offers(monkeypatch):
    from playwright import sync_api
    first={'JobsCount':2,'Jobs':{'Job':[ubs_row(1)]}}
    # Some career boards repeat the last row when the next page is loaded.
    second={'JobsCount':2,'Jobs':{'Job':[ubs_row(1),ubs_row(2,'Internship Quantitative Research')]}}
    class Pending:
        def __init__(self,payload):
            self.value=SimpleNamespace(json=lambda:payload)
        def __enter__(self):return self
        def __exit__(self,*args):pass
    page=Mock()
    page.goto.return_value=SimpleNamespace(status=200)
    page.expect_response.side_effect=[Pending(first),Pending(second)]
    browser=Mock();browser.new_page.return_value=page
    chromium=Mock();chromium.launch.return_value=browser
    class Playwright:
        def __enter__(self):return SimpleNamespace(chromium=chromium)
        def __exit__(self,*args):pass
    monkeypatch.setattr(sync_api,'sync_playwright',Playwright)
    jobs=m._ubs_jobs()
    assert len(jobs)==2
    assert len({job.url for job in jobs})==2


def test_new_banks_are_active_refresh_sources(monkeypatch):
    names=[]
    def collect(name,*args):
        names.append(name)
        return [],{'status':'empty'},''
    monkeypatch.setattr(m,'_collect_source',collect)
    monkeypatch.setattr(m,'_publish_refresh_progress',lambda *a:None)
    monkeypatch.setattr(m,'_write_source_job_cache',lambda:None)
    monkeypatch.setattr(m,'_source_checks',{})
    monkeypatch.setattr(m,'_source_counts',{})
    m._fetch_opportunities_progressive()
    for name in ('BBVA','ING','UBS'):
        assert names.count(name)==1
        assert SOURCE_COVERAGE[name].status=='connected'
