"""Regression cases from the public careers audit of 9 November 2026."""
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from internships_project import internships as m


@pytest.mark.parametrize('title', [
    'Stage - Assistant Spécialiste Produit – Gestions Actions H/F',
    'Stage OCIO Solutions - Advisory (Gestion Diversifiée) H/F',
    'Stage Assistant gestion taux',
    'Stage - Assistant Securities Lending Trading H/F',
    'Stage - Assistant Sales Front Office - Securities Finance et Repo H/F',
    'Internship - Credit & Structured Finance, Market Risk',
    'Intern Debt Capital Markets',
    'Graduate Trainee – Debt Capital Markets',
    'Stage - Assistant Syndication Obligataire F/H',
    'Internship Global Markets, Corporate Sales & Structuring',
    'Stage Sales Assistant Marketing Produits Structurés',
    'Stage - Assistant Trading Agreement Facilitation H/F',
    'Stage - Assistant commercial (clients institutionnels) H/F',
])
def test_keeps_market_and_listed_asset_management_roles(title):
    assert m._opportunity(title, 'Bank', 'Paris', '',
                          'https://jobs.smartrecruiters.com/bank/123', '') is not None


@pytest.mark.parametrize('title', [
    'STAGE - Trading Collateral Middle Officer H/F',
    'Stage MiddleOffice Equity',
    'Stage Back-Office Trading',
    'STAGE - Fund Execution Reconciliation Team H/F',
    'Stage Issuers Servicing Officer / Bonds H/F',
    'Stage Securities Lending Officer',
    'Stage Gestionnaire Fixed Income and Commodities - Vanilla',
    "Stage Assistant Chargé d'affaires financements structurés H/F",
    'Stagiaire Analyste Crédit Financement Structuré',
    'VIE Development and Structured Export Finance',
    'Stagiaire Portfolio Financements structurés',
    'Stage Equity and Debt advisory',
    'Stage Corporate Finance',
    'Stage Private Equity Funds Analyst',
    'Stage Analyste Quantitatif - Multi Actifs Privés',
    'Stage Fund Controller Junior',
    'Stage Juriste Marchés de Capitaux',
    'Stage Audit Trading',
])
def test_rejects_operations_and_corporate_even_with_market_boilerplate(title):
    assert not m._market_relevant_with_context(
        title, 'Our group has equity investment teams, analysts / portfolio managers and market risk teams.')


@pytest.mark.parametrize('title', [
    'International Equity Sales - Vice President',
    'Asset Management - Internal Client Advisor - Associate',
    'Internal Client Advisor',
    'International Private Bank - Investment Advisor',
    'Barclays Internal Audit - Markets - Credit AVP',
])
def test_internal_and_international_are_not_internships(title):
    assert m._kind(title) is None


@pytest.mark.parametrize('title, contract, kind', [
    ('Sales', 'Internship', 'Stage'),
    ('Internal Client Advisor', 'Internship', 'Stage'),
    ('Stage Sales - Pôle International', '', 'Stage'),
    ('Structured Credit Trading Analyst Trainee', '', 'Stage'),
    ('Sales Intern', 'Full time', 'Stage'),
    ('Sales Intern', 'Permanent contract', None),
    ('Stage Sales', 'Alternance', None),
])
def test_contract_evidence(title, contract, kind):
    assert m._kind(title, contract) == kind


@pytest.mark.parametrize('title, context, accepted', [
    ('Stage Assistant Fund Manager', 'Vos missions Au sein de la Direction Real Estate Fund Management, gestion de fonds immobiliers.', False),
    ('Stage Assistant Sales', "Vous intégrerez l'équipe Middle Office pour traiter les opérations.", False),
    ('Stage Assistant Sales', "Vous intégrerez l'équipe Trading et travaillerez en lien avec Middle Office.", True),
    ('Stage Assistant Sales Repo', 'CACEIS offers middle-office outsourcing. Vous rejoindrez notre équipe Sales et échangerez avec le Middle Office.', True),
    ('Stage Assistant Fund Manager', 'You will join our back office team.', False),
    ('Stage Financial Analyst', 'You will work with analysts / portfolio managers in equity investment teams.', True),
    ('Stagiaire Risk Management – Projets', 'Suivi des classes d’actifs liquides et du risque des portefeuilles.', True),
    ('Stage HR Analyst', 'Our group offers investment opportunities.', False),
])
def test_role_context_distinguishes_own_team_from_partners(title, context, accepted):
    assert m._market_relevant_with_context(title, context) is accepted


def test_socgen_uses_published_contract_not_graduate_degree(monkeypatch):
    url = 'https://careers.societegenerale.com/en/job-offers/trade-senior-sales-test-en'
    listing = f'<a href="{url}">Trade Senior Sales</a>'
    posting = {'@type': 'JobPosting', 'title': 'Trade Senior Sales', 'employmentType': 'Permanent contract'}
    detail = (f'<script type="application/ld+json">{json.dumps(posting)}</script>'
              '<h1>Trade Senior Sales</h1><p>Brussels, Belgium Reference TEST</p>'
              '<p>Responsibilities Sales. Profile required Graduate in a Master Degree. 10 years experience.</p>')
    monkeypatch.setattr(m.requests, 'get', lambda u, **kw: SimpleNamespace(
        text=detail if u == url else listing, raise_for_status=lambda: None))
    assert m._socgen_jobs() == []


def test_rss_and_detail_preserve_risk_role_confirmed_by_description(monkeypatch):
    url = 'https://jobs.amundi.com/offre-de-emploi/emploi-risk-projets_123.aspx'
    title = 'Stagiaire Risk Management - Projets'
    context = 'Suivi des classes d’actifs liquides et du risque des portefeuilles.'
    feed = f'<rss><channel><item><title>{title}</title><link>{url}</link><description>{context}</description></item></channel></rss>'
    detail = f'<h1>{title}</h1><p>Type de contrat Stage</p><p>Localisation Paris Niveau BAC + 5</p><p>{context}</p>'
    monkeypatch.setattr(m.requests, 'get', lambda u, **kw: SimpleNamespace(
        text=detail, content=feed.encode('utf-8'), raise_for_status=lambda: None))
    jobs = m._career_rss_jobs('Amundi', 'jobs.amundi.com', (579,))
    assert len(jobs) == 1
    assert jobs[0].title == title
    assert jobs[0].employment == 'Stage'


@pytest.mark.parametrize('failed_feed', [True, False])
def test_partial_rss_collection_does_not_claim_missing_offers_are_closed(monkeypatch, failed_feed):
    base = 'https://jobs.amundi.com/offre-de-emploi/'
    feed = ('<rss><channel>' + ''.join(
        f'<item><title>Stage Sales {i}</title><link>{base}{i}</link></item>' for i in range(2)
    ) + '</channel></rss>')

    def get(url, **kw):
        if failed_feed and kw['params']['Rss_Contract'] == 1478:
            raise m.requests.Timeout('public feed unavailable')
        return SimpleNamespace(content=feed.encode(), raise_for_status=lambda: None)

    def detail(url, company, title):
        if not failed_feed and url.endswith('/1'):
            raise m.requests.Timeout('public detail unavailable')
        return m.Opportunity(title, company, 'Paris', 'Stage', url, '', 90)

    monkeypatch.setattr(m.requests, 'get', get)
    monkeypatch.setattr(m, '_career_detail', detail)
    with pytest.raises(m._PartialSourceError) as raised:
        m._career_rss_jobs('Amundi', 'jobs.amundi.com', (579, 1478))
    assert raised.value.preserve_cached is failed_feed
    assert len(raised.value.jobs) == (2 if failed_feed else 1)
    assert raised.value.failed_urls == (set() if failed_feed else {base + '1'})


def test_same_selection_for_live_cache_and_delayed_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'CACHE_PATH', tmp_path / 'offers.json')
    monkeypatch.setattr(m, '_source_checks', {})
    monkeypatch.setattr(m, '_source_counts', {})
    valid = m.Opportunity('Stage Financial Analyst', 'Comgest', 'Paris', 'Stage',
                          'https://cm.comgest.com/application-form?jobID=123', '2026-11-01', 90,
                          description='Work with equity investment teams and analysts / portfolio managers.')
    invalid = [replace(valid, title=title, url=valid.url + str(i)) for i, title in enumerate([
        'Stage Fund Execution Reconciliation Team', 'Stage Financements structurés',
        'International Equity Sales - Vice President', 'Trade Senior Sales',
    ])]
    verified = replace(valid, title='Internal Client Advisor', employment='Internship',
                       url=valid.url + 'verified', description='')
    # An explicitly supplied internship contract must survive the legacy cleanup.
    verified = replace(verified, title='Internal Sales Advisor')
    jobs = [valid, verified, *invalid]
    kept = {valid.url, verified.url}
    assert {j.url for j in m._deduplicate_opportunities(jobs)} == kept
    snapshot = {'updated': '2026-11-01T12:00:00+00:00', 'jobs': [asdict(j) for j in jobs], 'errors': []}
    m.CACHE_PATH.write_text(json.dumps({'version': 3, **snapshot}), encoding='utf-8')
    assert {j.url for j in m._read_cache()[1]} == kept
    monkeypatch.setattr(m, '_read_history_document', lambda: {'snapshots': [snapshot]})
    assert {j.url for j in m.load_delayed_opportunities(now=datetime(2026, 11, 9, tzinfo=timezone.utc))[0]} == kept
