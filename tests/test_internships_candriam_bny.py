"""Public Candriam RSS and BNY Oracle integration, using synthetic responses."""
from types import SimpleNamespace

import pytest

from internships_project import internships as jobs


TITLE = 'Client Relationship Support Intern F/M'
SALES = "Starting in February 2027, you will join our Dutch Sales team in institutional asset management."
DETAIL = f'''<h1>{TITLE}</h1><h2>Contract type</h2><p>Internship</p>
<h2>Mission</h2><p>{SALES}</p><h2>Position location</h2>
<h3>Job location</h3><p>Europe, The Netherlands</p><h3>City</h3><p>Amsterdam</p>
<h2>Candidate criteria</h2><p>Less than 2 years</p>
<h2>Quantitative Trading Intern</h2><p>An unrelated recommended vacancy</p>'''
URL = 'https://jobs.candriam.com/Pages/Offre/detailoffre.aspx?idOffre=450&LCID=1036'


def response(*, text='', payload=None):
    return SimpleNamespace(text=text, content=text.encode(), json=lambda: payload,
                           raise_for_status=lambda: None)


def test_candriam_rss_preserves_real_title_city_date_start_and_sales_family(monkeypatch):
    feed = f'''<rss><channel><item><title>2026-450 - {TITLE}</title><link>{URL.replace('&', '&amp;')}</link>
    <pubDate>Wed, 21 Oct 2026 12:45:12 Z</pubDate><description>{SALES}</description>
    </item></channel></rss>'''
    calls=[]
    def get(url, **kwargs):
        calls.append((url,kwargs))
        return response(text=feed if url.endswith('offerRss.ashx') else DETAIL)
    monkeypatch.setattr(jobs.requests,'get',get)
    found=jobs._candriam_jobs()
    assert len(found)==1
    job=found[0]
    assert (job.title,job.location,job.kind,job.published,job.start_period,job.family)==(
        TITLE,'Amsterdam','Stage','2026-10-21','February 2027','Sales')
    assert calls[0][1]['params']['Rss_Contract']==2644
    assert jobs._eligible_offer(job)
    assert jobs._family(job.title,job.description)=='Sales'


@pytest.mark.parametrize('context', [
    'You will join our retail banking sales team selling mortgages.',
    'Our group provides asset management. You will join our middle office and support our sales team.',
    'You will join our operations team in asset management and support our sales team.',
    'Our group has an asset management business and a sales team. This internship handles settlements.',
])
def test_client_relationship_needs_its_own_asset_management_sales_desk(context):
    assert not jobs._opportunity(TITLE,'Candriam','Amsterdam','Internship',URL,'',role_context=context)


def test_candriam_detail_failure_does_not_report_empty_success(monkeypatch):
    feed=f'<rss><channel><item><title>{TITLE}</title><link>{URL.replace("&", "&amp;")}</link><description>{SALES}</description></item></channel></rss>'
    def get(url, **kwargs):
        if url.endswith('offerRss.ashx'):
            return response(text=feed)
        raise jobs.requests.ReadTimeout()
    monkeypatch.setattr(jobs.requests,'get',get)
    with pytest.raises(jobs.requests.ReadTimeout):
        jobs._candriam_jobs()


def test_bny_oracle_pages_and_str_fields_preserve_start_and_description(monkeypatch):
    calls=[]
    class Session:
        def __init__(self): self.headers={}
        def get(self,url,**kwargs):
            calls.append((url,kwargs))
            if '/hcmUI/' in url:
                return response(text='{"siteNumber":"BNY-Careers"}')
            if url.endswith('/recruitingCEJobRequisitionDetails'):
                assert kwargs['params']['finder']=='ById;Id=2027,siteNumber=BNY-Careers'
                return response(payload={'items':[{'ExternalDescriptionStr':
                    'You will work on the FX sales desk. Starting in June 2027. ' * 3}]})
            offset=100 if 'offset=100' in kwargs['params']['finder'] else 0
            rows=([{'Id':str(i),'Title':'Middle Office Intern','PrimaryLocation':'London'} for i in range(100)]
                  if offset==0 else [{'Id':'2027','Title':'2027 BNY Markets Summer Internship',
                    'PrimaryLocation':'London, United Kingdom','WorkerType':None,'ContractType':None,
                    'PostedDate':'2026-11-10','ShortDescriptionStr':'Work on our sales and trading desks.'}])
            return response(payload={'items':[{'TotalJobsCount':101,'requisitionList':rows}]})
    monkeypatch.setattr(jobs.requests,'Session',Session)
    monkeypatch.setattr(jobs,'_cached_detail',lambda job: None)
    found=jobs._oracle_jobs('BNY',jobs.ORACLE_CAREER_BOARDS['BNY'])
    assert len(found)==1 and found[0].kind=='Stage'
    assert found[0].start_period=='June 2027' and 'FX sales desk' in found[0].description
    assert found[0].published=='2026-11-10'
    assert any('offset=100' in str(kwargs) for _,kwargs in calls)
    assert jobs._family('2027 BNY Trade Execution Internship')=='Trading / Structuring'


def test_new_source_hosts_are_exact_and_public_only():
    for host in ('jobs.candriam.com','eofe.fa.us2.oraclecloud.com'):
        assert jobs.is_trusted_offer_url('https://'+host+'/job/123')
        assert not jobs.is_trusted_offer_url('https://'+host+'.evil.invalid/job/123')
        assert not jobs.is_trusted_offer_url('https://user:secret@'+host+'/job/123')
    assert 'Candriam' in jobs.CAREER_PORTALS and 'BNY' in jobs.CAREER_PORTALS
