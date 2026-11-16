"""Public bank catalogues and metadata; no account or browser required."""
import json
from types import SimpleNamespace

import pytest

from internships_project import internships as jobs


COMMERZ = 'https://jobs.commerzbank.com/index.php?ac=jobad&id=62934&language=2'
STANDARD = 'https://jobs.standardchartered.com/job/Markets-Intern-UK-2027/61048-en_GB/'


def response(text='', payload=None):
    return SimpleNamespace(content=text.encode('utf-8'), json=lambda: payload,
                           raise_for_status=lambda: None)


def commerz_detail(title='Praktikant*in Capital Markets - Bond Sales', deadline='2099-12-15'):
    structured={'@type':'JobPosting','title':title,'datePosted':'2026-10-26',
        'validThrough':deadline,'employmentType':'FULL_TIME',
        'jobLocation':{'address':{'addressLocality':'Frankfurt am Main','addressCountry':'DE'}},
        'description':'&lt;p&gt;Work on the institutional bond sales desk.&lt;/p&gt;'}
    return '<script type="application/ld+json">'+json.dumps(structured)+'</script>'+(
        '<h1>Willkommen im Team</h1><span>Datum des ersten Arbeitstages</span>'
        '<span>Datum des ersten Arbeitstages:</span><span>04.01.2027</span>')


def standard_detail(deadline='31/12/2099', title='Markets Intern UK 2027'):
    fields=[('Job Location','London, GBR'),('Employment Type','Intern'),
            ('Posting Start Date','27/08/2026'),('Posting End Date',deadline),('Start Date','June 2027')]
    return f'<meta property="og:title" content="{title}"><h1>Job Details</h1>'+''.join(
        f'<span>{label}:\xa0</span><span>{value}</span>' for label,value in fields)+(
        '<p>Placements on our sales and trading desks.</p>')


def test_commerz_german_title_repeated_labels_and_future_start(monkeypatch):
    monkeypatch.setattr(jobs.requests,'get',lambda *a,**k:response(commerz_detail()))
    job=jobs._bank_career_detail(COMMERZ,'Commerzbank')
    assert job.title=='Praktikant*in Capital Markets - Bond Sales'
    assert job.kind=='Stage' and job.family=='Sales'
    assert job.start_period=='2027-01-04' and job.published=='2026-10-26'
    assert job.deadline=='2099-12-15' and 'Frankfurt' in job.location
    assert '<p>' not in job.description and jobs._eligible_offer(job)


def test_commerz_trainee_is_graduate(monkeypatch):
    monkeypatch.setattr(jobs.requests,'get',lambda *a,**k:response(commerz_detail('Trainee Capital Markets Sales')))
    job=jobs._bank_career_detail(COMMERZ,'Commerzbank')
    assert job.kind=='Graduate' and jobs._eligible_offer(job)


@pytest.mark.parametrize('title',['Middle Office Intern','Corporate Finance Intern',
    'Application Operations Intern (Algorithmic Trading Systems)',
    'Praktikant im Segment Privat- und Unternehmerkunden - Fixed Income Solutions',
    'Senior Capital Markets Sales'])
def test_commerz_rejects_unwanted_or_permanent_roles(monkeypatch,title):
    monkeypatch.setattr(jobs.requests,'get',lambda *a,**k:response(commerz_detail(title)))
    assert jobs._bank_career_detail(COMMERZ,'Commerzbank') is None


def test_standard_uses_job_title_and_start_not_posting_start(monkeypatch):
    monkeypatch.setattr(jobs.requests,'get',lambda *a,**k:response(standard_detail()))
    job=jobs._bank_career_detail(STANDARD,'Standard Chartered')
    assert job.title=='Markets Intern UK 2027' and job.kind=='Stage'
    assert job.location=='London, GBR' and job.start_period=='June 2027'
    assert job.published=='2026-08-27' and job.deadline=='2099-12-31'
    assert job.family=='Trading / Structuring'


def test_commerz_english_working_day_uses_its_us_date_format(monkeypatch):
    page=commerz_detail('Intern Capital Markets - FX Sales')
    page=page[:page.index('<h1>')]+'<span>First working day</span><span>First working day:</span><span>5 / 1 / 2027</span>'
    monkeypatch.setattr(jobs.requests,'get',lambda *a,**k:response(page))
    job=jobs._bank_career_detail(COMMERZ,'Commerzbank')
    assert job.start_period=='2027-05-01'


def test_syndication_programmes_are_not_asset_management():
    assert jobs._family('Syndicate & Portfolio Management Intern', 'Join our Bond Syndication team.')=='Capital Markets'
    assert jobs._family('Markets Risk Intern', 'Collaborate with trading desks.')=='Risk / Support'


def test_standard_template_dates_for_other_countries_do_not_leak_into_start(monkeypatch):
    page=standard_detail().replace('June 2027','June 2027, April in India')
    monkeypatch.setattr(jobs.requests,'get',lambda *a,**k:response(page))
    assert jobs._bank_career_detail(STANDARD,'Standard Chartered').start_period=='June 2027'


@pytest.mark.parametrize('company,page,url',[
    ('Commerzbank',commerz_detail(deadline='2020-01-01'),COMMERZ),
    ('Standard Chartered',standard_detail(deadline='01/01/2020'),STANDARD)])
def test_expired_public_fiches_are_not_returned(monkeypatch,company,page,url):
    monkeypatch.setattr(jobs.requests,'get',lambda *a,**k:response(page))
    assert jobs._bank_career_detail(url,company) is None


def test_commerz_paginates_catalogue_without_following_external_links(monkeypatch):
    offsets=[];details=[]
    def post(url,**kwargs):
        offset=kwargs['json']['SearchParameters']['FirstItem'];offsets.append(offset)
        title='Middle Office Intern' if offset==1 else 'Praktikant Capital Markets Sales'
        return response(payload={'SearchResult':{'SearchResultCountAll':2,'SearchResultItems':[
            {'MatchedObjectDescriptor':{'ID':str(offset),'PositionTitle':title,'PositionURI':'https://evil.invalid'}}]}})
    monkeypatch.setattr(jobs.requests,'post',post)
    monkeypatch.setattr(jobs,'_bank_career_detail',lambda url,company:details.append(url))
    jobs._commerzbank_jobs()
    assert offsets==[1,2] and details==['https://jobs.commerzbank.com/index.php?ac=jobad&id=2&language=2']


def test_standard_sitemap_filters_before_details_and_reports_partial_failure(monkeypatch):
    urls=[STANDARD,STANDARD,'https://jobs.standardchartered.com.evil.invalid/job/Markets-Intern/1/',
          'https://jobs.standardchartered.com/job/Middle-Office-Intern/2/',
          'https://jobs.standardchartered.com/job/Senior-Sales/3/']
    sitemap='<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(
        f'<url><loc>{url}</loc></url>' for url in urls)+'</urlset>'
    monkeypatch.setattr(jobs.requests,'get',lambda *a,**k:response(sitemap))
    attempted=[]
    def fail(url,company):
        attempted.append(url)
        raise jobs.requests.ReadTimeout()
    monkeypatch.setattr(jobs,'_bank_career_detail',fail)
    with pytest.raises(jobs._PartialSourceError) as exc:
        jobs._standard_chartered_jobs()
    assert attempted==[STANDARD] and exc.value.failed_urls=={STANDARD}


def test_bank_hosts_are_exact():
    for host in ('jobs.commerzbank.com','jobs.standardchartered.com'):
        assert jobs.is_trusted_offer_url('https://'+host+'/job/1')
        assert not jobs.is_trusted_offer_url('https://'+host+'.evil.invalid/job/1')
        assert not jobs.is_trusted_offer_url('https://user:secret@'+host+'/job/1')


def test_commerz_preserves_verified_jobs_when_next_catalogue_page_fails(monkeypatch):
    def post(url,**kwargs):
        if kwargs['json']['SearchParameters']['FirstItem']>1:
            raise jobs.requests.ReadTimeout()
        return response(payload={'SearchResult':{'SearchResultCountAll':2,'SearchResultItems':[
            {'MatchedObjectDescriptor':{'ID':'1','PositionTitle':'Praktikant Capital Markets Sales'}}]}})
    monkeypatch.setattr(jobs.requests,'post',post)
    monkeypatch.setattr(jobs,'_bank_career_detail',lambda *a:'verified job')
    with pytest.raises(jobs._PartialSourceError) as exc:
        jobs._commerzbank_jobs()
    assert exc.value.jobs==['verified job'] and exc.value.preserve_cached


@pytest.mark.parametrize('company,url',[('Commerzbank',COMMERZ),('Standard Chartered',STANDARD)])
def test_http_200_challenge_is_not_reported_as_empty_success(monkeypatch,company,url):
    monkeypatch.setattr(jobs.requests,'get',lambda *a,**k:response('<h1>Please wait</h1>'))
    with pytest.raises(ValueError):
        jobs._bank_career_detail(url,company)
