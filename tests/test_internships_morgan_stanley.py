"""Audit public du 15/11/2026, uniquement GET publics sans candidature.

Bloomberg vérifié en premier : /careers/SearchJobs/ sur bloomberg.avature.net,
HTTP 200, 337 annonces, déjà présent localement et dans le catalogue publié.
GET https://marketdesk-source-suggestions.source-suggestions.workers.dev/suggestions
avec Origin https://caruanatheo-beep.github.io : 200, propositions Bank of America
et Morgan Stanley, raisons vides. Données non fiables, aucune archive/mutation.

https://caruanatheo-beep.github.io/Internships-Offres/sources.json et offers.json :
200, updated=2026-11-15T18:49:16.583997+00:00, 67 sources / 442 offres.
92 Sales, 14 Client Service / Financial Solutions, 37 Asset Management,
111 Quant / Research, 93 Trading / Structuring, 82 Risk / Support,
13 Capital Markets. Paris 115, Singapour 59, New York 34, Londres 30,
Francfort 23, Hong Kong 18, Amsterdam 14. Aucun doublon URL, cinq groupes
titre/employeur/lieu/contrat ambigus, 272 start_month vides, 68 dates de détection.
Bloomberg et BOFA ne sont donc plus des lacunes. Morgan Stanley, BlackRock,
PIMCO, Fidelity, State Street, Euroclear et Clearstream manquent ; TP ICAP
n'a qu'un lien local de portail, HSBC reste limité à Paris. Le stock historique
quant/opérations ne justifie aucun repli vers ces métiers pour la nouvelle source.

Recommandations examinées avant découverte :
- BOFA : URL proposée /en-us/students/job-search?ref=search&start=0&rows=10&search=getAllJobs,
  portail global /en-us/job-search et /services/campusjobssearchservlet?start=0&rows=100&search=getAllJobs
  sur careers.bankofamerica.com : 200, 12 programmes, FICC Sales Tokyo et Sales
  & Trading São Paulo pertinents ; déjà collectés/publiés, pas de nouveauté.
- Morgan Stanley : https://www.morganstanley.com/careers/career-opportunities-search
  sans opportunity=sg : 200 ; lien officiel vers https://morganstanley.eightfold.ai/careers.
  Son /gen/js/pcsxPwa.ceaedf5d9f9dac50.js confirme les GET search/position_details.
  /api/pcsx/search?domain=morganstanley.com&query=&location=&start=0 : 1171 résultats,
  dix/page même avec num=100. Synonymes audités : sales, sales analyst, sales
  internship, junior sales, intern, graduate, full time analyst, institutional
  client, prime brokerage, product specialist, investment management graduate.
  Sales pages start=0,10,20 ; junior sales/graduate pages 0,10 ; intern/full time
  analyst pages 0,10,20. Recherche floue : ses résultats ne prouvent pas le métier.
  Audit mondial sans filtre, pages start=0,10,...,1170 : les premiers essais
  ont couvert 1171 références ; certains essais suivants ont rencontré des
  chevauchements de pages et une limitation HTTP 429, sans conclusion d'absence.
  Le collecteur parcourt ensuite tous les résultats mondiaux du mot Sales,
  sort_by=timestamp, sans filtre de pays, nationalité, langue ou contrat :
  610 résultats observés, vérification des références distinctes, relecture
  bornée des limites de pages qui se chevauchent, état incomplet si nécessaire.
  https://morganstanley.eightfold.ai/careers/job/549800531335?domain=morganstanley.com
  200 : Taiwan Institutional Sales (Hong Kong), FX/crédit/taux, Analyst 1–2 ans,
  mandarin/anglais, publié 30/09/2026, validThrough 29/03/2027 ; candidature
  Workday employeur vérifiée dans position_details sans la suivre.
  https://morganstanley.eightfold.ai/careers/job/549797654964?domain=morganstanley.com
  200 : FRS Financing Sales Tokyo, expiré le 03/11/2026, écarté malgré HTTP 200.
  /careers/job/549798359489 (eRates London) : expérience Associate, pas de preuve junior.
  /careers/job/549799497286 (Calvert) : 3–6 ans, hors niveau débutant.
  /careers/job/549800443675 (Prime Brokerage Sydney) : Associate non confirmé junior,
  aucune déduction d'absence des autres métiers ou programmes du groupe.
- Découverte ensuite : https://tpicap.com/careers/opportunities : 200 ; candidat
  courtage pertinent ; fiche publique 200 vérifiée :
  https://tp.wd107.myworkdayjobs.com/TP-ICAP/job/New-York/XMLNAME-2027-Global-Broking-Internship_R6046
  Global Broking Internship, New York, publié 13/11/2026, sans validThrough.
  Non retenu face à la recommandation Morgan Stanley avec un poste Institutional
  Sales junior ouvert confirmé, employeur nouveau ; pas de refus pour absence.

Une seule source ajoutée : Morgan Stanley, Banques & services titres, 15/11/2026.
Périmètre du collecteur : Sales institutionnel débutant, pas de collecte globale
des opérations, du retail, du corporate, du quant ou du trading propriétaire.
Les langues/visas/durées restent dans la description sans filtre ni estimation.
Logo officiel découvert dans les link rel=icon du portail Morgan Stanley :
https://www.morganstanley.com/etc.clientlibs/msdotcomr4/clientlibs/components/site/resources/img/favicon-196x196.png
200 image/png, 19 307 octets ; PNG vérifié par Pillow, inférieur à 512 Ko.
Publication de cette nouvelle source non confirmée par le contrôleur.
"""

import json
import os
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog


HOST = 'https://morganstanley.eightfold.ai'
ID = '549800531335'
TITLE = 'Fixed Income Division - Analyst, Taiwan Institutional Sales (Hong Kong)'
URL = f'{HOST}/careers/job/{ID}?domain=morganstanley.com'
DESCRIPTION = ('Join our Taiwan institutional client coverage Sales team, covering FX, credit and rates.\n'
               '1 - 2 years of relevant experience in markets will be valuable.\n'
               'Mandarin and English required. Visa sponsorship is not available.')


def row(identity=ID, title=TITLE):
    return {'id': int(identity), 'name': title, 'positionUrl': f'/careers/job/{identity}',
            'locations': ['Hong Kong, Hong Kong'], 'postedTs': 9999999999, 'creationTs': 1790640000}


def detail(identity=ID, title=TITLE, **overrides):
    return {'id': int(identity), 'name': title, 'positionUrl': f'/careers/job/{identity}',
            'atsJobId': 'JR044975', 'locations': ['Hong Kong, Hong Kong'],
            'positionUserActions': {'applyAction': {'status': 'link_off', 'applyUrl':
                'https://ms.wd5.myworkdayjobs.com/External/job/Hong-Kong/Sales_JR044975/apply?src=Eightfold'}},
            **overrides}


def posting(identity=ID, title=TITLE, **overrides):
    data = {'@type': 'JobPosting', 'title': title, 'url': f'{HOST}/careers/job/{identity}?domain=morganstanley.com',
            'hiringOrganization': {'name': 'Morgan Stanley'}, 'description': DESCRIPTION,
            'datePosted': '2026-09-30T00:00:00', 'validThrough': '2027-03-29T00:00:00',
            'employmentType': 'FULL_TIME', 'jobLocation': {'address': {'addressCountry': {'name': 'HK'}}},
            **overrides}
    return ('<script type="application/ld+json">' + json.dumps(data) + '</script>'
            '<footer>Related internship starts in June 2028; updated 2026-11-15</footer>')


def response(payload=None, *, text='', status=200):
    def check():
        if status >= 400:
            raise jobs.requests.HTTPError(str(status))
    return SimpleNamespace(json=lambda: payload, text=text, status_code=status, raise_for_status=check)


@pytest.fixture
def serve(monkeypatch):
    def install(rows=None, *, pages=None, details=None, postings=None):
        rows = [row()] if rows is None else rows
        pages = pages if pages is not None else {0: response({'status': 200, 'data': {'positions': rows, 'count': len(rows)}})}
        details = details or {ID: response({'status': 200, 'data': detail()})}
        postings = postings or {ID: response(text=posting())}
        def get(url, **kwargs):
            assert kwargs['allow_redirects'] is False and kwargs['timeout'] == (8, 20)
            if url == HOST + '/api/pcsx/search':
                params = kwargs['params']
                assert params == {'domain': 'morganstanley.com', 'query': 'sales', 'location': '',
                                  'start': params['start'], 'sort_by': 'timestamp'}
                result = pages[params['start']]
            elif url == HOST + '/api/pcsx/position_details':
                assert kwargs['params']['domain'] == 'morganstanley.com'
                result = details[kwargs['params']['position_id']]
            else:
                assert url.startswith(HOST + '/careers/job/') and url.endswith('?domain=morganstanley.com')
                result = postings[url.split('/job/')[1].split('?')[0]]
            if isinstance(result, Exception):
                raise result
            return result
        request = Mock(side_effect=get)
        monkeypatch.setattr(jobs.requests, 'get', request)
        return request
    return install


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 15, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(jobs, 'datetime', Clock)


def test_source_card_registration_and_official_logo():
    source, = [s for s in public_source_catalog() if s['name'] == 'Morgan Stanley']
    assert source['category'] == 'Banques & services titres' and source['added_on'] == '2026-11-15'
    assert source['url'] == 'https://www.morganstanley.com/careers/career-opportunities-search'
    assert {'name': 'Morgan Stanley Campus', 'url': jobs.CAREER_PORTALS['Morgan Stanley Campus']} in source['feeds']
    task, = [t for t in jobs._opportunity_source_tasks() if t[0] == 'Morgan Stanley']
    assert task[1] is jobs._morgan_stanley_jobs
    path = jobs.COMPANY_LOGO_DIR / (jobs.COMPANY_ICON_HOSTS['morganstanley'] + '.png')
    assert jobs._canonical_company('Morgan Stanley') == 'morganstanley'
    assert 0 < path.stat().st_size <= 512 * 1024
    with Image.open(path) as image:
        assert image.format == 'PNG' and image.size == (196, 196)
        image.verify()


@pytest.mark.parametrize('second_page', ['open', 'closed', 'unavailable'])
def test_campus_trading_uses_public_programmes_and_pagination(monkeypatch, second_page):
    board = jobs.CAREER_PORTALS['Morgan Stanley Campus']
    prefix = board.replace('/jobboard/vacancy/1/adv/', '/so/pm/1/pl/1/opp/')
    title = '2027 Institutional Equities Trading Off-Cycle Internship (Paris)'
    offer = prefix + '22033-Institutional-Equities-Trading-Paris/en-GB'
    unrelated = prefix + '22034-Technology-Internship/en-GB'
    first = f'<h2>2 results match!</h2><a href="{unrelated}">Technology Internship</a><a href="?start=1">Next page</a>'
    filtered = offer.replace('/brand-2/', '/brand-2/xf-9f4755e53574/')
    second = f'<h2>2 results match!</h2><a href="{filtered}">{title}</a>'
    detail = f'''<h1>{title}</h1><form class="form-view">
      <span class="hform_lbl_text">City</span><div>Paris</div>
      <span class="hform_lbl_text">Program</span><div>Off-Cycle Internship</div>
      <span class="hform_lbl_text">Job description</span><p>Join an equity index trading desk.</p>
      </form><form action="{prefix}22033/apply/en-GB"></form>'''
    if second_page == 'closed':
        detail = '<p>This vacancy is closed.</p>'

    def get(url, *, timeout, allow_redirects, params=None):
        assert timeout == (8, 20) and not allow_redirects
        if url == board and params is None:
            return response(text=first)
        if url == board and params == {'start': 1}:
            return response(text=second, status=503 if second_page == 'unavailable' else 200)
        assert url == offer and params is None
        return response(text=detail)

    monkeypatch.setattr(jobs.requests, 'get', get)
    if second_page == 'unavailable':
        with pytest.raises(jobs._PartialSourceError) as error:
            jobs._morgan_stanley_campus_jobs()
        assert error.value.preserve_cached
        return
    found = jobs._morgan_stanley_campus_jobs()
    if second_page == 'closed':
        assert found == []
        return
    job, = found
    assert (job.url, job.company, job.location, job.kind, job.family) == (
        offer, 'Morgan Stanley', 'Paris', 'Stage', 'Trading / Structuring')
    assert not job.published and not job.start_period
    assert jobs.is_trusted_offer_url(job.url) and jobs._eligible_offer(job)


def test_verified_junior_keeps_dates_city_languages_visa_and_real_contract(serve):
    serve()
    job, = jobs._morgan_stanley_jobs()
    assert (job.title, job.company, job.location, job.kind, job.family) == (
        TITLE, 'Morgan Stanley', 'Hong Kong, Hong Kong', 'Graduate', 'Sales')
    assert job.url == URL and job.employment == 'FULL TIME'
    assert job.published == '2026-09-30' and job.deadline == '2027-03-29'
    assert job.start_period == '' and not job.published_inferred
    assert 'Mandarin and English' in job.description and 'Visa sponsorship is not available' in job.description
    assert jobs._eligible_offer(job) and jobs._deduplicate_opportunities([job, job]) == [job]
    assert not jobs._eligible_offer(replace(job, description='Experienced institutional Sales'))


@pytest.mark.parametrize('title', ['Quant Research Summer Analyst', 'Software Developer Intern',
    'Retail Sales Graduate', 'Corporate FX Sales Analyst', 'Senior Institutional Sales Analyst',
    'Institutional Sales Vice President', 'Sales Operations Intern', 'Sales Compliance Graduate',
    'Financial Analyst - Sales Compensation & Distribution', 'Proprietary Trading Intern'])
def test_no_unrelated_fallback_or_senior_titles(serve, title):
    request = serve([row(title=title)])
    assert jobs._morgan_stanley_jobs() == [] and request.call_count == 1


@pytest.mark.parametrize('description', [
    'Institutional clients FX Sales. 3–6 years of relevant experience.',
    'Institutional clients FX Sales. 2+ years of relevant experience.',
    'Institutional clients FX Sales. Minimum three years of experience required.',
    'Institutional clients FX Sales. Relevant experience desired.',
    'Retail banking sales, 1 - 2 years of experience.',
])
def test_requires_institutional_scope_and_junior_evidence(serve, description):
    serve(postings={ID: response(text=posting(description=description))})
    assert jobs._morgan_stanley_jobs() == []


def test_junior_evidence_does_not_change_other_employers():
    assert jobs._kind(TITLE, 'FULL TIME') is None
    assert jobs._opportunity(TITLE, 'Citi', 'Hong Kong', 'FULL TIME',
                             'https://citi.wd5.myworkdayjobs.com/en-US/2/job/HK/Sales_R1', '',
                             role_context=DESCRIPTION) is None
    assert jobs._morgan_stanley_kind('Quantitative Analyst', 'FULL TIME', DESCRIPTION) is None


def test_explicit_junior_title_still_requires_early_career_experience(serve):
    title = 'Junior Institutional Sales Analyst'
    serve([row(title=title)], details={ID: response({'status': 200, 'data': detail(title=title)})},
          postings={ID: response(text=posting(title=title,
              description='Institutional clients FX Sales. 5 years of relevant experience.'))})
    assert jobs._morgan_stanley_jobs() == []


@pytest.mark.parametrize('employment,title,expected', [
    ('INTERN', 'Institutional Sales Internship', 'Stage'),
    ('FULL_TIME', 'Institutional Sales Graduate', 'Graduate'),
    ('FULL_TIME', 'Institutional Sales VIE', 'VIE'),
    ('APPRENTICESHIP', TITLE, None),
])
def test_confirmed_contracts(serve, employment, title, expected):
    serve([row(title=title)], details={ID: response({'status': 200, 'data': detail(title=title)})},
          postings={ID: response(text=posting(title=title, employmentType=employment))})
    found = jobs._morgan_stanley_jobs()
    assert [job.kind for job in found] == ([expected] if expected else [])


@pytest.mark.parametrize('date_value', ['', 'invalid', '2027-09-30T00:00:00'])
def test_no_publication_from_detection_or_indexing(serve, date_value):
    serve(postings={ID: response(text=posting(datePosted=date_value))})
    job, = jobs._morgan_stanley_jobs()
    assert job.published == '' and job.start_period == ''


def test_expired_accessible_offer_is_not_open(serve):
    serve(postings={ID: response(text=posting(validThrough='2026-11-03T00:00:00'))})
    assert jobs._morgan_stanley_jobs() == []


def test_unknown_expiration_and_explicit_start_and_duration(serve):
    serve(postings={ID: response(text=posting(validThrough='', jobStartDate='2027-05-01',
        description=DESCRIPTION + '\nInternship duration: 6 months.'))})
    job, = jobs._morgan_stanley_jobs()
    assert job.deadline == '' and job.start_period == '2027-05-01'
    assert '6 months' in job.description


@pytest.mark.parametrize('overrides', [
    {'title': 'Other Sales Analyst'}, {'url': URL.replace(ID, '123')},
    {'hiringOrganization': {'name': 'Other Bank'}}, {'validThrough': 'invalid'}, {'description': ''},
])
def test_mismatched_or_incomplete_metadata_reports_partial(serve, overrides):
    serve(postings={ID: response(text=posting(**overrides))})
    with pytest.raises(jobs._PartialSourceError) as error:
        jobs._morgan_stanley_jobs()
    assert error.value.failed_urls == {URL}


@pytest.mark.parametrize('apply_url', [
    'http://ms.wd5.myworkdayjobs.com/External/job/HK/Sales_JR044975/apply',
    'https://ms.wd5.myworkdayjobs.com.evil.invalid/External/job/HK/Sales_JR044975/apply',
    'https://user:password@ms.wd5.myworkdayjobs.com/External/job/HK/Sales_JR044975/apply',
    'https://ms.wd5.myworkdayjobs.com/External/job/HK/Sales_JR000000/apply',
])
def test_untrusted_application_links_are_never_followed(serve, apply_url):
    data = detail(positionUserActions={'applyAction': {'status': 'link_off', 'applyUrl': apply_url}})
    request = serve(details={ID: response({'status': 200, 'data': data})})
    with pytest.raises(jobs._PartialSourceError):
        jobs._morgan_stanley_jobs()
    assert request.call_count == 2


@pytest.mark.parametrize('reference,suffix', [('JR044975', '-1'), ('PT-JR044975', ''), ('PT-JR044975', '-1')])
def test_official_workday_reference_variants(serve, reference, suffix):
    info = detail(atsJobId=reference, positionUserActions={'applyAction': {'status': 'link_off', 'applyUrl':
        f'https://ms.wd5.myworkdayjobs.com/External/job/Hong-Kong/Sales_{reference}{suffix}/apply?src=Eightfold'}})
    serve(details={ID: response({'status': 200, 'data': info})})
    job, = jobs._morgan_stanley_jobs()
    assert job.url == URL


@pytest.mark.parametrize('overrides', [{'id': 123}, {'name': 'Other Sales'},
                                     {'positionUrl': 'https://evil.invalid/offer'}, {'locations': []}])
def test_detail_identity_and_location_required(serve, overrides):
    serve(details={ID: response({'status': 200, 'data': detail(**overrides)})})
    with pytest.raises(jobs._PartialSourceError):
        jobs._morgan_stanley_jobs()


@pytest.mark.parametrize('status', [404, 410])
def test_removed_details_are_not_cached_as_open(serve, status):
    serve(details={ID: response(status=status)})
    assert jobs._morgan_stanley_jobs() == []


def test_complete_worldwide_pagination(serve):
    first = [row(str(i), 'Software Developer Intern') for i in range(1, 11)]
    pages = {0: response({'status': 200, 'data': {'positions': first, 'count': 11}}),
             10: response({'status': 200, 'data': {'positions': [row()], 'count': 11}})}
    serve(pages=pages)
    job, = jobs._morgan_stanley_jobs()
    assert job.url == URL


@pytest.mark.parametrize('second', [[], [row('1', 'Software Developer Intern')]])
def test_truncated_or_repeated_pagination_preserves_partial_results(serve, second):
    first = [row()] + [row(str(i), 'Software Developer Intern') for i in range(1, 10)]
    serve(pages={0: response({'status': 200, 'data': {'positions': first, 'count': 11}}),
                 10: response({'status': 200, 'data': {'positions': second, 'count': 11}})})
    with pytest.raises(jobs._PartialSourceError) as error:
        jobs._morgan_stanley_jobs()
    assert [job.url for job in error.value.jobs] == [URL]
    assert error.value.preserve_cached


def test_boundary_overlap_is_deduplicated_and_reread_for_missing_reference(serve):
    first = [row()] + [row(str(i), 'Software Developer Intern') for i in range(1, 10)]
    payload = lambda rows: {'status': 200, 'data': {'positions': rows, 'count': 11}}
    boundary = response()
    boundary.json = Mock(side_effect=[payload([row('1', 'Software Developer Intern')]),
                                     payload([row('10', 'Software Developer Intern')])])
    request = serve(pages={0: response(payload(first)), 10: boundary})
    job, = jobs._morgan_stanley_jobs()
    assert job.url == URL
    assert [call.kwargs['params']['start'] for call in request.call_args_list
            if call.args[0].endswith('/search')] == [0, 10, 0, 10]


@pytest.mark.parametrize('payload', [None, [], {'status': 500},
    {'status': 200, 'data': {'positions': [], 'count': -1}},
    {'status': 200, 'data': {'positions': [], 'count': True}},
    {'status': 200, 'data': {'positions': [row()], 'count': '1'}},
])
def test_invalid_catalogues_report_failure(serve, payload):
    serve(pages={0: response(payload)})
    with pytest.raises(jobs._PartialSourceError) as error:
        jobs._morgan_stanley_jobs()
    assert error.value.preserve_cached


def test_empty_valid_catalogue(serve):
    serve([])
    assert jobs._morgan_stanley_jobs() == []


def test_multi_location_offer_keeps_every_official_city(serve):
    info = detail(locations=['Hong Kong, Hong Kong', 'Singapore, Singapore', 'Hong Kong, Hong Kong'])
    serve(details={ID: response({'status': 200, 'data': info})})
    job, = jobs._morgan_stanley_jobs()
    assert job.location == 'Hong Kong, Hong Kong / Singapore, Singapore'


def test_failed_detail_does_not_discard_verified_other_offer(serve):
    other = '549800531336'
    serve([row(), row(other)], details={ID: response({'status': 200, 'data': detail()}),
                                      other: jobs.requests.Timeout('public detail timeout')})
    with pytest.raises(jobs._PartialSourceError) as error:
        jobs._morgan_stanley_jobs()
    assert [job.url for job in error.value.jobs] == [URL]
    assert error.value.failed_urls == {URL.replace(ID, other)}
    assert not error.value.preserve_cached


def test_failed_later_page_keeps_verified_results_and_cached_search(serve):
    first = [row()] + [row(str(i), 'Software Developer Intern') for i in range(1, 10)]
    serve(pages={0: response({'status': 200, 'data': {'positions': first, 'count': 11}}),
                 10: jobs.requests.Timeout('public search timeout')})
    with pytest.raises(jobs._PartialSourceError) as error:
        jobs._morgan_stanley_jobs()
    assert [job.url for job in error.value.jobs] == [URL] and error.value.preserve_cached


@pytest.mark.parametrize('where', ['search', 'api_detail', 'page_detail'])
def test_redirects_are_reported_without_following(serve, where):
    options = {'pages': {0: response(status=302)}} if where == 'search' else (
        {'details': {ID: response(status=302)}} if where == 'api_detail' else
        {'postings': {ID: response(status=302)}})
    serve(**options)
    with pytest.raises(jobs._PartialSourceError):
        jobs._morgan_stanley_jobs()


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_MORGAN_STANLEY_LIVE') != '1', reason='Public GET audit is opt-in')
def test_live_global_collection_and_public_comparison(monkeypatch):
    real_detail = jobs._morgan_stanley_detail
    real_get = jobs.requests.get
    references, search_requests = set(), []
    def audited_get(url, **kwargs):
        response = real_get(url, **kwargs)
        if url == HOST + '/api/pcsx/search':
            search_requests.append(kwargs['params']['start'])
            if response.status_code == 200:
                references.update(str(row['id']) for row in response.json()['data']['positions'])
        return response
    def checked_detail(identity, title):
        try:
            job = real_detail(identity, title)
            print(f'Fiche {identity} : {"retenue" if job else "hors cible ou expirée"} | {title}')
            return job
        except Exception as exc:
            print(f'Fiche {identity} : {type(exc).__name__}: {exc} | {title}')
            raise
    monkeypatch.setattr(jobs, '_morgan_stanley_detail', checked_detail)
    monkeypatch.setattr(jobs.requests, 'get', audited_get)
    began = perf_counter()
    found = jobs._morgan_stanley_jobs()
    elapsed = perf_counter() - began
    assert found and len(found) == len(jobs._deduplicate_opportunities(found))
    assert all(job.company == 'Morgan Stanley' and job.family == 'Sales'
               and jobs._eligible_offer(job) for job in found)
    print(f'Morgan Stanley : {len(found)} offres vérifiées, {elapsed:.3f}s, aucun doublon')
    print(f'Recherche Sales mondiale : {len(references)} références distinctes, {len(search_requests)} pages GET lues')
    for job in found:
        print(f'{job.title} | {job.location} | {job.kind} | publié={job.published!r} | '
              f'début={job.start_period!r} | échéance={job.deadline!r} | {job.url}')
    documents = {}
    for name in ('sources', 'offers'):
        r = jobs.requests.get(f'https://caruanatheo-beep.github.io/Internships-Offres/{name}.json',
                              timeout=(8, 20), allow_redirects=False)
        r.raise_for_status()
        assert r.status_code == 200
        documents[name] = r.json()
    public = {source['name'] for source in documents['sources']['sources']}
    local = {source['name'] for source in public_source_catalog()}
    offers = documents['offers']['offers']
    groups = Counter((j['title'], j['company'], j['location'], j['kind']) for j in offers)
    print(f'Catalogue public updated={documents["sources"]["updated"]} : {len(public)} sources, '
          f'{len(offers)} offres, {len(offers)-len({j["url"] for j in offers})} doublons URL, '
          f'{sum(count > 1 for count in groups.values())} groupes ambigus')
    print(f'Locaux seuls={sorted(local-public)} ; publics seuls={sorted(public-local)}')
    print(f'Métiers={dict(Counter(j["family"] for j in offers))}')
    print(f'Contrats={dict(Counter(j["kind"] for j in offers))}')
