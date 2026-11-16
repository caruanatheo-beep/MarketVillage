import json
from datetime import datetime, timezone

import pytest

from internships_project import internships as m


@pytest.mark.parametrize("text, expected, month", [
    ("Stage à partir d'avril 2027.", "avril 2027", "2027-04"),
    ("Stage à partir d’avril 2027.", "avril 2027", "2027-04"),
    ("Date de prise de fonction souhaitée : 1er février 2027", "1er février 2027", "2027-02"),
    ("Date de début du stage : 2027-04-01", "2027-04-01", "2027-04"),
    ("Start date 2027/01/04 Publication date 2026/10/23", "2027/01/04", "2027-01"),
    ("Starting date: January 4th, 2027", "January 4th, 2027", "2027-01"),
    ("Starting on 4 January 2027", "4 January 2027", "2027-01"),
    ("Démarrage prévu : avril 2027", "avril 2027", "2027-04"),
    ("Stage à pourvoir dès que possible", "Dès que possible", ""),
    ("Start date: ASAP", "Dès que possible", ""),
    ("Stage à partir de mars/avril 2027", "mars/avril 2027", "2027-04"),
    ("Début de stage à prévoir entre janvier et mars 2027", "entre janvier et mars 2027", "2027-03"),
])
def test_explicit_start_formats(text, expected, month):
    assert m._start_period(text) == expected
    assert m.start_month(expected) == month


@pytest.mark.parametrize("text", [
    "Date de début de diffusion : 01/04/2027",
    "Publication : 1er avril 2027. Date limite : 30 juin 2027.",
    "Nous travaillons sur des marchés depuis avril 2027.",
    "Date de début : 31/02/2027", "Start date: 2027-13-04",
    "Starting on 31 February 2027", "Merci de répondre ASAP",
])
def test_start_never_uses_publication_deadline_or_invalid_date(text):
    assert m._start_period(text) == ""


def detail(body, structured=None, company="Amundi"):
    page = "<h1>Stage Assistant Sales H/F</h1>" + body
    if structured is not None:
        page += '<script type="application/ld+json">' + json.dumps({
            "@type": "JobPosting", "employmentType": "Internship", **structured,
        }) + "</script>"
    return m._career_detail("https://jobs.amundi.com/offre-de-emploi/emploi-sales_123.aspx",
                            company, html_override=page)


def test_talentsoft_city_is_not_the_entire_location_section():
    job = detail("<h2>Localisation du poste</h2><h3>Zone géographique</h3>"
                 "<p>Europe, France, Ile-de-France</p><h3>Ville</h3>"
                 "<p>Montrouge</p><h2>Critères candidat</h2><p>Master</p>",
                 {"jobStartDate": "2027-04-01T00:00:00+02:00"})
    assert (job.location, job.start_period) == ("Montrouge", "2027-04-01")


def test_jsonld_location_list_and_country_object_survive_source_fallbacks():
    job = detail("<p>Rejoignez notre équipe.</p>", {
        "jobLocation": [
            {"address": {"addressLocality": "Paris", "addressCountry": {"name": "France"}}},
            {"address": {"addressLocality": "London", "addressCountry": "UK"}},
        ], "jobImmediateStart": True,
    }, company="Kepler Cheuvreux")
    assert job.location == "Paris, France / London, UK"
    assert job.start_period == "Dès que possible"


def test_structured_description_is_read_even_when_visible_page_is_longer():
    job = detail("<p>Localisation : Paris</p><p>" + "Notre banque. " * 100 + "</p>", {
        "description": "Stage à partir d’avril 2027.",
        "datePosted": "2026-01-01", "validThrough": "2027-05-01",
    })
    assert job.location == "Paris"
    assert job.start_period == "avril 2027"


def test_headquarters_and_publication_are_not_job_metadata():
    job = detail("<p>Localisation : Nanterre</p>", {
        "hiringOrganization": {"address": {"addressLocality": "London"}},
        "datePosted": "2026-01-01", "validThrough": "2027-05-01",
    })
    assert job.location == "Nanterre"
    assert job.start_period == ""


def test_cached_description_can_recover_missing_start_without_network(monkeypatch):
    job = m.Opportunity("Stage Sales", "Bank", "Paris", "Stage",
                        "https://jobs.smartrecruiters.com/bank/1", "2026-11-01", 100)
    previous = m.replace(job, description="Stage à partir d’avril 2027.")
    monkeypatch.setattr(m, "_refresh_previous_jobs", {job.url: previous})
    assert m._cached_detail(job).start_period == "avril 2027"


@pytest.mark.parametrize("title, expected", [
    ("Internship: Group Market Risk [Jan to May 2027]", "January 2027"),
    ("6 month Internship - Credit Sales: Jan - June 2027", "January 2027"),
    ("Sales Internship November - February 2027", "November 2026"),
    ("Stage Sales - Janvier 2027", "Janvier 2027"),
])
def test_title_interval_uses_start_not_end(title, expected):
    assert m._title_period(title) == expected


def test_old_cache_recovers_title_interval_without_rewriting_original(tmp_path, monkeypatch):
    job = m.Opportunity("Internship: Market Risk [Jan to May 2027]", "Bank", "Paris", "Stage",
                        "https://jobs.smartrecruiters.com/bank/1", "2026-11-01", 100,
                        start_period="May 2027")
    path = tmp_path / "internships.json"
    path.write_text(json.dumps({"version": 3, "updated": datetime.now(timezone.utc).isoformat(),
                               "jobs": [m.asdict(job)]}), encoding="utf-8")
    original = path.read_bytes()
    monkeypatch.setattr(m, "CACHE_PATH", path)
    result = m._read_cache()
    assert result[1][0].start_period == "January 2027"
    assert path.read_bytes() == original


def test_bpce_reads_explicit_start_field_and_retains_description(monkeypatch):
    from types import SimpleNamespace
    row = {"intitule": "Stage Sales", "organization": "Natixis", "ville": "Charenton-le-Pont",
           "jobtype": "Stage", "url": "https://recrutement.bpce.fr/job/stage-sales",
           "date_de_debut": "2027-04-01", "description": "Publié le 1 janvier 2027."}
    monkeypatch.setattr(m.requests, "get", lambda *a, **kw: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: [row]))
    job, = m._bpce_open_data_jobs()
    assert (job.location, job.start_period) == ("Charenton-le-Pont", "2027-04-01")
    assert job.description == row["description"]


@pytest.mark.parametrize("title, expected", [
    ("Stage - 6 mois - Assistant Sales F/H", "Assistant Sales"),
    ("Stage 6 mois Assistant Sales", "Assistant Sales"),
    ("Internship: Market Risk Management", "Internship: Market Risk Management"),
    ("6 month Internship - Fixed Income Credit Sales", "Internship - Fixed Income Credit Sales"),
    ("6-month internship – Quantitative Research", "internship – Quantitative Research"),
    ("Internship - 6 months - Sales", "Internship - Sales"),
    ("Assistant Sales - Stage de 6 mois", "Assistant Sales"),
    ("Quantitative Research (6 month Internship)", "Quantitative Research (Internship)"),
    ("Equity Sales Intern", "Equity Sales Intern"),
    ("International Sales", "International Sales"),
    ("Internal Market Risk Analyst", "Internal Market Risk Analyst"),
    ("Stage", "Stage"),
])
def test_display_title_removes_only_internship_labels(title, expected):
    assert m._display_offer_title(title) == expected


@pytest.mark.parametrize('title,expected', [
    ('Assistant Sales (H/F)', 'Assistant Sales'),
    ('H/F - Analyste Produits Structurés', 'Analyste Produits Structurés'),
    ('Stage - 6 mois - Assistant Sales F/H', 'Assistant Sales'),
    ('Sales (f/m/d)', 'Sales'), ('Sales [m/w/d]', 'Sales'),
    ('Sales (m/w/divers)', 'Sales'), ('Sales (m/f/diverse)', 'Sales'),
    ('Sales (m/f/x)', 'Sales'), ('Sales (all genders)', 'Sales'),
    ('Intern (all genders) - Equity Derivatives', 'Intern - Equity Derivatives'),
    ('Financial Controller Trading H/F H/F', 'Financial Controller Trading'),
    ('Sales F H', 'Sales'), ('Sales F M D', 'Sales'),
    ('H F - Sales', 'Sales'), ('Sales - F/H - Paris', 'Sales - Paris'),
    ('Structuration (QIS) f/m/d)', 'Structuration (QIS)'),
    ('ETF &amp; Indiciel H/F', 'ETF & Indiciel'),
    ('OCIO Solutions - Advisory (Gestion Diversifiée) H/F',
     'OCIO Solutions - Advisory (Gestion Diversifiée)'),
    ('Sales (FX & Rates)', 'Sales (FX & Rates)'),
    ('Analyst - Delta One (D1)', 'Analyst - Delta One (D1)'),
    ('Assistant(e) Sales', 'Assistant(e) Sales'),
    ('2027 Global Markets Graduate Programme - Paris', 'Global Markets Graduate Programme - Paris'),
    ('FICC Sales', 'FICC Sales'), ('HF Trading Analyst', 'HF Trading Analyst'),
    ('Quantitative Research (PhD)', 'Quantitative Research (PhD)'),
    ('Assistant de gestion (Quantitative, Finance, Data F/H) – S1 2027',
     'Assistant de gestion (Quantitative, Finance, Data)'),
])
def test_display_title_removes_gender_not_role_qualifications(title, expected):
    result = m._display_offer_title(title)
    assert result == expected
    assert m._display_offer_title(result) == expected


@pytest.mark.parametrize('title,location,expected', [
    ('2027 Credit Portfolio Management Summer Intern – Miami', 'Miami, United States', 'Credit Portfolio Management Summer Intern'),
    ('2027 Credit Portfolio Management Summer Intern – New York', 'New York, NY', 'Credit Portfolio Management Summer Intern'),
    ('Global Market, FX Sales Desk – January 2027', 'Paris', 'Global Market, FX Sales Desk'),
    ('Fixed Income Credit Sales: Jan - June 2027', 'Paris', 'Fixed Income Credit Sales'),
    ('Assistant Trading (Janvier 2027)', 'Paris', 'Assistant Trading'),
    ('Sales Activation - 6 months (July – December 2027)', 'Singapore', 'Sales Activation'),
    ('Global Markets, Corporate Sales & Structuring [Jan - Jun 2027]', 'Singapore',
     'Global Markets, Corporate Sales & Structuring'),
    ('Sales (FX & Rates) - London - 2027', 'Londres, Royaume-Uni', 'Sales (FX & Rates)'),
    ('Quantitative Trading Internship (Singapore) - 2027', 'Singapore', 'Quantitative Trading Internship'),
    ('Markets – Sales and Trading, Off-Cycle Internship, Paris – France, 2027', 'Paris, France',
     'Markets – Sales and Trading, Off-Cycle Internship'),
    ('Sales - London', '', 'Sales - London'),
    ('Sales - London', 'New York', 'Sales - London'),
    ('London Stock Exchange Sales Intern', 'London', 'London Stock Exchange Sales Intern'),
    ('EMEA Sales (PhD) - Paris', 'Paris', 'EMEA Sales (PhD)'),
    ('Delta One Structuring (D1)', 'Paris', 'Delta One Structuring (D1)'),
    ('Graduate Equity Analyst (2027 Start - Chicago)', 'Chicago', 'Graduate Equity Analyst'),
    ('Quantitative Trading Internship (Summer 2027 - Shanghai)', 'Shanghai', 'Quantitative Trading Internship (Summer)'),
    ('Summer 2027 Quantitative Research', 'Paris', 'Summer Quantitative Research'),
    ('Off-Cycle Internship - Sales - Paris 2027', 'Paris', 'Off-Cycle Internship - Sales'),
    ('Seasonal Internship - Quant - London', 'London', 'Seasonal Internship - Quant'),
])
def test_display_title_removes_documented_location_and_calendar_metadata(title, location, expected):
    result = m._display_offer_title(title, location)
    assert result == expected
    assert m._display_offer_title(result, location) == expected


def test_card_keeps_original_title_for_tracking_and_tooltip(monkeypatch):
    monkeypatch.setattr(m, "source_checks", lambda: {})
    job = m.Opportunity("Stage - 6 mois - Sales <FX>", "Bank", "Paris", "Stage",
                        "https://jobs.smartrecruiters.com/bank/1", "2026-11-01", 100)
    board = m.render_opportunities([job], [], datetime.now(timezone.utc))
    assert '>Sales &lt;FX&gt;</strong>' in board
    assert 'title="Stage - 6 mois - Sales &lt;FX&gt;"' in board
    assert 'data-offer-title="Stage - 6 mois - Sales &lt;FX&gt;"' in board
    assert job.title == "Stage - 6 mois - Sales <FX>"


@pytest.mark.parametrize("location, title, expected", [
    ("- Marex Careers Career opportunities Quantitative Researcher Internship Paris, FR , Front Office",
     "Quantitative Researcher Internship", "Paris, FR"),
    ("Apply Casablanca, Région de Casablanca-Settat, Morocco", "Stage Sales", "Casablanca, Région de Casablanca-Settat, Morocco"),
    ("Apply for this job New York, NY, United States", "Stage Sales", "New York, NY, United States"),
    ("Francfort, Hesse, Allemagne", "Stage Sales", "Francfort, Hesse, Allemagne"),
    ("Singapore, Marex Solutions, Full-Time", "Stage Sales", "Singapore"),
    ("Fontenay sous Bois", "Stage Sales", "Fontenay sous Bois"),
    ("Careers Career opportunities Apply", "Stage Sales", "Non précisé"),
    ("", "Stage Sales", ""),
])
def test_location_removes_navigation_and_job_metadata(location, title, expected):
    assert m._clean_job_location(location, title) == expected


def test_marex_reads_location_after_real_heading_not_document_title():
    title = "Quantitative Researcher Internship"
    page = (f"<html><head><title>{title} - Marex Careers</title></head><body>"
            f"<h1>Career opportunities</h1><h2>{title}</h2>"
            "<span>Paris, FR</span><span>,</span><span>Front Office</span>"
            "<span>,</span><span>Full-Time</span><p>About Marex</p></body></html>")
    job = m._career_detail("https://www.marex.com/careers/career-opportunities/quantitative-researcher-internship",
                           "Marex", html_override=page)
    assert job.location == "Paris, FR"


def test_socgen_location_skips_apply_button(monkeypatch):
    from types import SimpleNamespace
    url = "https://careers.societegenerale.com/en/job-offers/stage-pricing-123-en"
    title = "Stage Pricing Equity"
    page = (f"<head><title>{title} - Casablanca, Morocco</title></head>"
            f"<span>Internship</span><h1>{title}</h1><a>Apply</a>"
            "<span>Casablanca, Région de Casablanca-Settat, Morocco</span>"
            "<span>Reference</span><span>123ABC</span><h2>Responsibilities</h2>")
    monkeypatch.setattr(m.requests, "get", lambda requested, **kw: SimpleNamespace(
        text=f'<a href="{url}">{title}</a>' if requested.endswith('all-job-offers') else page,
        raise_for_status=lambda: None))
    job, = m._socgen_jobs()
    assert job.location == "Casablanca, Région de Casablanca-Settat, Morocco"


def test_existing_and_source_cached_locations_are_cleaned_without_mutating_cache(tmp_path, monkeypatch):
    job = m.Opportunity("Quantitative Researcher Internship", "Marex",
                        "- Marex Careers Career opportunities Quantitative Researcher Internship Paris, FR , Front Office",
                        "Stage", "https://www.marex.com/careers/career-opportunities/quantitative-researcher-internship",
                        "2026-11-01", 100)
    path = tmp_path / "internships.json"
    path.write_text(json.dumps({"version": 3, "updated": datetime.now(timezone.utc).isoformat(),
                               "jobs": [m.asdict(job)]}), encoding="utf-8")
    original = path.read_bytes()
    monkeypatch.setattr(m, "CACHE_PATH", path)
    assert m._read_cache()[1][0].location == "Paris, FR"
    assert m._deduplicate_opportunities([job])[0].location == "Paris, FR"
    assert path.read_bytes() == original
