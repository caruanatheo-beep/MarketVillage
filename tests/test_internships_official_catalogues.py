import json
from types import SimpleNamespace

import pytest

from internships_project import internships as m


def response(text):
    return SimpleNamespace(text=text, raise_for_status=lambda: None)


def amundi_detail(employer="Amundi Asset Management", start="12/01/2027"):
    posting = {"@type": "JobPosting", "title": "Stage Assistant Sales H/F",
               "hiringOrganization": {"name": employer}, "employmentType": "Stage",
               "jobLocation": {"address": {"addressLocality": "Paris", "addressCountry": "France"}},
               "description": "Assister les Sales dans leurs analyses des marchés."}
    return ('<script type="application/ld+json">' + json.dumps(posting) + '</script>'
            '<h1>Stage Assistant Sales H/F</h1><h2>Date de prise de fonction</h2>'
            f'<p>{start}</p>')


def test_amundi_catalogue_follows_nav_pagination_and_verifies_employer(monkeypatch):
    name = "Amundi · portail groupe"
    listing, host, prefix = m.CAREER_LISTINGS[name]
    next_page = listing + "page/2/"
    offer = f"https://{host}{prefix}579-123-stage-assistant-sales/"
    unrelated = f"https://{host}{prefix}577-456-stage-assistant-sales/"
    pages = {
        listing: f'<nav><a href="{next_page}">2</a><a href="{listing}page/999/">999</a>'
                 '<a href="https://other.invalid/fr/nos-offres/page/2/">2</a></nav>',
        next_page: f'<a href="{offer}">Stage Assistant Sales</a><a href="{unrelated}">Stage Assistant Sales</a>'
                   f'<nav><a href="{next_page}">2</a></nav>',
        offer: amundi_detail(), unrelated: amundi_detail("Crédit Agricole Banque Privée"),
    }
    calls = []
    def get(url, **kw):
        calls.append(url)
        return response(pages[url])
    monkeypatch.setattr(m.requests, "get", get)
    job, = m._career_page_jobs(name, m.CAREER_LISTINGS[name])
    assert (job.company, job.location, job.start_period) == ("Amundi", "Paris, France", "12/01/2027")
    assert job.url == offer
    assert calls.count(next_page) == 1
    assert m.is_trusted_offer_url(offer)
    assert not m.is_trusted_offer_url(offer.replace(host, host + ".evil.invalid"))


def test_lbp_stage_pagination_finds_later_offer_without_inventing_start(monkeypatch):
    listing, host, prefix = m.CAREER_LISTINGS["La Banque Postale"]
    next_page = listing.replace(".html", ".p-2.html")
    offer = f"https://{host}{prefix}2953.html/stage-analyste-risquesdemarche.html"
    pages = {
        listing: f'<nav><a href="{next_page}">2</a></nav>',
        next_page: f'<nav><a href="{next_page}#avoid-menu">Menu</a></nav>'
                   f'<h3>Stage Analyste risques de marché</h3><a href="{offer}">Détails de l’offre</a>',
        offer: '<h1>Stage Analyste risques de marché</h1><p>Type de contrat : Stage</p>'
               '<p>Ville Paris</p><a>Je postule</a><h2>Description de l’offre</h2>'
               '<p>Produire les sensibilités et analyser les dépassements.</p>',
    }
    monkeypatch.setattr(m.requests, "get", lambda url, **kw: response(pages[url]))
    job, = m._career_page_jobs("La Banque Postale", m.CAREER_LISTINGS["La Banque Postale"])
    assert job.location == "Paris" and job.start_period == ""
    assert "sensibilités" in job.description
    teaser = m._jobteaser_from_sitemap_url(
        "https://www.jobteaser.com/fr/job-offers/bb32b1f7-3e88-4e58-a317-7d758826ee7d-"
        "la-banque-postale-stage-analyste-risques-de-marche-f-h")
    assert m._without_jobteaser_duplicates([teaser, job]) == [job]


def test_amundi_direct_offer_replaces_matching_jobteaser_only():
    url = "https://groupecreditagricole.jobs/fr/nos-offres-emploi/579-123-stage-assistant-sales/"
    direct = m._career_detail(url, "Amundi · portail groupe", html_override=amundi_detail())
    teaser = m._jobteaser_from_sitemap_url(
        "https://www.jobteaser.com/fr/job-offers/11111111-2222-3333-4444-555555555555-amundi-stage-assistant-sales-h-f")
    assert m._without_jobteaser_duplicates([teaser, direct]) == [direct]
    other_start = m.replace(teaser, start_period="mars 2027")
    assert m._without_jobteaser_duplicates([other_start, direct]) == [other_start, direct]


def test_incomplete_catalogue_preserves_results_and_reports_failure(monkeypatch):
    listing, host, prefix = m.CAREER_LISTINGS["La Banque Postale"]
    next_page = listing.replace(".html", ".p-2.html")
    offer = f"https://{host}{prefix}2953.html/stage-sales.html"
    def get(url, **kw):
        if url == next_page:
            raise m.requests.Timeout("test")
        if url == listing:
            return response(f'<nav><a href="{next_page}">2</a></nav>'
                            f'<h3>Stage Sales</h3><a href="{offer}">Détails</a>')
        return response('<h1>Stage Sales</h1><p>Ville Paris</p><a>Je postule</a>')
    monkeypatch.setattr(m.requests, "get", get)
    with pytest.raises(m._PartialSourceError) as result:
        m._career_page_jobs("La Banque Postale", m.CAREER_LISTINGS["La Banque Postale"])
    assert len(result.value.jobs) == 1
    assert result.value.preserve_cached is True
