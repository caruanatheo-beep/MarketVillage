"""French source selection and readable cards, using synthetic public offers."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from internships_project import internships as m


@pytest.mark.parametrize("title, accepted", [
    ("Stage - Assistant(e) gestion taux (F/H)", True),
    ("Stage Assistant Fund Manager", True),
    ("Stage Real Estate Fund Manager", False),
    ("Stage Back Office Fund Management", False),
    ("Stage Contrôleur des risques - Actifs Non Cotés - Dette Privée", False),
])
def test_asset_management_selection(title, accepted):
    assert m._market_relevant(title) is accepted


def test_la_francaise_listing_imports_actual_asset_manager(monkeypatch):
    listing, host, prefix = m.CAREER_LISTINGS["La Française"]
    url = f"https://{host}{prefix}?annonce=123"
    pages = {
        listing: '<a href="/fr/offre.html?annonce=123">Stage Assistant gestion taux</a>',
        url: '<h1>Stage Assistant gestion taux</h1><p>Crédit Mutuel Asset Management</p>'
             '<p>Localisation PARIS (75) Niveau BAC + 5</p>'
             '<p>Type de contrat Stage</p><p>Date de publication 05/11/2026</p>',
    }
    monkeypatch.setattr(m.requests, "get", lambda url, **kw: SimpleNamespace(
        text=pages[url], raise_for_status=lambda: None))
    jobs = m._career_page_jobs("La Française", m.CAREER_LISTINGS["La Française"])
    assert len(jobs) == 1
    assert (jobs[0].company, jobs[0].location, jobs[0].url) == ("Crédit Mutuel AM", "PARIS (75)", url)


def test_titres_source_uses_only_trusted_direct_offers(monkeypatch):
    listing, host, prefix = m.CAREER_LISTINGS["Crédit Agricole Titres"]
    url = f"https://{host}{prefix}123-stage-sales-titres"
    pages = {
        listing: f'<a href="{url}">Stage Sales titres</a>'
                 '<a href="https://catitres.teamtailor.com.evil.invalid/jobs/456">Stage Sales</a>',
        url: '<h1>Stage Sales titres</h1><p>Localisation Paris Niveau BAC + 5</p>',
    }
    monkeypatch.setattr(m.requests, "get", lambda url, **kw: SimpleNamespace(
        text=pages[url], raise_for_status=lambda: None))
    jobs = m._career_page_jobs("Crédit Agricole Titres", m.CAREER_LISTINGS["Crédit Agricole Titres"])
    assert [j.url for j in jobs] == [url]
    assert not m.is_trusted_offer_url("https://catitres.teamtailor.com.evil.invalid/jobs/456")


def test_ofi_invest_listing_deduplicates_offers_and_keeps_published_date(monkeypatch):
    listing, host, prefix = m.CAREER_LISTINGS["Ofi Invest"]
    url = f"https://{host}{prefix}stage-trader"
    html = (f'<a href="{url}">Stage Trader</a>'
            f'<a href="{url}">Stage Trader</a>'
            '<a href="https://ofiinvestassetmanagement.flatchr.io.evil.invalid/fr/company/ofiinvestassetmanagement/vacancy/nope">'
            'Stage Trader</a>')
    monkeypatch.setattr(m.requests, "get", lambda requested, **kw: SimpleNamespace(
        text=html, raise_for_status=lambda: None))
    job = m.Opportunity("Stage Trader", "Ofi Invest", "Paris", "Stage",
                        url, "2026-11-05", 90)
    seen = []
    def detail(requested, company, title):
        seen.append(requested)
        return job
    monkeypatch.setattr(m, "_career_detail", detail)

    jobs = m._career_page_jobs("Ofi Invest", m.CAREER_LISTINGS["Ofi Invest"])

    assert seen == [url]
    assert len(jobs) == 1
    assert jobs[0].url == url and jobs[0].published == "2026-11-05"


def test_readable_card_keeps_unknown_dates_and_escapes_content(monkeypatch):
    monkeypatch.setattr(m, "source_checks", lambda: {})
    job = m.Opportunity('Stage Sales <taux>', 'Banque & Gestion', 'Paris', 'Stage',
                        'https://jobs.smartrecruiters.com/bank/123', '2026-11-09', 90,
                        published_inferred=True)
    board = m.render_opportunities([job], [], datetime.now(timezone.utc))
    assert '<small>Lieu</small><span class="job-location">Paris</span>' in board
    assert '<small>Début</small><span>Non précisé</span>' in board
    assert 'Publication inconnue · Détectée le 2026-11-09' in board
    assert 'Stage Sales &lt;taux&gt;' in board
    assert 'Banque &amp; Gestion' in board


@pytest.mark.parametrize('source', ['Site carrière · Amundi', 'JobTeaser · sitemap'])
def test_offer_card_has_one_link_including_its_footer(monkeypatch, source):
    monkeypatch.setattr(m, 'source_checks', lambda: {})
    job = m.Opportunity('Stage Sales', 'Bank', 'Paris', 'Stage',
                        'https://jobs.smartrecruiters.com/bank/123', '2026-11-09', 90,
                        source=source, checked_at='2026-11-09')
    board = m.render_opportunities([job], [], datetime.now(timezone.utc))
    card = board.split('<article ', 1)[1].split('</article>', 1)[0]
    assert card.count('<a ') == 1
    assert 'class="job-card-main"' in card
    assert card.index('class="job-card-footer"') < card.index('</a>')
    assert 'internship-open' not in card
    assert 'Voir l’offre' not in card
    assert source in card
    assert 'target="_blank" rel="noopener noreferrer"' in card
