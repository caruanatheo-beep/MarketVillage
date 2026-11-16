"""Audit du 15 novembre 2026, uniquement depuis les sources publiques.

Etat avant ajout (updated=2026-11-14T23:32:22.696761+00:00) :
https://caruanatheo-beep.github.io/Internships-Offres/sources.json
https://caruanatheo-beep.github.io/Internships-Offres/offers.json
63 sources / 71 flux, 56 employeurs presents dans 428 offres : 90 Sales,
111 Quant / Research, 93 Trading / Structuring, 84 Risk / Support,
37 Asset Management et 13 Capital Markets. Contrats : 368 stages, 51 graduate,
9 VIE. Paris 116, Singapour 49, New York 34, Londres 28, Francfort 23,
Hong Kong 18, Amsterdam 14, Milan et Chicago 11 chacun, Tokyo 9.
253 debuts non precises, 261 sans mois exploitable ; 56 dates sont explicitement
des dates de detection, pas de publication employeur. Aucun doublon d'URL.
Cinq groupes ont meme titre/employeur/lieu/contrat : Schroders Sales Activation
(deux cohortes janvier/juillet, a conserver), THEAM Rome sur chacun des deux
libelles BNP (aliases possibles), BNP Data & AI Lab Francfort (deux portails),
Barclays Quantitative Analytics Londres (deux references, a verifier avant fusion).
L'audit ne supprime ni ne modifie ces offres. Les connecteurs locaux reutilisent
les filtres metier/contrat, les dates explicites et le dedoublonnage communs ;
les flux couvrent banques, gestion et trading, mais certains catalogues sont
locaux (notamment HSBC Paris). Un catalogue de sources ne prouve pas que chaque
source fournit actuellement une offre. Les employeurs compares ci-dessous sont
absents des deux documents publics et des registres actifs locaux avant ajout.

Proposition lue par GET, sans aucune mutation :
https://marketdesk-source-suggestions.source-suggestions.workers.dev/suggestions
GET sans Origin : 403 ; avec Origin public https://caruanatheo-beep.github.io,
comme le site : 200, une proposition Bloomberg, raison vide. Texte traite comme
donnee non fiable. URL publique proposee lue sans ses parametres de suivi :
https://bloomberg.avature.net/careers/SearchJobs/?1686=%5B55479%5D&1686_format=2312&listFilterMode=1&jobRecordsPerPage=12
HTTP 200, six annonces visibles, surtout journalisme/operations et le stage BNEF
https://bloomberg.avature.net/careers/JobDetail/2027-BloombergNEF-Summer-Internship-Singapore/46133
HTTP 200 : recherche energie/commodities, dix semaines a Singapour ; option de
recherche proche, moins prioritaire qu'un stage Sales sur instruments financiers.
Aucune affirmation d'absence de Sales sur l'ensemble du portail Bloomberg.

Comparatif international (offres presentes dans les flux au moment de l'audit) :
* Susquehanna, retenu : https://careers.sig.com/institutional-sales/jobs et
  https://careers.sig.com/api/jobs?tags1=Institutional%20Sales&page=1&limit=20
  HTTP 200, cinq annonces. ETF Sales Internship: Summer 2027, 10944, pres de
  Philadelphie : equipe Sales, transactions ETF/portefeuilles actions, dix
  semaines. Les deux co-ops et les deux postes experimentes sont exclus par les
  filtres existants. Flux GET structure, pagination verifiee et une seule fiche
  pertinente a lire : collecte simple, employeur entierement nouveau, Sales
  directement confirme. Aucun filtre de pays ou de nationalite n'est envoye.
* Virtu : https://www.virtu.com/careers/ pointe vers le board Greenhouse virtu.
  https://boards-api.greenhouse.io/v1/boards/virtu/jobs?content=true
  HTTP 200, 45 annonces, dont Institutional Sales Trader EMEA (8782130002),
  Electronic Trading Sales Support New York (8935822002) et Sales Coverage
  Hong Kong (7098757002) : au moins trois ans d'experience, donc non retenus.
  Client Support Londres (8746197002), stage de dix semaines des le 21 juin 2027,
  cloture 15 novembre 2026 : missions mixtes institutionnelles/retail et support,
  moins cible que le stage ETF Sales retenu. Quant/trading disponibles mais pas
  necessaires comme repli. Collecte GET simple, nouveaux employeur et lieux.
* Old Mission : https://www.oldmissioncapital.com/careers/ pointe vers Ashby.
  https://api.ashbyhq.com/posting-api/job-board/old-mission-capital
  HTTP 200, 42 annonces. ETF Sales Trader Londres (743440a6-4291-4d5e-8458-48ee216d4655)
  exige 2+ ans, Hong Kong (330871d2-fbd4-45e5-b43a-27d4fae35a38) 2-5+ ans ;
  aucun contrat debutant confirme sur ces deux fiches. Graduates quant/trading
  Chicago/New York/Londres ouverts : repli possible, moins prioritaire que Sales.
  Nouveau portail public structure et facile a collecter.
* Maven : https://www.mavensecurities.com/jobs/ pointe vers le board exact
  https://boards-api.greenhouse.io/v1/boards/mavensecuritiesholdingltd/jobs?content=true
  HTTP 200, 36 annonces, stages Trader Amsterdam 8048591 et Londres 7806970,
  Graduate Floor Trader Chicago 8352763 ; pas de Sales dans ce catalogue.
  Bon repli trading et GET simple, mais une source Sales est exploitable.
* BTIG : https://www.btig.com/careers/career-opportunities/ HTTP 200 : trois
  fiches visibles (operations APAC, investment banking senior, technologie VP)
  et renvoi U.S. Bank. La presentation du programme de stages ne prouve pas une
  candidature Sales ouverte. Collecte moins directe ; aucune integration.
* Citadel Securities : https://www.citadelsecurities.com/careers/open-opportunities/
  HTTP 403 ; aucune collecte viable confirmee, aucun contournement.
Les essais de slugs non confirmes virtufinancial, citadelsecurities, gtsx,
mavensecurities, btig et oldmissioncapital renvoient 404 : seuls les liens
decouverts dans les pages employeurs sont retenus, jamais ces slugs supposes.

Collecte reelle via city_test.py avec INTERNSHIPS_SUSQUEHANNA_LIVE=1 :
premier controle, 45 tests passes, 1 offre Sales en 1.433 s, aucun doublon.
Controle final avec les regressions catalogue, dates et dedoublonnage :
184 tests et 50 sous-tests passes en 2.20 s ; collecte de la meme offre en 0.939 s.
https://careers.sig.com/jobs/10944?lang=en-us HTTP 200 : titre et adresse
JobPosting concordants, Bala Cynwyd (Philadelphia Area), Pennsylvania, United
States. datePosted=2026-06-04 ; validThrough=2027-06-04. Cette expiration publiee
par le portail n'est pas une date limite annoncee dans le texte. Summer 2027
ne precise aucun mois de debut : champ laisse vide. Ni modification du 5 novembre
ni annee de diplomation ne remplacent ces dates. Aucun sponsoring de visa selon
l'annonce : information conservee dans la description, sans exclusion nationale.
Seul Susquehanna est ajoute, categorie Courtage & trading, ajout 2026-11-15.
Les tests utilisent des donnees synthetiques ou le portail public, sans caches.
"""

import json
import os
from datetime import datetime, timezone
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from internships_project import internships as jobs
from internships_project.source_catalog import public_source_catalog


TITLE = 'ETF Sales Internship: Summer 2027'
URL = 'https://careers.sig.com/jobs/10944?lang=en-us'
DESCRIPTION = ('Interns on our ETF Sales and Capital Markets team gain experience on the trading desk. '
               'Partner with our sales team to facilitate ETF and equity portfolio trades. '
               'Intention to graduate within one year of the internship program. '
               'Visa sponsorship for work authorization is not available.')


def row(identity='10944', **overrides):
    return {'data': {'slug': identity, 'title': TITLE, 'applyable': True, 'searchable': True,
                     'posted_date': '2026-06-04T14:27:00+0000', 'posting_expiry_date': None,
                     'meta_data': {'canonical_url': 'https://untrusted.invalid/not-followed',
                                   'last_mod': '2026-11-05T19:30:10+0000'}, **overrides}}


def detail(**overrides):
    posting = {'@type': 'JobPosting', 'title': TITLE, 'datePosted': '2026-06-04T14:27:00+0000',
               'validThrough': '2027-06-04T14:48:44.000Z', 'employmentType': 'UNAVAILABLE',
               'description': DESCRIPTION,
               'jobLocation': {'address': {'addressLocality': 'Bala Cynwyd (Philadelphia Area)',
                                           'addressRegion': 'Pennsylvania', 'addressCountry': 'United States'}},
               **overrides}
    return '<script type="application/ld+json">' + json.dumps(posting) + '</script>'


def response(*, payload=None, text='', status=200):
    return SimpleNamespace(json=lambda: payload, text=text, status_code=status, raise_for_status=lambda: None)


@pytest.fixture
def serve(monkeypatch):
    clock = Mock(wraps=datetime)
    clock.now.return_value = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(jobs, 'datetime', clock)

    def install(rows=None, pages=None, details=None):
        rows = [row()] if rows is None else rows
        pages = pages or {1: {'jobs': rows, 'totalCount': len(rows)}}
        details = details or {URL: response(text=detail())}

        def get(url, **kwargs):
            assert kwargs['allow_redirects'] is False
            assert kwargs['timeout'] == (8, 20)
            if url == 'https://careers.sig.com/api/jobs':
                params = kwargs['params']
                assert params['tags1'] == 'Institutional Sales'
                assert set(params) == {'tags1', 'page', 'limit'}  # Worldwide; no nationality or country filter.
                value = pages[params['page']]
                if isinstance(value, Exception):
                    raise value
                return response(payload=value)
            value = details[url]
            if isinstance(value, Exception):
                raise value
            return value

        request = Mock(side_effect=get)
        monkeypatch.setattr(jobs.requests, 'get', request)
        return request

    return install


def test_sales_source_is_registered_once_with_category_url_and_addition_date():
    assert [(loader, args) for name, loader, args in jobs._opportunity_source_tasks()
            if name == 'Susquehanna'] == [(jobs._susquehanna_jobs, ('', ''))]
    source = next(s for s in public_source_catalog() if s['name'] == 'Susquehanna')
    assert source == {'name': 'Susquehanna', 'category': 'Courtage & trading',
                      'url': 'https://careers.sig.com/institutional-sales/jobs', 'added_on': '2026-11-15',
                      'feeds': [{'name': 'Susquehanna', 'url': 'https://careers.sig.com/institutional-sales/jobs'}]}


def test_sales_internship_preserves_employer_location_dates_and_visa_information(serve):
    request = serve()
    job, = jobs._susquehanna_jobs()
    assert job.title == TITLE and job.company == 'Susquehanna'
    assert job.kind == 'Stage' and job.family == 'Sales'
    assert job.url == URL
    assert job.location == 'Bala Cynwyd (Philadelphia Area), Pennsylvania, United States'
    assert job.published == '2026-06-04' and not job.published_inferred
    assert job.deadline == '2027-06-04'
    assert job.start_period == ''  # Summer does not identify a precise month.
    assert 'Visa sponsorship' in job.description and '<' not in job.description
    assert jobs._eligible_offer(job)
    assert request.call_count == 2


@pytest.mark.parametrize('title', ['Retail Banking Sales Intern', 'Middle Office Sales Intern',
    'Back Office Trading Intern', 'Markets Operations Intern', 'Legal Counsel Intern',
    'Corporate Finance Intern', 'Sales Trader', 'Derivatives Sales Trader | Experienced Hire',
    'Senior Production Engineer', 'ETF Sales + Capital Markets Co-op'])
def test_other_functions_senior_roles_and_unconfirmed_contracts_are_excluded(serve, title):
    request = serve(rows=[row(title=title)])
    assert jobs._susquehanna_jobs() == []
    assert request.call_count == 1


@pytest.mark.parametrize('overrides', [{'applyable': False}, {'searchable': False},
                                    {'posting_expiry_date': '2026-11-14T23:59:59Z'}])
def test_inactive_or_expired_feed_rows_do_not_trigger_detail_fetches(serve, overrides):
    request = serve(rows=[row(**overrides)])
    assert jobs._susquehanna_jobs() == []
    assert request.call_count == 1


@pytest.mark.parametrize('posted', ['', None, 'invalid', '2026-02-30', '2099-01-01'])
def test_unknown_publication_is_not_replaced_by_modification_start_or_expiry(serve, posted):
    serve(details={URL: response(text=detail(datePosted=posted, jobStartDate='2027-06-21'))})
    job, = jobs._susquehanna_jobs()
    assert job.published == ''
    assert job.start_period == '2027-06-21' and job.deadline == '2027-06-04'


@pytest.mark.parametrize('expiry,kept', [('2026-11-14', False), ('2026-11-15', True),
                                     ('2026-11-16', True), (None, True), ('invalid', True)])
def test_employer_expiry_filters_closed_postings_and_unknown_stays_unknown(serve, expiry, kept):
    serve(details={URL: response(text=detail(validThrough=expiry))})
    found = jobs._susquehanna_jobs()
    assert bool(found) is kept
    if kept:
        assert found[0].deadline == (expiry if expiry and expiry != 'invalid' else '')


def test_paginated_feed_deduplicates_identity_before_loading_details(serve):
    second = 'https://careers.sig.com/jobs/12345?lang=en-us'
    request = serve(pages={1: {'jobs': [row(), row()], 'totalCount': 3},
                           2: {'jobs': [row('12345', title='FX Sales Graduate')], 'totalCount': 3}},
                    details={URL: response(text=detail()),
                             second: response(text=detail(title='FX Sales Graduate',
                                                          jobLocation={'address': {'addressLocality': 'Singapore'}}))})
    found = jobs._susquehanna_jobs()
    assert len(found) == len(jobs._deduplicate_opportunities(found)) == 2
    assert {job.kind for job in found} == {'Stage', 'Graduate'}
    assert request.call_count == 4


@pytest.mark.parametrize('payload', [None, {}, [], {'jobs': None, 'totalCount': 0},
    {'jobs': [], 'totalCount': '0'}, {'jobs': [None], 'totalCount': 1},
    {'jobs': [row('https://untrusted.invalid')], 'totalCount': 1},
    {'jobs': [], 'totalCount': 1}])
def test_malformed_or_incomplete_catalogue_is_reported_as_failure(serve, payload):
    serve(pages={1: payload})
    with pytest.raises(jobs._PartialSourceError) as caught:
        jobs._susquehanna_jobs()
    assert caught.value.preserve_cached


def test_valid_empty_catalogue_does_not_keep_removed_postings(serve):
    serve(rows=[])
    assert jobs._susquehanna_jobs() == []


def test_failed_later_page_retains_verified_first_page_as_partial(serve):
    serve(pages={1: {'jobs': [row()], 'totalCount': 2}, 2: jobs.requests.Timeout()})
    with pytest.raises(jobs._PartialSourceError) as caught:
        jobs._susquehanna_jobs()
    assert len(caught.value.jobs) == 1 and caught.value.preserve_cached


def test_repeated_page_is_a_partial_failure(serve):
    page = {'jobs': [row()], 'totalCount': 2}
    serve(pages={1: page, 2: page})
    with pytest.raises(jobs._PartialSourceError) as caught:
        jobs._susquehanna_jobs()
    assert len(caught.value.jobs) == 1 and caught.value.preserve_cached


def test_catalogue_redirect_is_reported_without_following_it(monkeypatch):
    request = Mock(return_value=response(status=302))
    monkeypatch.setattr(jobs.requests, 'get', request)
    with pytest.raises(jobs._PartialSourceError) as caught:
        jobs._susquehanna_jobs()
    assert caught.value.preserve_cached
    assert request.call_count == 1
    assert request.call_args.kwargs['allow_redirects'] is False


@pytest.mark.parametrize('result', [response(text='Verify you are human'), response(status=302),
    response(text=detail(title='Different Sales Internship')), jobs.requests.Timeout()])
def test_failed_or_redirected_detail_is_not_reported_as_empty_success(serve, result):
    serve(details={URL: result})
    with pytest.raises(jobs._PartialSourceError) as caught:
        jobs._susquehanna_jobs()
    assert caught.value.failed_urls == {URL}
    assert not caught.value.preserve_cached


@pytest.mark.parametrize('url', ['http://careers.sig.com/jobs/10944',
    'https://careers.sig.com.evil.invalid/jobs/10944',
    'https://careers.sig.com@evil.invalid/jobs/10944'])
def test_only_exact_https_employer_host_is_trusted(url):
    assert not jobs.is_trusted_offer_url(url)


@pytest.mark.skipif(os.environ.get('INTERNSHIPS_SUSQUEHANNA_LIVE') != '1', reason='Public live audit is opt-in')
def test_live_institutional_sales_collection_and_employer_pages():
    began = perf_counter()
    found = jobs._susquehanna_jobs()
    elapsed = perf_counter() - began
    assert found and all(job.family == 'Sales' for job in found)
    assert len(found) == len(jobs._deduplicate_opportunities(found))
    print(f'Susquehanna: {len(found)} Sales offers, {elapsed:.3f}s collection, no duplicates')
    for job in found:
        response = jobs.requests.get(job.url, timeout=(8, 20), allow_redirects=False)
        assert response.status_code == 200
        structured = jobs._jsonld_jobposting(response.text)
        assert structured['title'] == job.title
        assert jobs._jsonld_job_posted(response.text) == job.published
        assert jobs._structured_job_location(structured) == job.location
        assert not job.deadline or job.deadline >= datetime.now(timezone.utc).date().isoformat()
        assert jobs._eligible_offer(job)
        print(f'{job.title} | {job.location} | publication={job.published} | start={job.start_period!r} | '
              f'expiry={job.deadline!r} | HTTP {response.status_code} | {job.url}')
