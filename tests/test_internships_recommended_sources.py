"""Public recommendation connectors: current vacancies, boundaries and pagination."""
from copy import deepcopy
from datetime import datetime,timezone
import json
from types import SimpleNamespace

import pytest
import requests

from internships_project import internships as m
from internships_project.source_catalog import public_source_catalog
from internships_project.source_coverage import SOURCE_COVERAGE


ADDED = ['S&P Global Market Intelligence','ICE Data Services','MarketAxess','Murex',
         'LSEG','Tradeweb','XTX Markets','Hudson River Trading','BlackRock','Mirova',
         'CPR AM','Edmond de Rothschild AM','La Banque Postale AM','PIMCO','Ostrum AM',
         'Market Securities','Intesa Sanpaolo IMI CIB','SMBC','Mizuho','RBC Capital Markets','Nomura']


def response(payload,status=200):
    def check():
        if status >= 400:
            raise requests.HTTPError(str(status))
    return SimpleNamespace(json=lambda:deepcopy(payload),status_code=status,raise_for_status=check)


@pytest.mark.parametrize('name',ADDED)
def test_recommended_employer_has_one_active_feed_and_a_dated_source_card(name):
    assert sum(source==name for source,_,_ in m._opportunity_source_tasks()) == 1
    card, = [source for source in public_source_catalog() if source['name']==name]
    assert card['added_on'] == '2026-11-17'
    assert SOURCE_COVERAGE[name].status in {'connected','shared'}
    assert m._canonical_company(name) in m.COMPANY_ICON_HOSTS


@pytest.mark.parametrize('company',['XTX Markets','Hudson River Trading','MarketAxess'])
def test_greenhouse_empty_catalogue_is_valid_and_custom_employer_links_are_trusted(monkeypatch,company):
    slug=next(key for key,name in m.GREENHOUSE.items() if name==company)
    monkeypatch.setattr(m.requests,'get',lambda *a,**k:response({'jobs':[],'meta':{'total':0}}))
    assert m._greenhouse_jobs(slug,company) == []
    host='www.hudsonrivertrading.com' if company=='Hudson River Trading' else 'www.marketaxess.com'
    assert m.is_trusted_offer_url(f'https://{host}/careers/job/?gh_jid=123')
    assert not m.is_trusted_offer_url(f'https://{host}.evil.invalid/careers/job/?gh_jid=123')


@pytest.mark.parametrize('live,division,expected',[(True,'Market Intelligence',1),(False,'Market Intelligence',0),(True,'Ratings',0)])
def test_spglobal_checks_live_detail_and_market_intelligence_division(monkeypatch,live,division,expected):
    title='Market Intelligence Sales Associate Internship'
    path='/job/London/Sales_1'
    monkeypatch.setattr(m.requests,'post',lambda *a,**k:response({'total':1,'jobPostings':[
        {'title':title,'locationsText':'London','externalPath':path}]}))
    info={'title':title,'location':'London','canApply':live,'timeType':'Full time',
          'startDate':'2026-11-17','jobDescription':f'S&P Global {division}. Internship supporting fixed income institutional clients.'}
    monkeypatch.setattr(m.requests,'get',lambda *a,**k:response({'jobPostingInfo':info}))
    jobs=m._workday_jobs('S&P Global Market Intelligence',m.WORKDAY['S&P Global Market Intelligence'])
    assert len(jobs)==expected


def test_successfactors_traverses_public_navigation_and_smbc_job_prefix(monkeypatch):
    company='SMBC';listing,host,prefix=m.CAREER_LISTINGS[company]
    url=f'https://{host}{prefix}London/Fixed-Income-Sales-Intern/123/'
    calls=[]
    def get(address,**kwargs):
        calls.append(address)
        if address==listing:
            return SimpleNamespace(text='<nav><a href="?q=&startrow=25">Next</a></nav>',raise_for_status=lambda:None)
        if 'startrow=25' in address:
            return SimpleNamespace(text=f'<a href="{url}">Fixed Income Sales Intern</a>',raise_for_status=lambda:None)
        raise AssertionError(address)
    monkeypatch.setattr(m.requests,'get',get)
    marker=m.Opportunity('Sales Intern',company,'London','Stage',url,'',50)
    monkeypatch.setattr(m,'_career_detail',lambda address,*args:marker)
    assert m._career_page_jobs(company,m.CAREER_LISTINGS[company])==[marker]
    assert len(calls)==2


def test_blackrock_reads_all_campus_pages_before_loading_programmes(monkeypatch):
    listing,host,_=m.CAREER_LISTINGS['BlackRock']
    url=f'https://{host}/job/new-york/quantitative-intern/45831/123'
    calls=[]
    def get(address,**kwargs):
        calls.append(address)
        text='<div data-total-pages="2"></div>'
        if address.endswith('/2'):
            text+=f'<a href="{url}">2027 Summer Internship Program</a>'
        return SimpleNamespace(text=text,raise_for_status=lambda:None)
    monkeypatch.setattr(m.requests,'get',get)
    marker=m.Opportunity('Quantitative Internship','BlackRock','New York','Stage',url,'',50)
    monkeypatch.setattr(m,'_career_detail',lambda *args:marker)
    assert m._career_page_jobs('BlackRock',m.CAREER_LISTINGS['BlackRock'])==[marker]
    assert calls == [listing,listing+'/2']


def ice_item(identity='123',description='ICE Data Services supplies fixed income market data.'):
    return {'data':{'slug':identity,'title':'Fixed Income Sales Intern','description':description,
                    'full_location':'London, United Kingdom','employment_type':'INTERN',
                    'posted_date':'2026-11-17T08:00:00Z','external':True,'applyable':True}}


def test_ice_paginates_and_excludes_mortgage_technology(monkeypatch):
    calls=[]
    def get(url,params,**kwargs):
        calls.append(params['page'])
        item=ice_item() if params['page']==1 else ice_item('124','ICE Mortgage Technology develops mortgage origination software.')
        return response({'jobs':[item],'totalCount':2})
    monkeypatch.setattr(m.requests,'get',get)
    job, = m._ice_data_jobs()
    assert calls==[1,2] and job.url=='https://careers.ice.com/jobs/123'
    assert job.kind=='Stage'


def test_ice_repeated_page_reports_partial_instead_of_empty_success(monkeypatch):
    monkeypatch.setattr(m.requests,'get',lambda *a,**k:response({'jobs':[ice_item()],'totalCount':2}))
    with pytest.raises(m._PartialSourceError) as error:
        m._ice_data_jobs()
    assert len(error.value.jobs)==1 and error.value.preserve_cached


@pytest.mark.parametrize('status,share,expected',[('Open','https://marketsecurities.bamboohr.com/careers/120',1),
    ('Closed','https://marketsecurities.bamboohr.com/careers/120',0)])
def test_bamboo_confirms_open_detail_and_never_collects_referral_programmes(monkeypatch,status,share,expected):
    listing=[{'id':'96','jobOpeningName':'Broker Referral Program','employmentStatusLabel':'Intern'},
             {'id':'120','jobOpeningName':'Fixed Income Broker Intern','employmentStatusLabel':'Intern'}]
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        if url.endswith('/list'):
            return response({'result':listing})
        return response({'result':{'jobOpening':{'jobOpeningShareUrl':share,'jobOpeningStatus':status,
            'jobOpeningName':'Fixed Income Broker Intern','employmentStatusLabel':'Intern',
            'description':'Assist the rates and credit broking desk.','location':{'city':'Paris','addressCountry':'France'},
            'datePosted':'2026-11-17'}}})
    monkeypatch.setattr(m.requests,'get',get)
    assert len(m._market_securities_jobs())==expected
    assert len(calls)==2 and not any('/96/' in url for url in calls)


def test_bamboo_unreadable_current_detail_is_partial_not_a_fabricated_offer(monkeypatch):
    def get(url,**kwargs):
        return response({'result':[{'id':'120','jobOpeningName':'Rates Sales Intern','employmentStatusLabel':'Intern'}]}) if url.endswith('/list') else response({})
    monkeypatch.setattr(m.requests,'get',get)
    with pytest.raises(m._PartialSourceError) as error:
        m._market_securities_jobs()
    assert error.value.failed_urls=={'https://marketsecurities.bamboohr.com/careers/120'}


def test_lbpam_uses_actual_posting_contract_location_and_publication(monkeypatch):
    page={'module':'offer','moduleLandingPage':False,'publishingDate':1794873600000,
          'tags':['CARRIERE_CONTRAT_STAGE','CARRIERE_LOCATION_PARIS'],
          'seoData':{'title':'Fixed Income Sales Intern','description':'Institutional fixed income sales internship.',
                     'canonical':'https://www.lbpam.com/fr/carrieres/offre/sales-intern'}}
    def post(url,json,**kwargs):
        assert json['moduleKeyword']=='offer' and json['nbrOfElements']==-1
        return response({'pages':[page]})
    monkeypatch.setattr(m.requests,'post',post)
    job, = m._lbpam_jobs()
    assert job.company=='La Banque Postale AM' and job.kind=='Stage' and job.location=='PARIS'
    assert job.published==datetime.fromtimestamp(page['publishingDate']/1000,timezone.utc).date().isoformat()
    page['seoData']['canonical']='https://evil.invalid/offre/sales-intern'
    assert m._lbpam_jobs()==[]


def test_bpce_brand_feed_cannot_relabel_an_unrelated_employer(monkeypatch):
    rows=[{'title':'Fixed Income Sales Intern','organization':org,'city':'Paris','jobtype':'Stage',
           'url':'https://recrutement.bpce.fr/job/sales-123/','description':'Rates and credit sales internship.'}
          for org in ['Ostrum Asset Management','Natixis CIB']]
    def get(url,params,**kwargs):
        assert params=={'where':'search(organization,"Ostrum")'}
        return response(rows)
    monkeypatch.setattr(m.requests,'get',get)
    job, = m._subsidiary_jobs('Ostrum AM')
    assert job.company=='Ostrum AM'


def test_cpr_dedicated_feed_keeps_only_explicit_cpr_employer(monkeypatch):
    jobs=[m.Opportunity('Sales Intern',company,'Paris','Stage','https://jobs.amundi.com/job/1','',50)
          for company in ['Amundi','CPR AM']]
    monkeypatch.setattr(m,'_amundi_jobs',lambda:jobs)
    assert [job.company for job in m._subsidiary_jobs('CPR AM')]==['CPR AM']
