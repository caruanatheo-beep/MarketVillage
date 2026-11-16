"""Regressions from the public employer/snapshot audit of November 2026."""
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from internships_project import internships as jobs


@pytest.mark.parametrize('title', [
    'H/F - Assistant Juridique en Asset Management – Juillet 2027',
    'Internship: Group Operations & Technology – Markets Operations [January - May 2027]',
    'Clearing Operations Derivatives Analyst (VIE)',
    'Branch Operations Lead Trainee - Middle Virginia Market - Stafford, VA',
    'Stage Gestionnaire Operations Equity Vanilla F H',
    'Internship: Global Consumer Financial Services, CFS Finance, Strategy and Execution',
    'Stage Contrôleur de gestion Market Data F H',
    'Stage Contoleur De Gestion Market Data F H',
    'Stage Analyste reporting financier junior H/F',
    'Junior Operations Analyst',
])
def test_out_of_scope_titles_cannot_borrow_market_context(title):
    assert not jobs._market_relevant_with_context(title, 'Work with sales, trading and global markets teams.')


@pytest.mark.parametrize('title', [
    'Stage Assistant Sales - Derivatives Clearing Services',
    'Securities Lending Sales Internship', 'Repo Trading Internship',
    'Stage Sales - Clients Corporates', 'Treasury Sales Graduate',
    'Stage Analyste Risques de Marché', 'Stage Gestion de portefeuille obligataire',
])
def test_market_desks_and_risk_roles_remain_eligible(title):
    assert jobs._market_relevant_with_context(title, 'Work with middle office and clearing operations.')


def test_hsbc_macro_research_needs_financial_research_context():
    title = 'Stage - Recherche en Macroéconomie (f/m/d)'
    assert jobs._market_candidate(title)
    assert jobs._market_relevant_with_context(title, 'Direction des études économiques rattachée à Global Research.')
    assert not jobs._market_relevant_with_context(title, 'Etudes générales sans contexte financier.')
    assert jobs._family(title) == 'Quant / Research'


def career_page(title, *, body='', structured=None):
    return f'<h1>{title}</h1>{body}<script type="application/ld+json">' + json.dumps({
        '@type': 'JobPosting', 'title': title, 'employmentType': 'Internship',
        'jobLocation': {'address': {'addressLocality': 'Paris', 'addressCountry': 'FR'}},
        **(structured or {}),
    }) + '</script>'


def test_related_market_offer_does_not_replace_accounting_title():
    page = career_page('Stage Analyste reporting financier junior H/F', body=(
        '<p>Reporting financier</p><h2>Financial & International Markets Trainee</h2>'))
    assert jobs._career_detail('https://jobs.amundi.com/offre-de-emploi/emploi-sales_123.aspx', 'BNP Paribas', html_override=page) is None


def test_primary_heading_without_jsonld_wins_over_related_jobs():
    page = '<h1>Stage Assistant Juridique en Asset Management</h1><h2>Stage Sales</h2>Paris'
    assert jobs._career_detail('https://jobs.amundi.com/offre-de-emploi/emploi-sales_123.aspx', 'Lazard', html_override=page) is None


def test_structured_title_wins_over_unrelated_market_heading():
    page = career_page('Stage Assistant Sales', structured={'title': 'Stage Quantitative Research'})
    result = jobs._career_detail('https://jobs.amundi.com/offre-de-emploi/emploi-sales_123.aspx', 'Bank', html_override=page)
    assert result and result.title == 'Stage Quantitative Research'


@pytest.mark.parametrize('offset,accepted', [(-1, False), (0, True), (1, True)])
def test_expiry_applies_to_public_details_and_retained_cache(offset, accepted):
    deadline = (datetime.now(timezone.utc).date() + timedelta(days=offset)).isoformat()
    page = career_page('Stage Sales', structured={'validThrough': deadline+'T23:59:59Z'})
    result = jobs._career_detail('https://jobs.amundi.com/offre-de-emploi/emploi-sales_123.aspx', 'Bank', html_override=page)
    assert bool(result) == accepted
    cached = jobs.Opportunity('Stage Sales', 'Bank', 'Paris', 'Stage', 'https://jobs.amundi.com/offre-de-emploi/emploi-sales_123.aspx', '', 10,
                              deadline=deadline)
    assert jobs._eligible_offer(cached) == accepted


@pytest.mark.parametrize('location1,location2', [
    ('Miami, Florida, United States', 'Miami'),
    ('New York, New York, United States', 'New York, NY'),
    ('Frankfurt, Hesse, Germany', 'Francfort, Allemagne'),
    ('Milan - via Tomacelli, Italy', 'Milan, Italy'),
    ('Singapore, Singapore', 'Singapour'),
])
def test_same_role_merges_employer_location_variants(location1, location2):
    a = jobs.Opportunity('Stage - Global Markets Sales', 'BNP Paribas', location1, 'Stage',
                         'https://example.test/a', '', 10)
    b = replace(a, location=location2, url='https://example.test/b')
    assert len(jobs._deduplicate_opportunities([a, b])) == 1
    assert len(jobs._deduplicate_opportunities([a, replace(b, start_period='January 2027'),
                                               replace(b, start_period='June 2027')])) == 3


def test_vie_suffix_does_not_duplicate_same_role_or_drop_start():
    a = jobs.Opportunity('Market Analyst Western and Central Europe', 'Euronext', 'Milan, Italy', 'VIE',
                         'https://example.test/a', '', 10, start_period='January 2027')
    b = replace(a, title=a.title+' (VIE)', start_period='', url='https://example.test/b')
    result = jobs._deduplicate_opportunities([a, b])
    assert len(result) == 1 and result[0].start_period == 'January 2027'


def test_cfm_filter_city_all_does_not_override_real_workplace():
    page = ('<label>City</label><span>All</span><h1>Portfolio Engineering - Internship</h1>'
            '<span>Paris, 75, FR</span><h2>ABOUT CFM</h2><p>Quantitative asset management.</p>')
    result = jobs._career_detail('https://jobs.cfm.com/job/Paris-Portfolio-Engineering-Internship-75/1372636755/',
                                'CFM', html_override=page)
    assert result and result.location == 'Paris, 75, FR'


@pytest.mark.parametrize('country,description,expected', [
    ('United States of America', 'Based in New York, join our credit portfolio team.', 'New York, États-Unis'),
    ('United Kingdom', 'Based in New York, join our credit portfolio team.', 'Madison Ave Corp'),
    ('United States of America', 'Our head office is in New York.', 'Madison Ave Corp'),
])
def test_building_name_is_replaced_only_by_documented_workplace(monkeypatch, country, description, expected):
    def reply(payload):
        return SimpleNamespace(json=lambda: payload, status_code=200, raise_for_status=lambda: None)
    monkeypatch.setattr(jobs.requests, 'post', lambda *a, **kw: reply({'total': 1, 'jobPostings': [{
        'title': '2027 Credit Portfolio Management Summer Intern – New York',
        'externalPath': '/job/Madison-Ave-Corp/1', 'locationsText': 'Madison Ave Corp'}]}))
    monkeypatch.setattr(jobs.requests, 'get', lambda *a, **kw: reply({'jobPostingInfo': {
        'location': 'Madison Ave Corp', 'country': {'descriptor': country}, 'jobDescription': description}}))
    monkeypatch.setattr(jobs, '_cached_detail', lambda job: replace(job, description=description))
    result = jobs._workday_jobs('Santander CIB', jobs.WORKDAY['Santander CIB'])
    assert len(result) == 1 and result[0].location == expected


@pytest.mark.parametrize('status,can_apply,count', [(200, False, 0), (404, None, 0), (410, None, 0),
                                                   (200, True, 1), (200, None, 1)])
def test_closed_workday_posting_is_removed_even_if_listing_still_contains_it(monkeypatch, status, can_apply, count):
    def response(payload, code=200):
        return SimpleNamespace(json=lambda: payload, status_code=code, raise_for_status=lambda: None)
    monkeypatch.setattr(jobs.requests, 'post', lambda *a, **kw: response({'total': 1, 'jobPostings': [{
        'title': 'Markets Sales Internship', 'externalPath': '/job/Paris/1', 'locationsText': 'Paris'}]}))
    monkeypatch.setattr(jobs.requests, 'get', lambda *a, **kw: response({'jobPostingInfo': {
        'canApply': can_apply, 'location': 'Paris', 'jobDescription': 'Institutional sales desk'}}, status))
    monkeypatch.setattr(jobs, '_cached_detail', lambda job: None)
    assert len(jobs._workday_jobs('NatWest Markets', jobs.WORKDAY['NatWest Markets'])) == count
