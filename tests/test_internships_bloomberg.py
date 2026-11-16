"""Audit public du 15 novembre 2026 et régressions du collecteur Bloomberg.

https://caruanatheo-beep.github.io/Internships-Offres/sources.json
https://caruanatheo-beep.github.io/Internships-Offres/offers.json
Snapshot 06:41 UTC : 65 sources / 73 flux, 426 offres (366 stages, 52 graduate,
8 VIE), 90 Sales, 111 Quant/Research, 93 Trading/Structuring, 82 Risk/Support,
37 Asset Management, 13 Capital Markets. Paris 115, Singapour 49, New York 34,
Londres 28, Francfort 23, Hong Kong 18, Amsterdam 14. Aucun doublon d'URL ;
cinq groupes titre/employeur/lieu/contrat : Schroders Sales Activation (cohortes
différentes), THEAM Rome sous deux noms BNP, BNP Data & AI Lab Francfort et
Barclays Quantitative Analytics Londres. Pas de fusion aveugle de références.
261 offres sans mois de début, 54 dates de détection. Le catalogue local et le
catalogue public ont les mêmes groupes de sources avant cet ajout. Bloomberg,
BlackRock, PIMCO, Fidelity, Morgan Stanley, State Street, Euroclear et Clearstream
restent des lacunes ; TP ICAP n'est qu'un lien de portail, sans tâche active.
La couverture HSBC locale reste limitée à Paris. Les sources existantes ne
sont pas modifiées et aucun repli quant/développement/prop trading n'est ajouté.

Propositions : GET
https://marketdesk-source-suggestions.source-suggestions.workers.dev/suggestions
403 sans Origin ; 200 avec Origin https://caruanatheo-beep.github.io, une seule
proposition Bloomberg, raison vide. Aucune mutation ; texte traité comme données.
URL proposée vérifiée HTTP 200 :
https://bloomberg.avature.net/careers/SearchJobs/?1686=%5B55479%5D&1686_format=2312&listFilterMode=1&jobRecordsPerPage=12
Six stages principalement news/BNEF/opérations. Ce filtre ne prouve aucune
absence : portail mondial sans filtre d'expérience, pays, langue ou nationalité
https://bloomberg.avature.net/careers/SearchJobs/
337 annonces, 29 pages, jobRecordsPerPage=12, jobOffset=0,12,...,336 ; demander
100 conserve 12 résultats. Synonymes examinés : Analytics & Sales, Early
Professional, Graduate, Programme, Internship, Junior, Client Service,
Product Specialist. Quatorze programmes Analytics & Sales identifiés, Londres,
São Paulo, Singapour, Sydney ; la rotation Londres/Afrique du Sud conserve ses
conditions de droit au travail dans le texte. Description, Business Area,
référence et lien Apply vérifiés sur chaque fiche, sans suivre ce lien.

Candidats comparés après Bloomberg :
BlackRock https://careers.blackrock.com/search-jobs (200, 284 résultats, 29 pages)
https://careers.blackrock.com/category/students-and-graduates-jobs/45831/9022304/1
et /2 (200) ; recherche ?k=client%20service (200, 211 résultats, 22 pages).
https://careers.blackrock.com/job/london/2027-client-and-product-graduate-rotational-program-emea/45831/97150826688
200, programme pertinent, échéances Londres 30/09, plusieurs villes 30/10 et
13/11 dépassées, Abu Dhabi encore ouvert jusqu'au 31/01/2027 ; ne pas assimiler
page accessible et candidatures ouvertes partout. Source nouvelle et faisable,
non retenue au profit de la proposition Bloomberg,
sans affirmer l'absence d'autres postes ouverts chez BlackRock.
TP ICAP https://tpicap.com/careers/opportunities et ?function=earlycareers
200, stages Global Broking Londres et New York, autres placements opérations
hors périmètre ;
https://tp.wd107.myworkdayjobs.com/TP-ICAP/job/New-York/XMLNAME-2027-Global-Broking-Internship_R6046
200, JobPosting publié le 13/11/2026, pertinent, nouveau flux possible. Non
retenu : Bloomberg est la proposition prioritaire et couvre 14 programmes
confirmés dans plusieurs régions ; faisabilité examinée après pertinence.
Essais initiaux non probants, corrigés via liens employeurs : BlackRock /jobs
404 et tpicap.wd3.myworkdayjobs.com 500 ; aucun refus fondé sur ces erreurs.

Une seule source ajoutée : Bloomberg, Information financière & relation clients,
15/11/2026 ; famille distincte Client Service / Financial Solutions. Aucune date
de publication/expiration inventée. Logo PNG 96x96 trouvé dans le portail officiel :
https://bloomberg.avature.net/_cms/4/image/iconLogo96x96?version=14115241
HTTP 200, 1 074 octets, validation Pillow. Aucun appel au site privé ou aux caches.

Validation réelle via city_test.py, INTERNSHIPS_BLOOMBERG_LIVE=1 : 55 tests
réussis en 78,91 s, dont collecte de 14 offres en 78,456 s, aucune fusion ni
perte au dédoublonnage commun. Quatorze fiches employeur HTTP 200 vérifiées ;
aucune datePosted ni validThrough publiée, champs laissés vides ; cinq cohortes
May class deviennent May 2027. Langues et conditions de visa conservées dans
les descriptions, y compris absence de sponsoring en Afrique du Sud et aide
possible au Royaume-Uni. Les durées de rotation restent dans la description.
Premier essai réel : contrôle trop strict de 'Apply' au lieu de 'Apply Now',
corrigé avant la réussite ci-dessus et reproduit par les tests synthétiques.
Comparaison publique séparée, INTERNSHIPS_PUBLIC_CATALOGUE_AUDIT=1 : 1 test
réussi en 1,11 s ; seul Bloomberg existe localement sans être encore publié,
aucune source publique sans collecteur local. Publication Pages non confirmée.

Reprise de la même mission, 15/11/2026, sans nouvelle source sélectionnée :
le snapshot Git contient déjà le travail Bloomberg décrit ci-dessus. GET publics
sources.json et offers.json : HTTP 200, updated 2026-11-15T14:42:09.904316+00:00,
66 sources locales/publiques identiques, 440 offres : 366 stages, 66 graduate,
8 VIE ; 90 Sales, 14 Client Service / Financial Solutions, autres familles
inchangées. Paris 115, Singapour 59, New York 34, Londres 30, Francfort 23,
Hong Kong 18. Aucun doublon d'URL ; les cinq groupes ambigus décrits plus haut
subsistent, sans les fusionner à partir du seul titre. Le schéma public utilise
start_month et date_label : 270 mois de début absents, 68 dates de détection.
Bloomberg : 10 Singapour, 2 Londres, 1 São Paulo, 1 Sydney ; cinq débuts en mai
2027, neuf non précisés. Pas de datePosted/validThrough sur les fiches vérifiées.
Ces observations ne confirment pas la publication du delta de cette reprise.

GET suggestions avec Origin : HTTP 200, propositions actuelles Bank of America
et Morgan Stanley, raisons vides ; aucune archive ni autre mutation.
Bank of America : URL proposée et portail mondial /en-us/job-search sans filtre
géographique HTTP 200. Le HTML initial étudiant mélange des postes professionnels ;
sa liste ne permet pas de conclure. Le JavaScript officiel clientlib-base.js
indique le flux public /services/campusjobssearchservlet. Requêtes GET vérifiées :
https://careers.bankofamerica.com/services/campusjobssearchservlet?start=0&rows=10&search=getAllJobs
HTTP 200, 10/12 ; start=10&rows=10 HTTP 200 mais liste vide malgré total=12 ;
start=0&rows=100 HTTP 200, les 12 annonces sont présentes. Aucun filtre hérité,
examen des titres/contrats Internship, Intern, Full Time Analyst, Programme,
Graduate et des métiers Sales, Rates/Currencies, Global Markets. L'essai
search=keywords&keywords=Global%20Markets retourne 204, sans valeur d'absence.
https://careers.bankofamerica.com/en-us/students/job-detail/15269/global-markets-fixed-income-currencies-commodities-sales-full-time-analyst-2027-tokyo-tokyo-japan
HTTP 200, FICC Sales institutionnel, anglais et japonais, échéance 29/11/2026,
publié le 04/11 selon le flux : candidat pertinent et nouveau, non refusé.
Le programme Mexico Rates and Currencies vise les clients corporate, hors cible.
Morgan Stanley : URL proposée ?opportunity=sg, portail mondial sans ce filtre et
https://morganstanley.eightfold.ai/careers HTTP 200, lien trouvé sur le site
officiel. Audit des annonces/pagination incomplet ; aucune conclusion d'absence.
Ces propositions sont documentées avant toute nouvelle découverte ; BlackRock
et TP ICAP restent les comparaisons historiques ci-dessus. Bloomberg reste
l'unique choix de cette mission reprise : proposition initialement prioritaire,
14 programmes ouverts, couverture internationale et famille métier distincte.

Correction limitée à Bloomberg : les métadonnées JobPosting dont le titre ou
l'URL identifie une autre annonce ne peuvent plus dater ou expirer la fiche.
Régression reproduite avant correction : 4 échecs, 3 réussites ; après correction
61 réussites et 2 audits ignorés sans opt-in. Avec les deux opt-ins : 63 réussites
en 80,21 s ; collecte de 14 annonces en 78,019 s, sans doublon. Vérifications
complémentaires dates, dédoublonnage et logos : 63 tests et 72 sous-tests réussis.
Les durées, langues et conditions de visa restent dans les descriptions ; les
métadonnées contradictoires sont ignorées plutôt que remplacées par une estimation.
"""

import html
import json
import os
from datetime import datetime, timezone
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog


BASE = 'https://bloomberg.avature.net/careers/'
URL = BASE + 'JobDetail/2027-Analytics-Sales-Sao-Paulo/45729'
TITLE = '2027 - Analytics & Sales - Sao Paulo'
DESCRIPTION = ("The Analytics & Sales Program offers expertise in financial markets. "
               "You will begin your career in Analytics with Bloomberg Professional Services clients. "
               "You'll need a bachelor's degree. Eligibility to start a full-time role in 2027. "
               "Fluency in English and Portuguese or Spanish. Visa sponsorship is not available.")


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 15, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(jobs, 'datetime', Clock)


def response(text='', status=200):
    def raise_for_status():
        if status >= 400:
            raise jobs.requests.HTTPError(str(status))
    return SimpleNamespace(text=text, status_code=status, raise_for_status=raise_for_status)


def row(title=TITLE, url=URL, location='Sao Paulo, São Paulo, Brazil'):
    return f'''<article class="article article--result"><h3><a href="{html.escape(url)}">{html.escape(title)}</a></h3>
    <span class="list-item-location">{html.escape(location)}</span><a href="{html.escape(url)}">Apply</a></article>'''


def listing(rows=None, total=None):
    rows = [row()] if rows is None else rows
    return f'<span aria-label="{len(rows) if total is None else total} results"></span>' + ''.join(rows)


def detail(title=TITLE, description=DESCRIPTION, *, identity='45729', location='Sao Paulo',
           area='Sales and Client Service', apply=True, structured=None, reference='10054618'):
    data = f'<script type="application/ld+json">{json.dumps(structured)}</script>' if structured else ''
    return f'''{data}<article class="article article--details"><div>{html.escape(title)}</div></article>
    <article class="article article--details regular-fields"><div>Location</div><div>{location}</div>
    <div>Business Area</div><div>{area}</div><div>Ref #</div><div>{reference}</div></article>
    <article class="article article--details"><h2>Description &amp; Requirements</h2><div>{html.escape(description)}</div></article>
    {f'<a href="{BASE}Login?jobId={identity}">Apply Now</a>' if apply else ''}
    <footer>Graduate Quant Developer Internship starts in June 2028.</footer>
    <article><h2>Related Sales Internship</h2><p>Start in December 2030.</p></article>'''


@pytest.fixture
def serve(monkeypatch):
    def configure(pages=None, details=None):
        pages = {0: response(listing())} if pages is None else pages
        details = {URL: response(detail())} if details is None else details
        def get(url, **kwargs):
            assert kwargs['allow_redirects'] is False
            assert kwargs['timeout'] == (8, 20)
            if url == BASE + 'SearchJobs/':
                assert set(kwargs['params']) == {'jobRecordsPerPage', 'jobOffset'}
                assert kwargs['params']['jobRecordsPerPage'] == 12
                result = pages[kwargs['params']['jobOffset']]
            else:
                result = details[url]
            if isinstance(result, Exception):
                raise result
            return result
        request = Mock(side_effect=get)
        monkeypatch.setattr(jobs.requests, 'get', request)
        return request
    return configure


def test_registry_source_card_category_date_and_official_logo():
    tasks = [task for task in jobs._opportunity_source_tasks() if task[0] == 'Bloomberg']
    assert len(tasks) == 1 and tasks[0][1] is jobs._bloomberg_jobs
    source, = [source for source in public_source_catalog() if source['name'] == 'Bloomberg']
    assert source['category'] == 'Information financière & relation clients'
    assert source['url'] == BASE + 'SearchJobs/' and source['added_on'] == '2026-11-15'
    path = jobs.COMPANY_LOGO_DIR / (jobs.COMPANY_ICON_HOSTS['bloomberg'] + '.png')
    assert path.stat().st_size <= 512 * 1024
    with Image.open(path) as image:
        assert image.format == 'PNG' and image.size == (96, 96)
        image.verify()


def test_collection_keeps_location_languages_visa_and_distinct_family(serve):
    request = serve()
    job, = jobs._bloomberg_jobs()
    assert (job.title, job.company, job.kind, job.location) == (
        TITLE, 'Bloomberg', 'Graduate', 'Sao Paulo, São Paulo, Brazil')
    assert job.family == 'Client Service / Financial Solutions'
    assert job.family == jobs._family(job.title, job.description)
    assert job.employment == 'Graduate programme' and jobs._eligible_offer(job)
    assert job.published == job.start_period == job.deadline == ''
    assert 'Portuguese or Spanish' in job.description and 'Visa sponsorship is not available' in job.description
    assert 'Related' not in job.description and 'Developer' not in job.description
    assert request.call_count == 2


def test_undated_offer_uses_detection_date_only_at_shared_publication_step(serve, monkeypatch):
    serve()
    job, = jobs._bloomberg_jobs()
    monkeypatch.setattr(jobs, '_refresh_first_seen', {})
    dated = jobs._date_detected_offer(job, None, jobs.datetime.now(timezone.utc).date())
    assert dated.published == '2026-11-15' and dated.published_inferred
    assert dated.start_period == dated.deadline == ''


@pytest.mark.parametrize('title', [
    '2027 Analytics & Sales Graduate Programme (Thai speaker), Singapore',
    '2027 Analytics & Sales Early Professional Programme, Singapore (May class, Thai Speaker)',
    '2027 - Analytics & Sales - London/South Africa Rotational Programme',
    '2027 Analytics and Sales - Japanese Speakers',
    'Sales Summer Internship', 'Institutional Sales VIE', 'Junior Sales Analyst',
])
def test_contract_and_role_synonyms_include_international_programmes(serve, title):
    serve(pages={0: response(listing([row(title=title)]))}, details={URL: response(detail(title=title))})
    job, = jobs._bloomberg_jobs()
    assert jobs._eligible_offer(job)
    if 'May class' in title:
        assert job.start_period == 'May 2027'
    if 'Summer' in title:
        assert job.kind == 'Stage' and job.start_period == ''
    if 'VIE' in title:
        assert job.kind == 'VIE'


@pytest.mark.parametrize('title', ['BloombergNEF Summer Internship', 'News Summer Internship',
    'Procurement Operations Intern', 'Quant Developer Graduate', 'Proprietary Trading Intern',
    'Retail Banking Sales Intern', 'Corporate Sales Graduate', 'Senior Sales Graduate',
    'Sales Solutions Engineer Graduate', 'Middle Office Sales Intern', 'Sales Account Manager'])
def test_no_fallback_or_non_junior_collection(serve, title):
    request = serve(pages={0: response(listing([row(title=title)]))})
    assert jobs._bloomberg_jobs() == [] and request.call_count == 1


@pytest.mark.parametrize('description,area', [
    ('Experienced sales team. Not an entry programme.', 'Sales and Client Service'),
    (DESCRIPTION, 'News'),
    (DESCRIPTION + ' At least 5 years of relevant experience required.', 'Sales and Client Service'),
])
def test_programme_requires_own_entry_and_business_evidence(serve, description, area):
    serve(details={URL: response(detail(description=description, area=area))})
    assert jobs._bloomberg_jobs() == []


@pytest.mark.parametrize('published', [None, '', 'invalid', '2026-02-30', '2099-01-01'])
def test_no_invented_publication_from_start_modification_or_deadline(serve, published):
    structured = {'@type': 'JobPosting', 'datePosted': published, 'dateModified': '2026-11-14',
                  'jobStartDate': '2027-06-21', 'validThrough': '2026-12-31'}
    serve(details={URL: response(detail(structured=structured))})
    job, = jobs._bloomberg_jobs()
    assert job.published == '' and job.start_period == '2027-06-21' and job.deadline == '2026-12-31'


@pytest.mark.parametrize('expiry,kept', [('2026-11-14', False), ('2026-11-15', True),
                                     ('2026-11-16', True), ('invalid', True), ('', True)])
def test_expiration_and_explicit_publication(serve, expiry, kept):
    serve(details={URL: response(detail(structured={
        '@type': 'JobPosting', 'datePosted': '2026-11-10', 'validThrough': expiry}))})
    found = jobs._bloomberg_jobs()
    assert bool(found) is kept
    if kept:
        assert found[0].published == '2026-11-10'
        assert found[0].deadline == (expiry if expiry != 'invalid' else '')


@pytest.mark.parametrize('identity', [
    {'title': 'Unrelated Sales Graduate Programme'},
    {'url': BASE + 'JobDetail/Another-Programme/999'},
    {'url': 'https://untrusted.invalid/careers/JobDetail/Programme/45729'},
    {'url': {'@id': URL}},
])
def test_other_posting_metadata_cannot_date_or_expire_current_vacancy(serve, identity):
    serve(details={URL: response(detail(structured={
        '@type': 'JobPosting', **identity, 'datePosted': '2026-10-01',
        'jobStartDate': '2028-09-01', 'validThrough': '2026-11-01'}))})
    job, = jobs._bloomberg_jobs()
    assert job.published == job.start_period == job.deadline == ''


@pytest.mark.parametrize('identity', [
    {'title': TITLE}, {'url': URL},
    {'url': '/careers/JobDetail/Canonical-Slug/45729'},
])
def test_matching_posting_identity_keeps_verified_dates(serve, identity):
    serve(details={URL: response(detail(structured={
        '@type': 'JobPosting', **identity, 'datePosted': '2026-11-10',
        'jobStartDate': '2027-06-21', 'validThrough': '2026-12-31'}))})
    job, = jobs._bloomberg_jobs()
    assert (job.published, job.start_period, job.deadline) == (
        '2026-11-10', '2027-06-21', '2026-12-31')


def test_global_pagination_and_duplicate_identity_before_detail(serve):
    second = BASE + 'JobDetail/2027-Analytics-Sales-Sydney/45126'
    # Repeated links and slug variants must not load the same employer ID twice.
    rows = [row()] * 2 + [row(title='News Internship', url=BASE + f'JobDetail/News/{n}') for n in range(10)]
    title = '2027 Analytics & Sales Graduate Programme, Sydney'
    request = serve(pages={0: response(listing(rows, 14)),
                           12: response(listing([row(url=BASE + 'JobDetail/Other-Slug/45729'),
                                                row(title=title, url=second)], 14))},
                    details={URL: response(detail()), second: response(detail(title=title, identity='45126', location='Sydney'))})
    found = jobs._bloomberg_jobs()
    assert len(found) == len(jobs._deduplicate_opportunities(found)) == 2
    assert request.call_count == 4


@pytest.mark.parametrize('result', [response('Verify you are human'), response(status=302),
    response(listing([], 1)), response(listing([row()], 0)),
    response(listing([row(url='https://evil.invalid/careers/JobDetail/Job/123')]))])
def test_invalid_listing_is_failure_not_empty_success(serve, result):
    serve(pages={0: result})
    with pytest.raises(jobs._PartialSourceError) as caught:
        jobs._bloomberg_jobs()
    assert caught.value.preserve_cached


def test_valid_empty_catalogue(serve):
    serve(pages={0: response(listing([]))})
    assert jobs._bloomberg_jobs() == []


def test_confirmed_closed_offer_is_removed(serve):
    serve(details={URL: response(detail(description='This position has been filled.', apply=False))})
    assert jobs._bloomberg_jobs() == []


@pytest.mark.parametrize('second', [jobs.requests.Timeout(), response(listing([row()] * 12, 24))])
def test_failed_or_repeated_later_page_preserves_verified_results(serve, second):
    serve(pages={0: response(listing([row()] * 12, 24)), 12: second})
    with pytest.raises(jobs._PartialSourceError) as caught:
        jobs._bloomberg_jobs()
    assert len(caught.value.jobs) == 1 and caught.value.preserve_cached


@pytest.mark.parametrize('result', [jobs.requests.Timeout(), response(status=302), response('Challenge'),
    response(detail(title='Different Sales Programme')), response(detail(reference='')),
    response(detail(apply=False)), response(detail(identity='999'))])
def test_unverified_details_report_partial_failure(serve, result):
    serve(details={URL: result})
    with pytest.raises(jobs._PartialSourceError) as caught:
        jobs._bloomberg_jobs()
    assert caught.value.failed_urls == {URL} and not caught.value.preserve_cached


@pytest.mark.parametrize('url', ['http://bloomberg.avature.net/careers/JobDetail/Job/123',
    'https://bloomberg.avature.net.evil.invalid/careers/JobDetail/Job/123',
    'https://user:password@bloomberg.avature.net/careers/JobDetail/Job/123'])
def test_only_exact_https_employer_host(url):
    assert not jobs.is_trusted_offer_url(url)


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_BLOOMBERG_LIVE') != '1', reason='Public live audit is opt-in')
def test_live_collection_dates_locations_and_duplicates(monkeypatch):
    began = perf_counter()
    real_detail = jobs._bloomberg_detail
    def checked_detail(url, title, location, page_html):
        try:
            result = real_detail(url, title, location, page_html)
        except ValueError as error:
            print(f'Unverified public detail: {url}: {error}', flush=True)
            raise
        print(f'Verified public detail: {url}', flush=True)
        return result
    monkeypatch.setattr(jobs, '_bloomberg_detail', checked_detail)
    found = jobs._bloomberg_jobs()
    elapsed = perf_counter() - began
    assert found and len(found) == len(jobs._deduplicate_opportunities(found))
    assert all(job.company == 'Bloomberg' and jobs._eligible_offer(job) for job in found)
    print(f'Bloomberg: {len(found)} offers, {elapsed:.3f}s, no duplicates')
    for job in found:
        assert job.description and job.location and jobs.is_trusted_offer_url(job.url)
        assert not job.deadline or job.deadline >= '2026-11-15'
        print(f'{job.title} | {job.location} | {job.kind} | {job.family} | '
              f'published={job.published!r} | start={job.start_period!r} | expiry={job.deadline!r} | {job.url}')


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_PUBLIC_CATALOGUE_AUDIT') != '1', reason='Public inventory audit is opt-in')
def test_live_public_inventory_comparison():
    """Compare public inventory with active collectors, never read local caches."""
    documents = {}
    for name in ('sources', 'offers'):
        response = jobs.requests.get(f'https://caruanatheo-beep.github.io/Internships-Offres/{name}.json',
                                     timeout=(8, 20), allow_redirects=False)
        response.raise_for_status()
        assert response.status_code == 200
        documents[name] = response.json()
    public = {source['name'] for source in documents['sources']['sources']}
    local = {source['name'] for source in public_source_catalog()}
    offers = documents['offers']['offers']
    assert 'Bloomberg' in local and all(jobs.is_trusted_offer_url(job['url']) or
                                      'jobteaser.com/' in job['url'] for job in offers)
    urls = [job['url'] for job in offers]
    print(f'Public: {len(public)} sources, {len(offers)} offers, {len(urls) - len(set(urls))} duplicate URLs')
    print(f'Active only locally: {sorted(local - public)}; public only: {sorted(public - local)}')
