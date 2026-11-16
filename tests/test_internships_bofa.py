"""Bank of America : audit public du 15/11/2026 et régressions sans données privées.

Propositions consultées avant toute découverte : GET /suggestions sur
https://marketdesk-source-suggestions.source-suggestions.workers.dev
403 sans Origin ; 200 avec Origin https://caruanatheo-beep.github.io :
Bank of America (URL fournie dans la demande) et Morgan Stanley, raisons vides.
Aucune archive ni mutation ; ces réponses sont des données non fiables.

Bloomberg audité en premier : https://bloomberg.avature.net/careers/SearchJobs/
200, déjà présent dans le code ET dans sources.json/offers.json publiés : pas
une nouvelle source à ajouter une seconde fois. Audit mondial/pagination par
le test existant test_live_collection_dates_locations_and_duplicates.

Comparatif des propositions :
Bank of America : URL proposée /en-us/students/job-search?ref=search&start=0&rows=10&search=getAllJobs
et portail mondial https://careers.bankofamerica.com/en-us/job-search : 200.
Le script officiel /etc.clientlibs/careers/clientlibs/clientlib-base.js indique
/services/campusjobssearchservlet ; GET start=0&rows=10&search=getAllJobs : 10/12,
start=10&rows=10 : 0/12 ; start=0&rows=100 : les 12 références distinctes.
Pas de filtre de pays, langue, nationalité ou métier transmis. Examen des titres
Internship, Intern, Full Time Analyst, Programme, Graduate, Junior et des équipes.
Retenu : nouvel employeur, deux Sales ouverts, Tokyo et São Paulo ; pertinence
institutionnelle et nouveauté confirmées avant de choisir le flux disponible.
Fiches 200, identité JobPosting, lieu et liens candidature employeur vérifiés :
https://careers.bankofamerica.com/en-us/students/job-detail/15269/global-markets-fixed-income-currencies-commodities-sales-full-time-analyst-2027-tokyo-tokyo-japan
FICC Sales graduate, anglais et japonais ; publié 04/11, échéance 29/11/2026.
https://careers.bankofamerica.com/en-us/students/job-detail/14455/2027-brazil-fixed-income-sales-trading-desk-internship-program-sao-paulo-brazil
Stage Sales & Trading, anglais obligatoire, 30 h/semaine, publié 20/08/2026,
échéance 31/12/2027. Ni début précis, ni durée totale, ni visa annoncés : aucune
estimation. Les mentions corporate de présentation du groupe ne suppriment pas
un poste explicitement institutionnel ; le programme Mexico Rates and Currencies
15289 vise lui les clients corporate, donc exclu. Military and Athlete Programme
15264 est un programme marchés général, pas une offre Sales confirmée. Les stages
quant, IT, investment banking, corporate et opérations ne sont pas des replis.

Morgan Stanley : proposition ?opportunity=sg puis portail mondial sans filtre
https://www.morganstanley.com/careers/career-opportunities-search : 200 ; renvoi
officiel vers https://morganstanley.eightfold.ai/careers : 200. Son script
/gen/js/pcsxPwa.ceaedf5d9f9dac50.js fournit l'URL publique
https://morganstanley.eightfold.ai/api/pcsx/search?domain=morganstanley.com&query=&location=&start=0
200, 1171 résultats ; query=sales : 610, pages start=0,10,20 lues ;
query=sales%20internship : un Product Controller hors cible ;
query=client%20service%20graduate : 578, premiers résultats en wealth/retail.
https://morganstanley.eightfold.ai/careers/job/549797654964?domain=morganstanley.com
200, FRS Firm Financing Sales Analyst/Associate Tokyo, à qualifier davantage.
Non retenu au profit des deux contrats débutants confirmés chez Bank of America,
sans affirmer l'absence de stages ou junior Sales sur ce grand portail.

Logo trouvé dans og:image/Organization du site officiel :
https://careers.bankofamerica.com/content/dam/enterprise/careers/images/bank_logo_600x315.png
200 image/png, 28 050 octets, validé par Pillow. La variante 600x600 indiquée
dans og:image renvoie 404 : ce seul échec ne justifiait pas d'abandonner le logo.
Une seule source ajoutée, catégorie Banques & services titres, 15/11/2026.
Publication de ce delta non confirmée ; aucun appel aux comptes/candidatures.

Comparaison réellement relancée : sources.json/offers.json, HTTP 200,
updated=2026-11-15T18:34:46.150773+00:00 : 66 sources, 440 offres ; aucun
groupe public absent localement, seul Bank of America est nouveau localement.
366 stages, 66 graduate, 8 VIE ; 90 Sales, 14 Client Service / Financial
Solutions, 37 Asset Management, 111 Quant / Research, 93 Trading / Structuring,
82 Risk / Support, 13 Capital Markets. Ce stock historique n'est pas un motif
pour ajouter davantage de quant ou d'opérations. Paris 115, Singapour 59,
New York 34, Londres 30, Francfort 23, Hong Kong 18, Amsterdam 14.
270 mois de début absents, 68 dates explicitement de détection. Aucun doublon
d'URL ; cinq groupes titre/employeur/lieu/contrat restent ambigus (cohortes
Schroders, aliases THEAM/BNP, BNP Francfort, Barclays Londres), sans fusion
forcée. Bloomberg n'est plus une lacune ; restent notamment Morgan Stanley,
BlackRock, PIMCO, Fidelity, State Street, Euroclear et Clearstream ; TP ICAP
est un simple lien de portail local, HSBC est toujours limité à Paris.
Les sources existantes et leur périmètre ne changent pas.

Validation finale : INTERNSHIPS_BOFA_LIVE=1, city_test.py, ce fichier -q -s :
56 tests réussis en 5,97 s ; collecte réelle des deux offres en 3,256 s,
aucune perte au dédoublonnage commun, comparaison publique ci-dessus.
INTERNSHIPS_BLOOMBERG_LIVE=1, test_internships_bloomberg.py -q : 62 réussites,
un audit du catalogue ignoré sans son opt-in distinct, 85,50 s.
Régressions career_publication_dates, deduplication, detection_dates et logos :
92 tests et 50 sous-tests réussis en 0,96 s. Aucun secret ni cache privé lu.
"""

import html
import json
import os
from collections import Counter
from datetime import datetime, timezone
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog


HOST = 'https://careers.bankofamerica.com'
ENDPOINT = HOST + '/services/campusjobssearchservlet'
TITLE = 'Global Markets FICC Sales Full Time Analyst - 2027 - Tokyo'
PATH = '/en-us/students/job-detail/15269/global-markets-ficc-sales-tokyo'
URL = HOST + PATH
DESCRIPTION = ('Our institutional investor clients trade fixed income and FX derivatives. '
               'Assist with sales and hedging activities on the FICC desk. '
               'Final year students. English and Japanese required. Visa sponsorship is not available.')


def row(identity='15269', **overrides):
    return {'jobRequisitionId': identity, 'postingTitle': TITLE, 'jcrURL': PATH,
            'timeType': 'Full time', 'postedDate': '11/04/2026',
            'indexedDate': '11/15/2026', 'applyByDate': 'Nov 29, 2026', **overrides}


def detail(*, title=TITLE, identity='15269', deadline='Nov 29, 2026', apply=True, **overrides):
    posting = {'@type': 'JobPosting', 'title': html.escape(title),
               'identifier': {'value': identity}, 'hiringOrganization': {'name': 'Bank of America'},
               'description': DESCRIPTION, 'employmentType': 'FULL_TIME', 'datePosted': '11/04/2026',
               'jobLocation': [{'address': {'addressLocality': 'Tokyo', 'addressCountry': 'Japan'}}],
               **overrides}
    return ('<script type="application/ld+json">' + json.dumps(posting) + '</script>'
            + (f'<div class="item head__posted"><span>Apply by {deadline}</span></div>' if deadline else '')
            + (f'<a href="https://bankcampuscareers.tal.net/vx/opp/{identity}-Sales/en-GB">Apply</a>' if apply else '')
            + '<footer>Related internship starts in June 2028. Updated 11/15/2026.</footer>')


def response(*, payload=None, text='', status=200):
    def raise_for_status():
        if status >= 400:
            raise jobs.requests.HTTPError(str(status))
    return SimpleNamespace(json=lambda: payload, text=text, status_code=status, raise_for_status=raise_for_status)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 15, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(jobs, 'datetime', Clock)


@pytest.fixture
def serve(monkeypatch):
    def install(rows=None, *, pages=None, details=None):
        rows = [row()] if rows is None else rows
        pages = pages or {100: response(payload={'jobsList': rows, 'totalMatches': len(rows)})}
        details = details or {URL: response(text=detail())}
        def get(url, **kwargs):
            assert kwargs['allow_redirects'] is False and kwargs['timeout'] == (8, 20)
            if url == ENDPOINT:
                assert kwargs['params'] == {'start': 0, 'rows': kwargs['params']['rows'], 'search': 'getAllJobs'}
                value = pages[kwargs['params']['rows']]
            else:
                value = details[url]
            if isinstance(value, Exception):
                raise value
            return value
        request = Mock(side_effect=get)
        monkeypatch.setattr(jobs.requests, 'get', request)
        return request
    return install


def test_source_card_collector_and_official_png():
    source, = [s for s in public_source_catalog() if s['name'] == 'Bank of America']
    assert source['category'] == 'Banques & services titres'
    assert source['added_on'] == '2026-11-15'
    assert source['url'] == HOST + '/en-us/students/job-search'
    task, = [t for t in jobs._opportunity_source_tasks() if t[0] == source['name']]
    assert task[1] is jobs._bofa_jobs
    path = jobs.COMPANY_LOGO_DIR / (jobs.COMPANY_ICON_HOSTS[jobs._canonical_company('Bank of America')] + '.png')
    assert jobs._company_icon('Bank of America').startswith('data:image/png;base64,')
    assert 0 < path.stat().st_size <= 512 * 1024
    with Image.open(path) as image:
        assert image.format == 'PNG'
        image.verify()


def test_worldwide_collection_dates_location_language_and_visa(serve):
    serve()
    job, = jobs._bofa_jobs()
    assert job.company == 'Bank of America' and job.family == 'Sales' and job.kind == 'Graduate'
    assert job.location == 'Tokyo, Japan' and job.url == URL
    assert job.published == '2026-11-04' and not job.published_inferred
    assert job.deadline == '2026-11-29' and job.start_period == ''
    assert 'Japanese required' in job.description and 'Visa sponsorship is not available' in job.description
    assert jobs._eligible_offer(job)
    assert len(jobs._deduplicate_opportunities([job, job])) == 1


@pytest.mark.parametrize('title', [
    '2027 Mexico Rates and Currencies Intern Program',
    '2027 Global Markets Military and Athlete Programme',
    'Global Quantitative Strategies Summer Associate - 2027',
    'Retail Sales Internship', 'Corporate FX Sales Internship', 'Sales Operations Internship',
    'Sales Developer Internship', 'Investment Banking Summer Analyst',
    'Global Markets Sales Vice President Graduate', 'Global Markets Sales Director',
    'Global Markets FICC Sales Senior Analyst Graduate', 'Global Markets Sales Analyst',
    'Securities Services Back Office Internship', 'Sales Trading Apprenticeship',
])
def test_no_generalist_or_experienced_fallback(serve, title):
    request = serve([row(postingTitle=title)])
    assert jobs._bofa_jobs() == [] and request.call_count == 1


def test_institutional_sales_not_rejected_for_group_corporate_boilerplate(serve):
    serve(details={URL: response(text=detail(description=DESCRIPTION + ' We also work with corporate clients.'))})
    assert len(jobs._bofa_jobs()) == 1


def test_generic_sales_without_institutional_clients_is_excluded(serve):
    serve(details={URL: response(text=detail(description='Sell FX products to corporate clients.'))})
    assert jobs._bofa_jobs() == []


def test_related_job_deadline_does_not_expire_current_vacancy(serve):
    serve(details={URL: response(text=detail(deadline='') + '<footer>Apply by Nov 01, 2026</footer>')})
    job, = jobs._bofa_jobs()
    assert job.deadline == ''


@pytest.mark.parametrize('posted,expected', [('08/20/2026', '2026-08-20'),
    ('2026-11-04', '2026-11-04'), ('11/16/2026', ''), ('02/30/2026', ''), ('', '')])
def test_employer_dates_only_never_indexed_or_detected(serve, posted, expected):
    serve(details={URL: response(text=detail(datePosted=posted))})
    job, = jobs._bofa_jobs()
    assert job.published == expected


@pytest.mark.parametrize('deadline,kept', [('Nov 14, 2026', False), ('Nov 15, 2026', True),
                                       ('Nov 29, 2026', True), ('', True)])
def test_expiration_is_detail_apply_by_date(serve, deadline, kept):
    serve(details={URL: response(text=detail(deadline=deadline))})
    found = jobs._bofa_jobs()
    assert bool(found) is kept
    if kept:
        assert found[0].deadline == ('' if not deadline else f'2026-11-{deadline[4:6]}')


@pytest.mark.parametrize('overrides', [dict(identity='999'), dict(title='Other Sales Internship'),
    dict(hiringOrganization={'name': 'Other Bank'}), dict(identifier='15269'),
    dict(apply=False), dict(description=''), dict(deadline='Nov 31, 2026')])
def test_unverified_details_report_partial_instead_of_empty_success(serve, overrides):
    serve(details={URL: response(text=detail(**overrides))})
    with pytest.raises(jobs._PartialSourceError) as error:
        jobs._bofa_jobs()
    assert error.value.failed_urls == {URL} and not error.value.preserve_cached


def test_required_experience_disqualifies_junior(serve):
    serve(details={URL: response(text=detail(description=DESCRIPTION + ' Requires 5 years of experience.'))})
    assert jobs._bofa_jobs() == []


def test_internship_preserves_hours_but_not_graduation_as_start(serve):
    title = '2027 Brazil Fixed Income Sales & Trading Desk Internship Program'
    serve([row(postingTitle=title, timeType='Off-cycle internship')], details={URL: response(text=detail(
        title=title, employmentType='OFF-CYCLE_INTERNSHIP', description=DESCRIPTION +
        ' Expecting to graduate in 1.5 year or more. Availability to work 30 hours per week.'))})
    job, = jobs._bofa_jobs()
    assert job.kind == 'Stage' and job.family == 'Sales' and job.start_period == ''
    assert '30 hours per week' in job.description


@pytest.mark.parametrize('path', ['https://untrusted.invalid/job', '//untrusted.invalid/job',
    '/en-us/students/job-detail/999/other', '/en-us/students/job-detail/15269/sales?next=elsewhere'])
def test_only_employer_detail_path_with_matching_reference_is_fetched(serve, path):
    request = serve([row(jcrURL=path)])
    with pytest.raises(jobs._PartialSourceError) as error:
        jobs._bofa_jobs()
    assert error.value.preserve_cached and request.call_count == 1


@pytest.mark.parametrize('status', [302, 403, 404, 500])
def test_detail_http_failure_is_partial(serve, status):
    serve(details={URL: response(status=status)})
    with pytest.raises(jobs._PartialSourceError) as error:
        jobs._bofa_jobs()
    assert error.value.failed_urls == {URL}


@pytest.mark.parametrize('payload', [None, {}, {'jobsList': [], 'totalMatches': 12},
    {'jobsList': [], 'totalMatches': '0'}, {'jobsList': [], 'totalMatches': -1},
    {'jobsList': [row(), row()], 'totalMatches': 2}, {'jobsList': [None], 'totalMatches': 1}])
def test_malformed_missing_and_nonprogressing_catalogues_are_partial(serve, payload):
    serve(pages={100: response(payload=payload)})
    with pytest.raises(jobs._PartialSourceError) as error:
        jobs._bofa_jobs()
    assert error.value.preserve_cached


def test_empty_source_is_success_when_total_is_zero(serve):
    serve([])
    assert jobs._bofa_jobs() == []


def test_growing_prefix_covers_results_without_broken_start_offset(serve):
    others = [row(str(n), postingTitle='Operations Intern') for n in range(100)]
    request = serve(pages={100: response(payload={'jobsList': others, 'totalMatches': 101}),
                          101: response(payload={'jobsList': others + [row()], 'totalMatches': 101})})
    job, = jobs._bofa_jobs()
    assert job.url == URL and request.call_count == 3


def test_catalogue_failure_keeps_verified_jobs_and_marks_cache_preservation(serve):
    serve(pages={100: response(payload={'jobsList': [row()], 'totalMatches': 12})})
    with pytest.raises(jobs._PartialSourceError) as error:
        jobs._bofa_jobs()
    assert error.value.preserve_cached and len(error.value.jobs) == 1


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_BOFA_LIVE') != '1', reason='Public GET audit is opt-in')
def test_live_collection_and_public_catalogue_comparison():
    began = perf_counter()
    found = jobs._bofa_jobs()
    assert found and len(found) == len(jobs._deduplicate_opportunities(found))
    assert all(job.company == 'Bank of America' and jobs._eligible_offer(job) for job in found)
    print(f'Bank of America : {len(found)} offres, {perf_counter() - began:.3f}s, aucun doublon')
    for job in found:
        print(f'{job.title} | {job.location} | {job.kind} | {job.family} | '
              f'publié={job.published!r} | début={job.start_period!r} | échéance={job.deadline!r} | {job.url}')
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
    assert 'Bloomberg' in public and 'Bank of America' in local
    urls = [job['url'] for job in offers]
    groups = Counter((job['title'], job['company'], job['location'], job['kind']) for job in offers)
    print(f'Catalogue public updated={documents["sources"]["updated"]}: {len(public)} sources, '
          f'{len(offers)} offres, {len(urls) - len(set(urls))} doublons URL, '
          f'{sum(count > 1 for count in groups.values())} groupes titre/employeur/lieu/contrat ambigus')
    print(f'Locaux seuls={sorted(local-public)} ; publics seuls={sorted(public-local)}')
    print(f'Métiers={dict(Counter(job["family"] for job in offers))}')
    print(f'Contrats={dict(Counter(job["kind"] for job in offers))}')
    print(f'Lieux principaux={Counter(job["location"] for job in offers).most_common(7)}')
    print(f'Sans mois de début={sum(not job.get("start_month") for job in offers)} ; '
          f'dates de détection={sum(job.get("date_label", "").startswith("Détectée") for job in offers)}')
