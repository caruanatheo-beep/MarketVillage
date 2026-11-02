from datetime import date, datetime, timezone

from datetime import timedelta

from internships_project.internships import (
    Opportunity,
    _canonical_title, _opportunity, _smart_jobs, _socgen_jobs, _start_period, _title_period,
    _vie_jobs, _workday_jobs, _workday_publication_date, mark_opened_offer_applied,
    render_opportunities, render_tracking,
    export_tracking, import_tracking, normalize_status, save_offer_feedback, save_tracking, start_month,
)
from internships_project.internships import _amundi_jobs, _arkea_jobs, _bnp_cib_jobs, _ca_cib_jobs, _career_detail, _career_page_jobs
from internships_project.internships import _read_cache
from internships_project.internships import _bpce_open_data_jobs, CACHE_SECONDS
from internships_project.internships import _jobteaser_from_sitemap_url, _jobteaser_jobs
from internships_project.internships import _canonical_company, _company_icon, _market_relevant
from internships_project.internships import _jsonld_job_posted
from internships_project.source_coverage import SOURCE_COVERAGE
import json
import pytest
from dataclasses import asdict
from internships_project import state_store


def test_requested_source_inventory_has_no_palatine_and_distinguishes_portals():
    assert CACHE_SECONDS == 3600
    assert "Banque Palatine" not in SOURCE_COVERAGE
    assert "Palatine AM" not in SOURCE_COVERAGE
    assert SOURCE_COVERAGE["CACEIS"].status == "connected"
    assert SOURCE_COVERAGE["Tikehau Capital"].status == "portal"
    assert SOURCE_COVERAGE["CFM"].status == "connected"
    assert SOURCE_COVERAGE["BGC"].status == "blocked"
    assert SOURCE_COVERAGE["CPR AM"].via == "Amundi"


def test_jobteaser_url_extracts_only_explicit_role_and_location():
    base = "https://www.jobteaser.com/fr/job-offers/11111111-2222-3333-4444-555555555555-"
    job = _jobteaser_from_sitemap_url(base + "oddo-bhf-stage-assistant-trading-janvier-2027")
    assert job is not None
    assert (job.company, job.kind, job.location, job.published) == ("ODDO BHF", "Stage", "", "")
    assert job.start_period == "Janvier 2027"
    assert job.url.startswith(base)
    paris = _jobteaser_from_sitemap_url(base + "hsbc-continental-europe-stage-sales-trading-paris")
    assert paris is not None and paris.location == "Paris"
    vie = _jobteaser_from_sitemap_url(base + "societe-generale-v-i-e-sales-trading-frankfurt")
    assert vie is not None and (vie.kind, vie.location) == ("VIE", "Frankfurt")
    assert _jobteaser_from_sitemap_url(base + "amundi-stage-marketing-etf-paris") is None
    assert _jobteaser_from_sitemap_url(base + "aew-stage-analyste-marches-immobiliers-paris") is None


def test_jobteaser_public_sitemap_is_cached_without_opening_offer_pages(tmp_path, monkeypatch):
    from internships_project import internships

    index = (b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
             b'<sitemap><loc>https://assets-cf.jobteaser.com/sitemaps/job_ads_sitemap.xml</loc></sitemap>'
             b'</sitemapindex>')
    offer = ("https://www.jobteaser.com/fr/job-offers/11111111-2222-3333-4444-555555555555-"
             "oddo-bhf-stage-assistant-trading-janvier-2027")
    sitemap = (f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               f'<url><loc>{offer}</loc><lastmod>2026-10-25</lastmod></url></urlset>').encode()
    calls = []
    class Response:
        def __init__(self, content):
            self.content = content
        def raise_for_status(self):
            pass
    def fake_get(url, **kwargs):
        calls.append(url)
        return Response(index if url == internships.JOBTEASER_INDEX else sitemap)
    monkeypatch.setattr(internships.requests, "get", fake_get)
    monkeypatch.setattr(internships, "JOBTEASER_CACHE_PATH", tmp_path / "jobteaser_sitemap_cache.json")
    first = _jobteaser_jobs()
    second = _jobteaser_jobs()
    assert [job.url for job in first] == [offer]
    assert [job.url for job in second] == [offer]
    assert calls == [internships.JOBTEASER_INDEX, "https://assets-cf.jobteaser.com/sitemaps/job_ads_sitemap.xml"]


def test_jobteaser_duplicate_yields_to_direct_employer_offer(monkeypatch):
    from internships_project import internships

    direct = _opportunity("Stage - Assistant Trading Janvier 2027", "ODDO", "Paris", "Stage",
                          "https://jobs.smartrecruiters.com/ODDO/123", "2026-10-24")
    assert direct is not None
    teaser = _jobteaser_from_sitemap_url(
        "https://www.jobteaser.com/fr/job-offers/11111111-2222-3333-4444-555555555555-"
        "oddo-bhf-stage-assistant-trading-janvier-2027")
    assert teaser is not None
    monkeypatch.setattr(internships, "SMARTRECRUITERS", {"ODDO": "ODDO"})
    monkeypatch.setattr(internships, "GREENHOUSE", {})
    monkeypatch.setattr(internships, "WORKDAY", {})
    monkeypatch.setattr(internships, "CAREER_LISTINGS", {})
    monkeypatch.setattr(internships, "_smart_jobs", lambda *args: [direct])
    monkeypatch.setattr(internships, "_jobteaser_jobs", lambda *args: [teaser])
    for name in ("_socgen_jobs", "_vie_jobs", "_ca_cib_jobs", "_bnp_cib_jobs", "_bnp_tal_jobs",
                 "_amundi_jobs", "_arkea_jobs", "_bpce_open_data_jobs"):
        monkeypatch.setattr(internships, name, lambda *args: [])
    jobs, errors = internships._fetch_opportunities()
    assert not errors
    assert [job.url for job in jobs] == [direct.url]


def test_source_checks_distinguish_results_empty_and_error_and_survive_cache(tmp_path, monkeypatch):
    from internships_project import internships

    offer = _opportunity("Trading Intern", "Bank A", "Paris", "Stage",
                         "https://jobs.smartrecruiters.com/BankA/123", "2026-10-25")
    assert offer is not None
    monkeypatch.setattr(internships, "SMARTRECRUITERS", {"a": "Bank A", "b": "Bank B", "c": "Bank C"})
    monkeypatch.setattr(internships, "GREENHOUSE", {})
    monkeypatch.setattr(internships, "WORKDAY", {})
    monkeypatch.setattr(internships, "CAREER_LISTINGS", {})
    monkeypatch.setattr(internships, "_source_checks", {})
    monkeypatch.setattr(internships, "_cache", None)
    monkeypatch.setattr(internships, "CACHE_PATH", tmp_path / "internships_cache.json")

    def smart(slug, _company):
        if slug == "c":
            raise internships.requests.Timeout("unavailable")
        return [offer] if slug == "a" else []

    monkeypatch.setattr(internships, "_smart_jobs", smart)
    for name in ("_socgen_jobs", "_vie_jobs", "_ca_cib_jobs", "_bnp_cib_jobs", "_bnp_tal_jobs",
                 "_amundi_jobs", "_arkea_jobs", "_bpce_open_data_jobs", "_jobteaser_jobs"):
        monkeypatch.setattr(internships, name, lambda *args: [])

    jobs, errors, updated = internships.refresh_opportunities()
    assert [job.url for job in jobs] == [offer.url]
    assert "Bank C: délai dépassé" in errors
    checks = internships.source_checks()
    assert checks["Bank A"]["status"] == "ok" and checks["Bank A"]["count"] == 1
    assert checks["Bank B"]["status"] == "empty" and checks["Bank B"]["count"] == 0
    assert checks["Bank C"]["status"] == "error" and checks["Bank C"]["count"] is None
    assert all(check["checked_at"] for check in checks.values())
    board = internships.render_opportunities(jobs, errors, updated)
    assert "État des sources" in board
    assert "Aucune offre remontée" in board
    assert "Vérification impossible" in board

    monkeypatch.setattr(internships, "_source_checks", {})
    internships._read_cache()
    assert internships.source_checks()["Bank B"]["count"] == 0


def test_source_connector_cache_reuses_fresh_result_and_records_duration(tmp_path, monkeypatch):
    from internships_project import internships

    job = _opportunity("Trading Intern", "Bank", "Paris", "Stage",
                       "https://jobs.example.com/trading-intern", "2026-10-20")
    assert job is not None
    monkeypatch.setattr(internships, "CACHE_PATH", tmp_path / "internships_cache.json")
    monkeypatch.setattr(internships, "_source_job_cache", {})
    monkeypatch.setattr(internships, "_source_job_cache_path", None)
    calls = []

    def fetch():
        calls.append(True)
        return [job]

    first, first_check, first_error = internships._collect_source("Test bank", fetch, (), False)
    second, second_check, second_error = internships._collect_source(
        "Test bank", lambda: (_ for _ in ()).throw(AssertionError("cache should be used")), (), False
    )
    assert calls == [True]
    assert first == second == [job]
    assert first_check["cache_status"] == "live"
    assert isinstance(first_check["duration_ms"], int)
    assert second_check["cache_status"] == "fresh"
    assert not first_error and not second_error


def test_expensive_source_intervals_are_longer_than_hourly_feeds():
    from internships_project import internships

    assert internships._source_refresh_seconds("JobTeaser · sitemap", internships._jobteaser_jobs) == 24 * 3600
    assert internships._source_refresh_seconds("ODDO BHF", internships._oddo_jobs) == 4 * 3600
    assert internships._source_refresh_seconds("Bank", internships._smart_jobs) == 3600


def test_jobteaser_natixis_slug_yields_to_mirova_direct_offer_in_cache(tmp_path, monkeypatch):
    from internships_project import internships

    direct = _opportunity(
        "Stage - 6 mois -Analyste Quantitatif F/H", "Mirova", "Paris", "Stage",
        "https://recrutement.bpce.fr/job/stage-6-mois-analyste-quantitatif-f-h", "",
        "janvier 2027",
    )
    teaser = _jobteaser_from_sitemap_url(
        "https://www.jobteaser.com/fr/job-offers/3c962641-3206-4ef3-909c-76a9206520a9-"
        "natixis-stage-6-mois-analyste-quantitatif-f-h"
    )
    assert direct is not None and teaser is not None
    direct = internships.replace(direct, source="Site carrière · BPCE Open Data")
    jobs = internships._without_jobteaser_duplicates([teaser, direct])
    assert [job.url for job in jobs] == [direct.url]
    assert jobs[0].company == "Mirova" and jobs[0].start_period == "janvier 2027"

    cache = tmp_path / "internships_cache.json"
    cache.write_text(json.dumps({
        "version": 3, "updated": "2026-10-25T00:00:00+00:00",
        "jobs": [asdict(teaser), asdict(direct)], "errors": [],
    }), encoding="utf-8")
    monkeypatch.setattr(internships, "CACHE_PATH", cache)
    _, cached, _ = internships._read_cache()
    assert [job.url for job in cached] == [direct.url]


def test_jobteaser_does_not_merge_unrelated_or_different_natixis_roles():
    from internships_project import internships

    direct = _opportunity(
        "Stage - 6 mois -Analyste Quantitatif F/H", "Mirova", "Paris", "Stage",
        "https://recrutement.bpce.fr/job/stage-6-mois-analyste-quantitatif-f-h", "",
    )
    other_role = _jobteaser_from_sitemap_url(
        "https://www.jobteaser.com/fr/job-offers/11111111-2222-3333-4444-555555555555-"
        "natixis-stage-assistant-trading"
    )
    unrelated = _jobteaser_from_sitemap_url(
        "https://www.jobteaser.com/fr/job-offers/11111111-2222-3333-4444-555555555556-"
        "oddo-bhf-stage-6-mois-analyste-quantitatif-f-h"
    )
    assert direct and other_role and unrelated
    jobs = internships._without_jobteaser_duplicates([direct, other_role, unrelated])
    assert {job.url for job in jobs} == {direct.url, other_role.url, unrelated.url}


def test_company_icon_uses_official_host_and_unknown_company_keeps_initials():
    assert _company_icon("Société Générale") == "https://www.societegenerale.com/favicon.ico"
    assert _company_icon("BNP Paribas Mission Handicap") == "https://group.bnpparibas/favicon.ico"
    assert _company_icon("Employeur inconnu") == ""
    job = _opportunity("Stage Sales Trading", "Société Générale", "Paris", "Stage",
                       "https://careers.societegenerale.com/fr/emploi/test", "2026-10-25")
    assert job is not None
    card = render_opportunities([job], [], datetime.now(timezone.utc))
    assert 'src="https://www.societegenerale.com/favicon.ico"' in card
    assert 'onerror="this.remove()"' in card


def test_market_role_filter_preserves_desk_jobs_and_rejects_support_roles():
    for title in ("Stage Broker Assistant Repo", "Stage Pricing Analyst FX Swaps",
                  "Stage Portfolio Manager Fixed Income", "VIE Liquidity Sales",
                  "Stage Négociation buy-side", "Stage Market Risk",
                  "Stage Sales Assistant Marketing Produits Structurés"):
        assert _market_relevant(title), title
    for title in ("Stage Trading Back Office", "Stage Treasury Corporate Finance",
                  "Stage Sales Administration", "Stage Private Equity", "Stage FX Settlement",
                  "Stage OTC Derivatives Collateral Officer",
                  "Stage - 6 mois - Analyste Marchés Immobiliers F/H",
                  "Stage - Chargé de clientèle Marché Immobilier HF H/F"):
        assert not _market_relevant(title), title
    assert _market_relevant("Stage Analyste Marchés Financiers")
    assert _canonical_company("BNP Paribas AM") == _canonical_company("BNP Paribas Asset Management")


def test_caceis_listing_keeps_only_official_direct_market_jobs(monkeypatch):
    class Response:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            pass
    offer = "https://jobs.caceis.com/offre-de-emploi/emploi-stage-assistant-sales-repo_123.aspx"
    def fake_get(url, **kwargs):
        if url == offer:
            return Response('<h1>Stage - Assistant Sales Repo</h1><p>Type de contrat Stage '
                            'Date de parution 23/10/2026 Date prévue de prise de fonction 01/04/2027 '
                            'Localisation du poste Zone géographique Europe, France Ville Paris '
                            'Critères candidat Bac + 5</p>')
        return Response('<a href="/offre-de-emploi/emploi-stage-assistant-sales-repo_123.aspx">Stage - Assistant Sales Repo</a>'
                        '<a href="https://example.com/job/fake">Stage Trader</a>'
                        '<a href="/offre-de-emploi/emploi-stage-marketing_124.aspx">Stage Marketing</a>')
    monkeypatch.setattr("internships_project.internships.requests.get", fake_get)
    jobs = _career_page_jobs("CACEIS", (
        "https://jobs.caceis.com/pages/offre/listeoffre.aspx?lcid=1036", "jobs.caceis.com", "/offre-de-emploi/"))
    assert len(jobs) == 1
    assert (jobs[0].company, jobs[0].location, jobs[0].published, jobs[0].start_period) == (
        "CACEIS", "Paris", "2026-10-23", "01/04/2027")
    assert jobs[0].url == offer


def test_public_career_page_without_offer_links_reports_connector_failure(monkeypatch):
    class Response:
        text = '<p>Les offres sont chargées uniquement par JavaScript</p>'
        def raise_for_status(self):
            pass
    monkeypatch.setattr("internships_project.internships.requests.get", lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match="aucun lien"):
        _career_page_jobs("Tikehau Capital", (
            "https://tikehau-capital-career.talentview.io/jobs",
            "tikehau-capital-career.talentview.io", "/jobs/"))


def test_caceis_vie_contract_is_read_from_official_detail(monkeypatch):
    class Response:
        text = ('<h1>Assistant Trader - Securities Finance H/F</h1>'
                '<p>Date de parution 23/10/2026 Type de contrat VIE '
                'Date prévue de prise de fonction 01/01/2027 '
                'Localisation du poste Zone géographique Europe, Luxembourg '
                'Ville Luxembourg Critères candidat Bac + 5</p>')
        def raise_for_status(self):
            pass
    monkeypatch.setattr("internships_project.internships.requests.get", lambda *args, **kwargs: Response())
    job = _career_detail("https://jobs.caceis.com/offre-de-emploi/emploi-assistant-trader_116800.aspx",
                         "CACEIS")
    assert job is not None
    assert job.kind == "VIE"
    assert job.location == "Luxembourg"
    assert job.start_period == "01/01/2027"


def test_palatine_offer_is_excluded_even_when_loaded_from_group_portal(monkeypatch):
    class Response:
        text = ('<h1>Stage - Assistant Sales FX</h1><p>Stage 123 Paris '
                'Banque Palatine fait partie du Groupe BPCE.</p>')
        def raise_for_status(self):
            pass
    monkeypatch.setattr("internships_project.internships.requests.get", lambda *args, **kwargs: Response())
    assert _career_detail("https://recrutement.bpce.fr/job/stage-assistant-sales-fx",
                          "BPCE / Natixis / BRED") is None


def test_cfm_official_internship_keeps_portfolio_analytics_offer(monkeypatch):
    class Response:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            pass
    offer = "https://jobs.cfm.com/job/Paris-Portfolio-Engineering-Internship-75/1372636755/"
    def fake_get(url, **kwargs):
        if url == offer:
            return Response('<h1>Portfolio Engineering - Internship</h1>'
                            '<p>Paris, 75, FR</p><h2>ABOUT CFM</h2>')
        return Response(f'<a href="{offer}">Portfolio Engineering - Internship</a>'
                        '<a href="https://example.com/job/other">Trading Intern</a>')
    monkeypatch.setattr("internships_project.internships.requests.get", fake_get)
    jobs = _career_page_jobs("CFM", ("https://jobs.cfm.com/go/Internship/9276655/",
                                    "jobs.cfm.com", "/job/"))
    assert len(jobs) == 1
    assert jobs[0].company == "CFM"
    assert jobs[0].location == "Paris, 75, FR"
    assert jobs[0].url == offer


def test_bpce_open_data_keeps_direct_official_market_offer(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return [
                {"title": "Stage - Assistant Sales Forex", "company": "Groupe BPCE",
                 "organization": "Natixis CIB", "city": "Paris", "jobtype": "Stage",
                 "date_de_publication": "2026-10-24", "description": "À partir de décembre 2026",
                 "url": "https://recrutement.bpce.fr/job/stage-assistant-sales-forex"},
                {"titre": "Stage Trading Assistant", "entreprise": "Banque Palatine",
                 "ville": "Paris", "type_de_contrat": "Stage",
                 "url_offre": "https://recrutement.bpce.fr/job/stage-trading"},
                {"titre": "Stage Trading Assistant", "entreprise": "BRED",
                 "ville": "Paris", "type_de_contrat": "Stage",
                 "url_offre": "https://example.com/job/fake"},
            ]
    monkeypatch.setattr("internships_project.internships.requests.get", lambda *args, **kwargs: Response())
    jobs = _bpce_open_data_jobs()
    assert len(jobs) == 1
    assert jobs[0].company == "Natixis CIB"
    assert jobs[0].start_period == "décembre 2026"
    assert jobs[0].published == "2026-10-24"
    assert jobs[0].source == "Site carrière · BPCE Open Data"


def test_career_page_reads_only_direct_matching_offers(monkeypatch):
    class Response:
        text = ('<a href="/emploi-carriere/offre-emploi/stage-trading">Stage Trading Paris</a>'
                '<a href="https://example.com/stage-trading">Stage Trading Paris</a>'
                '<a href="/emploi-carriere/offre-emploi/stage-marketing">Stage Marketing Paris</a>')
        def raise_for_status(self):
            pass
    monkeypatch.setattr("internships_project.internships.requests.get", lambda *args, **kwargs: Response())
    monkeypatch.setattr("internships_project.internships._career_detail",
                        lambda url, company, title: (url, company, title))
    jobs = _career_page_jobs("BNP Paribas", (
        "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/stage/france",
        "group.bnpparibas", "/emploi-carriere/offre-emploi/"))
    assert len(jobs) == 1
    assert jobs[0][0] == "https://group.bnpparibas/emploi-carriere/offre-emploi/stage-trading"


def test_bnp_reads_later_pages_and_vie_without_duplicate_jobs(monkeypatch):
    calls = []
    class Response:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            pass
    def fake_get(url, **kwargs):
        calls.append(url)
        if url.endswith("/stage/france"):
            return Response('<a href="?page=2">2</a>')
        if url.endswith("/stage/france?page=2"):
            return Response('<a href="/emploi-carriere/offre-emploi/stage-sales-trading">'
                            'Stage Sales Trading Paris</a>')
        if url.endswith("/vie"):
            return Response('<a href="/emploi-carriere/offre-emploi/vie-global-markets">'
                            'VIE Global Markets London</a>')
        return Response('')
    monkeypatch.setattr("internships_project.internships.requests.get", fake_get)
    monkeypatch.setattr("internships_project.internships._career_detail",
                        lambda url, company, title: (url, company, title))
    jobs = _career_page_jobs("BNP Paribas", (
        "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/stage/france",
        "group.bnpparibas", "/emploi-carriere/offre-emploi/"))
    assert len(jobs) == 2
    assert any(url.endswith("?page=2") for url in calls)
    assert any(url.endswith("/vie") for url in calls)


def test_bnp_cib_archive_parses_open_market_internship(monkeypatch):
    offer_url = "https://careers.cib.bnpparibas/jobs/structured-credit-trading-analyst-trainee/"
    class Response:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            pass
    def fake_get(url, **kwargs):
        if url == offer_url:
            return Response('<h1>Structured Credit Trading Analyst Trainee</h1>'
                            '<p>Apply for this job Employment contract: Internship '
                            'Location: Lisboa, Lisboa, Portugal Job/mission: Financial expertise '
                            'Reference: 123 About the job</p>')
        if url.endswith("/page/2/"):
            return Response('<a href="/jobs/structured-credit-trading-analyst-trainee/">'
                            'Structured Credit Trading Analyst Trainee</a>'
                            '<span>19 October 2026</span>')
        return Response('<a href="/jobs/stage-marketing/">Stage Marketing</a>')
    monkeypatch.setattr("internships_project.internships.requests.get", fake_get)
    jobs = _bnp_cib_jobs()
    assert len(jobs) == 1
    assert jobs[0].url == offer_url
    assert jobs[0].location == "Lisboa, Lisboa, Portugal"
    assert jobs[0].kind == "Stage"
    assert jobs[0].published == "2026-10-19"


def test_bnp_cib_uses_stage_archive_after_internship_timeout(monkeypatch):
    import requests
    offer_url = "https://careers.cib.bnpparibas/jobs/structured-credit-trading-analyst-trainee/"

    class Response:
        text = '<a href="/jobs/structured-credit-trading-analyst-trainee/">Structured Credit Trading Analyst Trainee</a>'

        def raise_for_status(self):
            pass

    def fake_get(url, **kwargs):
        if "/internship/" in url:
            raise requests.ReadTimeout("internship archive timed out")
        return Response()

    monkeypatch.setattr("internships_project.internships.requests.get", fake_get)
    monkeypatch.setattr("internships_project.internships._career_detail",
                        lambda url, company, title: _opportunity(title, company, "Lisboa, Portugal", "Stage", url, ""))
    jobs = _bnp_cib_jobs()
    assert len(jobs) == 1
    assert jobs[0].url == offer_url


def test_bnp_cib_discovers_market_role_from_official_global_markets_page(monkeypatch):
    from internships_project import internships

    offer_url = "https://careers.cib.bnpparibas/jobs/global-markets-trading-intern/"
    class Response:
        text = '<a href="/jobs/global-markets-trading-intern/">Global Markets Trading intern</a>'
        def raise_for_status(self):
            pass

    def fake_get(url, **kwargs):
        if url.endswith("/who-we-are/global-markets/"):
            return Response()
        raise internships.requests.ReadTimeout("archive unavailable")

    monkeypatch.setattr(internships.requests, "get", fake_get)
    monkeypatch.setattr(internships, "_career_detail",
                        lambda url, company, title: _opportunity(title, company, "London", "Internship", url, ""))
    jobs = _bnp_cib_jobs()
    assert [job.url for job in jobs] == [offer_url]


def test_bnp_diagnostics_are_not_shown_in_job_board():
    board = render_opportunities([], [
        "BNP Paribas: HTTP 403", "BNP Paribas Asset Management: HTTP 403",
        "BNP Paribas CIB: délai dépassé",
    ], datetime(2026, 10, 25, tzinfo=timezone.utc))
    assert "HTTP 403" not in board
    assert "délai dépassé" not in board
    assert "sources indisponibles" not in board
    assert "BNP Paribas : 0" not in board
    assert "Voir les stages BNP Paribas sur le site officiel" in board
    other_source = render_opportunities([], ["CACEIS: HTTP 503", "BNP Paribas: HTTP 403"],
                                        datetime(2026, 10, 25, tzinfo=timezone.utc))
    assert "1 sources indisponibles" in other_source
    assert "CACEIS: HTTP 503" in other_source
    assert "BNP Paribas: HTTP 403" not in other_source


def test_bnp_apac_board_verifies_generic_trainee_roles(monkeypatch):
    from internships_project import internships

    board = ('<a href="/vx/lang-en-GB/mobile-0/appcentre-1/brand-4/xf-session/'
             'candidate/so/pm/1/pl/3/opp/151-Trainee/en-GB">Trainee</a>'
             '<a href="/vx/lang-en-GB/mobile-0/appcentre-1/brand-4/xf-session/'
             'candidate/so/pm/1/pl/3/opp/152-Trainee/en-GB">Trainee</a>')
    market = ('<h1>Trainee</h1><p>Location Two IFC, Central, Hong Kong '
              'Job Category EQD Position Type Trainee Job Description '
              '6-month Internship within Global Markets -- the Options Market Making desk, '
              'supporting quant traders.</p>')
    unrelated = ('<h1>Trainee</h1><p>Location Two IFC, Central, Hong Kong '
                 'Position Type Trainee Job Description Internship in accounting.</p>')
    class Response:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            pass
    calls = []
    def fake_get(url, **kwargs):
        calls.append(url)
        return Response(board if "/jobboard/" in url else market if "/151-" in url else unrelated)
    monkeypatch.setattr(internships.requests, "get", fake_get)
    jobs = internships._bnp_tal_jobs()
    assert len(jobs) == 1
    assert jobs[0].company == "BNP Paribas"
    assert jobs[0].title == "6-month Internship within Global Markets -- the Options Market Making desk"
    assert jobs[0].location == "Two IFC, Central, Hong Kong"
    assert jobs[0].url.endswith("/opp/151-Trainee/en-GB")
    assert all("xf-session" not in url for url in calls[1:])


def test_cic_career_detail_keeps_start_and_direct_link(monkeypatch):
    class Response:
        text = ('<h1>Stagiaire école - Credit Desk Analyst</h1>'
                '<p>Type de contrat | Stage (6 mois) Métier | Marchés '
                'Localisation | PARIS (75) Niveau d études | Master '
                'Date de publication | 14/10/2026 Date de prise de poste | 16/11/2026</p>')
        def raise_for_status(self):
            pass
    monkeypatch.setattr("internships_project.internships.requests.get", lambda *args, **kwargs: Response())
    job = _career_detail("https://recrutement.creditmutuel.fr/fr/offre.html?annonce=116253",
                         "Crédit Mutuel / CIC")
    assert job is not None
    assert job.location == "PARIS (75)"
    assert job.published == "2026-10-14"
    assert job.start_period == "16/11/2026"
    assert job.url.endswith("annonce=116253")


def test_filled_bnp_offer_is_removed(monkeypatch):
    class Response:
        text = ('<h1>Stage - Sales Trading</h1><p>Cette offre est déjà pourvue. '
                'Localisation Paris, France</p>')
        def raise_for_status(self):
            pass
    monkeypatch.setattr("internships_project.internships.requests.get", lambda *args, **kwargs: Response())
    assert _career_detail("https://group.bnpparibas/emploi-carriere/offre-emploi/stage-sales-trading",
                          "BNP Paribas") is None


def test_marex_uses_job_heading_after_page_heading(monkeypatch):
    class Response:
        text = ('<h1>Career opportunities</h1><section><h1>Digital Assets Trading Intern</h1>'
                '<p>Singapore, Marex Solutions, Full-Time</p></section>')
        def raise_for_status(self):
            pass
    monkeypatch.setattr("internships_project.internships.requests.get", lambda *args, **kwargs: Response())
    job = _career_detail("https://www.marex.com/careers/career-opportunities/digital-assets-trading-intern",
                         "Marex")
    assert job is not None
    assert job.title == "Digital Assets Trading Intern"
    assert job.location == "Singapore"


def test_ca_cib_reads_official_stage_and_vie_rss(monkeypatch):
    class Response:
        content = (b'<rss><channel><item><title>Global Markets Stage</title>'
                   b'<link>https://jobs.ca-cib.com/offre-de-emploi/emploi-global-markets_123.aspx</link>'
                   b'</item><item><title>Marketing Stage</title>'
                   b'<link>https://jobs.ca-cib.com/offre-de-emploi/emploi-marketing_124.aspx</link>'
                   b'</item></channel></rss>')
        def raise_for_status(self):
            pass
    calls = []
    def fake_get(url, **kwargs):
        calls.append(kwargs["params"]["Rss_Contract"])
        return Response()
    monkeypatch.setattr("internships_project.internships.requests.get", fake_get)
    monkeypatch.setattr("internships_project.internships._career_detail",
                        lambda url, company, title: (url, company, title))
    jobs = _ca_cib_jobs()
    assert calls == [579, 1478]
    assert len(jobs) == 1
    assert jobs[0][2] == "Global Markets Stage"


def test_amundi_and_arkea_read_their_official_contract_feeds(monkeypatch):
    calls = []
    class Response:
        def __init__(self, host):
            self.content = (f'<rss><channel><item><title>Stage Capital Markets ETF</title>'
                            f'<link>https://{host}/offre-de-emploi/emploi-stage-markets_123.aspx</link>'
                            '</item><item><title>Stage Marketing</title>'
                            f'<link>https://{host}/offre-de-emploi/emploi-marketing_124.aspx</link>'
                            '</item></channel></rss>').encode()
        def raise_for_status(self):
            pass
    def fake_get(url, **kwargs):
        calls.append((url, kwargs["params"]["Rss_Contract"]))
        return Response(urlparse(url).hostname)
    from urllib.parse import urlparse
    monkeypatch.setattr("internships_project.internships.requests.get", fake_get)
    monkeypatch.setattr("internships_project.internships._career_detail",
                        lambda url, company, title: (url, company, title))
    assert len(_amundi_jobs()) == 1
    assert len(_arkea_jobs()) == 1
    assert calls == [
        ("https://jobs.amundi.com/handlers/offerRss.ashx", 579),
        ("https://jobs.amundi.com/handlers/offerRss.ashx", 1478),
        ("https://recrutement.arkea.com/handlers/offerRss.ashx", 1798),
    ]


def test_arkea_detail_ignores_filter_menu_for_employer_and_location(monkeypatch):
    class Response:
        text = ('<p>Entité Arkéa Asset Management Localisation du poste '
                'Veuillez sélectionner une ou des valeurs PARIS (9)</p>'
                '<h1>Stage Assistant Trader</h1>'
                '<p>Détail de l\'offre Informations générales Entité '
                'Arkéa Banque Entreprises et Institutionnels Description du poste '
                'Contrat Stage Localisation du poste Lieu Paris Critères candidat BAC+5</p>')
        def raise_for_status(self):
            pass
    monkeypatch.setattr("internships_project.internships.requests.get", lambda *args, **kwargs: Response())
    job = _career_detail("https://www.recrutement.arkea.com/Pages/Offre/detailoffre.aspx?idOffre=1",
                         "Crédit Mutuel Arkéa", "Stage Assistant Trader")
    assert job is not None
    assert job.company == "Arkéa Banque Entreprises et Institutionnels"
    assert job.location == "Paris"


def test_amundi_detail_extracts_paris_from_talentsoft_location(monkeypatch):
    class Response:
        text = ('<h1>Stage Capital Markets ETF H/F</h1>'
                '<p>Localisation du poste Zone géographique Europe, France, '
                'Ile-de-France, 75 - Paris Critères candidat '
                'Type de contrat Stage Date de publication 24/10/2026</p>')
        def raise_for_status(self):
            pass
    monkeypatch.setattr("internships_project.internships.requests.get", lambda *args, **kwargs: Response())
    job = _career_detail("https://jobs.amundi.com/offre-de-emploi/emploi-stage-markets_123.aspx",
                         "Amundi")
    assert job is not None
    assert "Paris" in job.location
    assert job.published == "2026-10-24"


def test_bpce_detail_returns_natixis_market_stage(monkeypatch):
    class Response:
        text = ('<h1>Stage - Assistant Sales Forex F/H</h1>'
                '<p>Stage 22385 Paris Natixis CIB fait partie du Groupe BPCE. '
                'À partir de décembre 2026.</p>')
        def raise_for_status(self):
            pass
    monkeypatch.setattr("internships_project.internships.requests.get", lambda *args, **kwargs: Response())
    job = _career_detail("https://recrutement.bpce.fr/job/stage-assistant-sales-forex-f-h",
                         "BPCE / Natixis / BRED")
    assert job is not None
    assert job.company == "Natixis CIB"
    assert job.location == "Paris"
    assert job.start_period == "décembre 2026"


def test_credit_mutuel_uses_stage_page_when_search_is_empty(monkeypatch):
    class Response:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            pass
    def fake_get(url, **kwargs):
        if "etudiants/stage.html" in url:
            return Response('<a href="/fr/offre.html?annonce=116253">Stagiaire Credit Desk Analyst</a>')
        return Response("<p>Aucune offre visible</p>")
    monkeypatch.setattr("internships_project.internships.requests.get", fake_get)
    monkeypatch.setattr("internships_project.internships._career_detail",
                        lambda url, company, title: (url, company, title))
    jobs = _career_page_jobs("Crédit Mutuel / CIC", (
        "https://recrutement.creditmutuel.fr/fr/nos_offres.html?offres=true&tc=3",
        "recrutement.creditmutuel.fr", "/fr/offre.html"))
    assert len(jobs) == 1
    assert jobs[0][0].endswith("annonce=116253")


def test_paris_market_internship_outscores_global_graduate():
    paris = _opportunity("Sales Trading Intern", "Bank", "Paris, France", "Intern",
                         "https://jobs.smartrecruiters.com/Bank/123", "2026-10-20")
    london = _opportunity("Markets Graduate", "Bank", "London, UK", "",
                          "https://job-boards.greenhouse.io/bank/jobs/123", "2026-10-21")
    assert paris is not None and london is not None
    assert paris.kind == "Stage" and paris.score > london.score
    assert london.kind == "Graduate"


def test_april_to_september_2027_starts_are_shown_first():
    older = _opportunity("Trading Intern", "Bank", "Paris", "",
                         "https://jobs.smartrecruiters.com/Bank/older", "2026-10-24", "mars 2027")
    april = _opportunity("Sales Trading Intern", "Bank", "Paris", "",
                         "https://jobs.smartrecruiters.com/Bank/april", "2026-10-20", "avril 2027")
    september = _opportunity("Markets Graduate", "Bank", "London", "",
                             "https://job-boards.greenhouse.io/bank/jobs/september", "2026-10-21", "September 2027")
    october = _opportunity("FX Trading Intern", "Bank", "Paris", "",
                           "https://jobs.smartrecruiters.com/Bank/october", "2026-10-24", "octobre 2027")
    assert all((older, april, september, october))
    view = render_opportunities([older, october, september, april], [],
                                datetime(2026, 10, 24, tzinfo=timezone.utc))
    assert view.index("/april") < view.index("/september")
    assert view.index("/september") < view.index("/older")
    assert view.index("/older") < view.index("/october")


def test_internships_reject_unrelated_or_unsafe_links():
    assert _opportunity("Marketing Intern", "Bank", "Paris", "",
                        "https://jobs.smartrecruiters.com/Bank/123", "") is None
    assert _opportunity("Trading Intern", "Bank", "Paris", "",
                        "https://example.com/jobs/123", "") is None


def test_private_equity_and_corporate_finance_are_not_market_roles():
    excluded = (
        "Private Equity Funds Analyst Stage",
        "Internship Private Equity, Club Deal Team",
        "Leveraged Finance & Telecom - Portfolio Management Stage",
        "Investment Banking Analyst - Leveraged Finance Intern",
        "Analyste Financement de Projet - Portefeuille Stage",
        "Stage Quantitatif Risque de crédit IRB Retail",
    )
    for title in excluded:
        assert _opportunity(title, "Bank", "Paris", "Stage",
                            "https://jobs.smartrecruiters.com/Bank/123", "") is None


def test_market_roles_remain_eligible_after_relevance_filter():
    included = (
        "Stage Equity Research - Paris",
        "Assistant Sales Trading Intern",
        "Market Risk Stage",
        "Stage Structuration Produits Dérivés",
        "Internship Asset Management Analyst",
    )
    for title in included:
        assert _opportunity(title, "Bank", "Paris", "",
                            "https://jobs.smartrecruiters.com/Bank/123", "") is not None


def test_existing_cache_drops_private_equity_offers(monkeypatch, tmp_path):
    market = _opportunity("Trading Intern", "Bank", "Paris", "",
                          "https://jobs.smartrecruiters.com/Bank/market", "2026-10-24")
    assert market is not None
    private_equity = asdict(market) | {"title": "Private Equity Funds Analyst Stage",
                                          "url": "https://jobs.smartrecruiters.com/Bank/private-equity"}
    cache = tmp_path / "internships_cache.json"
    cache.write_text(json.dumps({"version": 3, "updated": "2026-10-25T00:00:00+00:00",
                                 "jobs": [asdict(market), private_equity], "errors": []}), encoding="utf-8")
    monkeypatch.setattr("internships_project.internships.CACHE_PATH", cache)
    _, jobs, _ = _read_cache()
    assert [job.title for job in jobs] == ["Trading Intern"]


def test_existing_cache_drops_real_estate_and_malformed_location(monkeypatch, tmp_path):
    valid = _opportunity("Stage Assistant Sales FX", "Bank", "Paris", "Stage",
                         "https://jobs.smartrecruiters.com/Bank/valid", "")
    assert valid is not None
    property_job = asdict(valid) | {
        "title": "Stage - 6 mois - Analyste Marchés Immobiliers F/H", "company": "AEW",
        "url": "https://recrutement.bpce.fr/job/stage-analyste-marches-immobiliers",
    }
    broken_location = asdict(valid) | {
        "url": "https://www.recrutement.arkea.com/Pages/Offre/detailoffre.aspx?idOffre=8375",
        "location": "Veuillez sélectionner une ou des valeurs Tout déselectionner PARIS (9) Détail de l'offre",
    }
    cache = tmp_path / "internships_cache.json"
    cache.write_text(json.dumps({"version": 3, "updated": "2026-10-25T00:00:00+00:00",
                                 "jobs": [asdict(valid), property_job, broken_location], "errors": []}), encoding="utf-8")
    monkeypatch.setattr("internships_project.internships.CACHE_PATH", cache)
    _, jobs, _ = _read_cache()
    assert [job.url for job in jobs] == [valid.url]


def test_render_links_to_original_posting_and_filters():
    paris = _opportunity("FX Trading Stage", "Bank", "Paris", "",
                         "https://jobs.smartrecruiters.com/Bank/123", "2026-10-20")
    london = _opportunity("Markets Graduate", "Bank", "London", "",
                          "https://job-boards.greenhouse.io/bank/jobs/456", "2026-10-21")
    result = render_opportunities([paris, london], [], datetime.now(timezone.utc), "Stages Paris")
    assert 'href="https://jobs.smartrecruiters.com/Bank/123"' in result
    assert "Markets Graduate" not in result
    assert 'target="_blank"' in result
    vie_view = render_opportunities([], [], datetime.now(timezone.utc), "VIE")
    assert "mon-vie-via.businessfrance.fr/en/offres" in vie_view


def test_contract_filter_separates_paris_and_international_stages():
    stamp = datetime(2026, 10, 25, tzinfo=timezone.utc)
    jobs = [
        Opportunity("Sales Intern Paris", "Bank", "Paris", "Stage", "https://example.com/paris", "2026-10-24", 100),
        Opportunity("Sales Intern London", "Bank", "London", "Stage", "https://example.com/london", "2026-10-24", 80),
        Opportunity("Sales Intern Lyon", "Bank", "Lyon, France", "Stage", "https://example.com/lyon", "2026-10-24", 70),
        Opportunity("Markets VIE Paris", "Bank", "Paris", "VIE", "https://example.com/vie-paris", "2026-10-24", 60),
        Opportunity("Markets VIE London", "Bank", "London", "VIE", "https://example.com/vie-london", "2026-10-24", 60),
    ]
    paris = render_opportunities(jobs, [], stamp, category="Stages Paris")
    abroad = render_opportunities(jobs, [], stamp, category="Stages International")
    vie = render_opportunities(jobs, [], stamp, category="VIE")
    assert "Sales Intern Paris" in paris and "Sales Intern London" not in paris
    assert "Sales Intern London" in abroad
    assert "Sales Intern Lyon" not in abroad and "Markets VIE London" not in abroad
    assert "Markets VIE Paris" in vie and "Markets VIE London" in vie


def test_recent_sort_places_publication_before_priority_start():
    stamp = datetime(2026, 10, 25, tzinfo=timezone.utc)
    older = Opportunity("Older Sales Intern", "Bank", "Paris", "Stage", "https://example.com/older", "2026-10-20", 200, "avril 2027")
    newer = Opportunity("Newer Sales Intern", "Bank", "Paris", "Stage", "https://example.com/newer", "2026-10-25", 40, "octobre 2027")
    relevant = render_opportunities([newer, older], [], stamp)
    recent = render_opportunities([newer, older], [], stamp, sort_by="recent")
    assert relevant.index("Older Sales Intern") < relevant.index("Newer Sales Intern")
    assert recent.index("Newer Sales Intern") < recent.index("Older Sales Intern")


def test_opened_offer_can_be_confirmed_as_applied_without_losing_progress():
    offer = Opportunity("FX Sales Intern", "Bank", "Paris", "Stage",
                        "https://example.com/fx-sales", "2026-10-25", 100)
    pending = {offer.url: {"status": "À candidater", "note": "Contacter le desk",
                           "deadline": "2027-03-01", "follow_up": "2026-11-02"}}
    updated, changed = mark_opened_offer_applied(pending, [offer], offer.url)
    assert changed and updated[offer.url]["status"] == "Postulé"
    assert updated[offer.url]["note"] == "Contacter le desk"
    assert updated[offer.url]["deadline"] == "2027-03-01"
    assert updated[offer.url]["follow_up"] == "2026-11-02"
    assert updated[offer.url]["applied_at"]
    advanced = {offer.url: {**updated[offer.url], "status": "Interview"}}
    assert mark_opened_offer_applied(advanced, [offer], offer.url) == (advanced, False)
    assert mark_opened_offer_applied({}, [offer], "https://example.com/unknown") == ({}, False)


def test_offer_card_exposes_only_known_offer_for_return_reminder():
    offer = Opportunity("FX Sales Intern", "Bank", "Paris", "Stage",
                        "https://example.com/fx-sales", "2026-10-25", 100)
    card = render_opportunities([offer], [], datetime(2026, 10, 25, tzinfo=timezone.utc))
    assert 'data-offer-url="https://example.com/fx-sales"' in card
    assert 'data-offer-title="FX Sales Intern"' in card


def test_weekly_view_uses_publication_date_and_existing_filters():
    jobs = [
        _opportunity("Recent Trading Intern", "Bank", "Paris", "",
                     "https://jobs.smartrecruiters.com/Bank/recent", "2026-10-24"),
        _opportunity("Boundary Trading Intern", "Bank", "Paris", "",
                     "https://jobs.smartrecruiters.com/Bank/boundary", "2026-10-18"),
        _opportunity("Older Trading Intern", "Bank", "Paris", "",
                     "https://jobs.smartrecruiters.com/Bank/older", "2026-10-17"),
        _opportunity("Undated Trading Intern", "Bank", "Paris", "",
                     "https://jobs.smartrecruiters.com/Bank/undated", ""),
        _opportunity("Future Trading Intern", "Bank", "Paris", "",
                     "https://jobs.smartrecruiters.com/Bank/future", "2026-10-25"),
    ]
    assert all(jobs)
    stamp = datetime(2026, 10, 24, tzinfo=timezone.utc)
    all_view = render_opportunities(jobs, [], stamp, today=date(2026, 10, 24))
    weekly = render_opportunities(jobs, [], stamp, weekly=True, today=date(2026, 10, 24))
    assert "Older Trading Intern" in all_view
    assert "Undated Trading Intern" in all_view
    assert "Recent Trading Intern" in weekly
    assert "Boundary Trading Intern" in weekly
    assert "Older Trading Intern" not in weekly
    assert "Undated Trading Intern" not in weekly
    assert "Future Trading Intern" not in weekly
    filtered = render_opportunities(jobs, [], stamp, weekly=True, today=date(2026, 10, 24),
                                    query="Recent")
    assert "Recent Trading Intern" in filtered
    assert "Boundary Trading Intern" not in filtered


def test_daily_view_uses_only_todays_dated_offers():
    today = date(2026, 10, 24)
    jobs = [
        _opportunity("Today Trading Intern", "Bank", "Paris", "",
                     "https://jobs.smartrecruiters.com/Bank/today", "2026-10-24"),
        _opportunity("Yesterday Trading Intern", "Bank", "Paris", "",
                     "https://jobs.smartrecruiters.com/Bank/yesterday", "2026-10-23"),
        _opportunity("Undated Trading Intern", "Bank", "Paris", "",
                     "https://jobs.smartrecruiters.com/Bank/undated", ""),
    ]
    view = render_opportunities(jobs, [], datetime(2026, 10, 24, tzinfo=timezone.utc),
                                daily=True, today=today)
    assert "Today Trading Intern" in view
    assert "Yesterday Trading Intern" not in view
    assert "Undated Trading Intern" not in view


def test_start_period_requires_explicit_start_language():
    assert _start_period("Publié le 20 octobre 2026. À partir de janvier 2027.") == "janvier 2027"
    assert _start_period("The internship starts in January 2027.") == "January 2027"
    assert _start_period("Publié le 20 octobre 2026.") == ""
    assert _title_period("Assistant Sales - Stage - Janvier 2027") == "Janvier 2027"
    assert start_month("04/01/2027") == "2027-01"
    assert start_month("January 2027") == "2027-01"
    assert start_month("") == ""


def test_socgen_career_cards_include_start_date(monkeypatch):
    offer = "https://careers.societegenerale.com/en/job-offers/internship-market-risk-123-en"
    listing = f'<a href="{offer}">Internship Market Risk</a>'

    class Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    def get(url, **kwargs):
        if url.endswith("all-job-offers"):
            return Response(listing)
        return Response("<h1>Internship Market Risk</h1><p>Paris, France Salary from $ 100,000</p>"
                        "<p>Start date 2027/01/04 Publication date 2026/10/23</p>"
                        "<p>Market Risk Global Markets internship.</p>")

    monkeypatch.setattr("internships_project.internships.requests.get", get)
    jobs = _socgen_jobs()
    assert len(jobs) == 1
    assert jobs[0].start_period == "January 2027"
    assert jobs[0].published == "2026-10-23"
    assert jobs[0].score >= 100


def test_smartrecruiters_reads_second_page(monkeypatch):
    seen_offsets = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def get(url, params=None, **kwargs):
        if params is None:
            return Response({"jobAd": {"sections": {}}})
        seen_offsets.append(params["offset"])
        count = 100 if params["offset"] == 0 else 1
        return Response({"totalFound": 101, "content": [
            {"id": str(params["offset"] + index), "name": "Trading Intern",
             "location": {"city": "Paris"}, "typeOfEmployment": {"label": "Intern"}}
            for index in range(count)
        ]})

    monkeypatch.setattr("internships_project.internships.requests.get", get)
    assert len(_smart_jobs("Bank", "Bank")) == 101
    assert seen_offsets == [0, 100]


def test_workday_offer_and_explicit_start(monkeypatch):
    published = (datetime.now(timezone.utc).date() - timedelta(days=5)).isoformat()
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def post(url, json=None, **kwargs):
        if json["searchText"] != "Paris":
            return Response({"total": 0, "jobPostings": []})
        return Response({"total": 1, "jobPostings": [
            {"title": "Rates Sales Intern", "locationsText": "Paris",
             "externalPath": "/job/Paris/Rates-Sales-Intern_R123", "postedOn": "Posted 5 Days Ago"}
        ]})

    monkeypatch.setattr("internships_project.internships.requests.post", post)
    monkeypatch.setattr("internships_project.internships.requests.get", lambda *args, **kwargs: Response({
        "jobPostingInfo": {"location": "Paris", "jobDescription": "Starting in January 2027.",
                           "postedOn": "Posted 5 Days Ago", "startDate": published}
    }))
    jobs = _workday_jobs("Deutsche Bank", ("db.wd3.myworkdayjobs.com", "db", "DBWebsite"))
    assert len(jobs) == 1
    assert jobs[0].start_period == "January 2027"
    assert jobs[0].published == published
    assert not jobs[0].published_inferred
    assert jobs[0].url.endswith("/job/Paris/Rates-Sales-Intern_R123")


def test_workday_preserves_relevant_offers_beyond_detail_enrichment_limit(monkeypatch):
    class Response:
        def __init__(self, payload):
            self.payload = payload
        def raise_for_status(self):
            pass
        def json(self):
            return self.payload

    def post(url, json=None, **kwargs):
        if json["searchText"] != "Paris":
            return Response({"total": 0, "jobPostings": []})
        offset = json["offset"]
        rows = [{"title": f"Rates Sales Intern {index}", "locationsText": "Paris",
                 "externalPath": f"/job/Paris/Rates-Sales-Intern-{index}_R{index}",
                 "postedOn": "Posted 2 Days Ago"}
                for index in range(offset, min(offset + 20, 55))]
        return Response({"total": 55, "jobPostings": rows})

    monkeypatch.setattr("internships_project.internships.requests.post", post)
    monkeypatch.setattr("internships_project.internships.requests.get", lambda *args, **kwargs: Response({
        "jobPostingInfo": {"location": "Paris", "jobDescription": "Rates sales internship"}
    }))
    jobs = _workday_jobs("Deutsche Bank", ("db.wd3.myworkdayjobs.com", "db", "DBWebsite"))
    assert len(jobs) == 55


def test_socgen_global_connector_finds_international_quant_pricing_internship(monkeypatch):
    from internships_project import internships

    url = ("https://careers.societegenerale.com/en/job-offers/"
           "internship-equity-derivatives-quantitative-pricing-26000MO2-en")
    listing_html = f'<a href="{url}">Internship - Equity Derivatives Quantitative Pricing</a>'
    detail_html = """<html><h1>Internship - Equity Derivatives Quantitative Pricing</h1>
      <p>Internship SG Americas Securities</p>
      <p>New York, New York, United States Salary from $ 100,000</p>
      <p>Reference 26000MO2 Start date 2026/12/07 Publication date 2026/10/26</p>
      <p>Global Markets Division. Equity derivatives pricing, structuring and trading.</p></html>"""

    class Response:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            pass

    def fake_get(request_url, **kwargs):
        return Response(listing_html if request_url.endswith("all-job-offers") else detail_html)

    monkeypatch.setattr(internships.requests, "get", fake_get)
    jobs = internships._socgen_jobs()
    assert len(jobs) == 1
    assert jobs[0].title == "Internship - Equity Derivatives Quantitative Pricing"
    assert jobs[0].company == "Société Générale"
    assert jobs[0].location == "New York, New York, United States"
    assert jobs[0].published == "2026-10-26"
    assert jobs[0].start_period == "December 2026"


def test_socgen_keeps_market_offers_outside_curated_financial_hubs(monkeypatch):
    from internships_project import internships

    url = ("https://careers.societegenerale.com/en/job-offers/"
           "graduate-trainee-global-markets-sales-26000MH3-en")
    listing_html = f'<a href="{url}">Graduate Trainee - Global Markets Sales</a>'
    detail_html = """<html><h1>Graduate Trainee - Global Markets Sales</h1>
      <p>Sydney, Australia Salary from to</p>
      <p>Reference 26000MH3 Start date 2026/11/23 Publication date 2026/10/25</p>
      <p>Graduate Trainee role in Global Markets (Equity & Derivatives), supporting sales.</p></html>"""

    class Response:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            pass

    monkeypatch.setattr(internships.requests, "get", lambda request_url, **kwargs: Response(
        listing_html if request_url.endswith("all-job-offers") else detail_html))
    jobs = internships._socgen_jobs()
    assert len(jobs) == 1
    assert jobs[0].location == "Sydney, Australia"
    assert jobs[0].kind == "Graduate"
    assert internships._is_international_location(jobs[0].location)
    assert not internships._is_international_location("Lyon, Auvergne-Rhône-Alpes, France")
    assert jobs[0].published == "2026-10-25"
    assert jobs[0].start_period == "November 2026"


def test_workday_posted_on_fallback_uses_only_exact_day_labels():
    today = date(2026, 10, 25)
    assert _workday_publication_date("2026-10-20", "Posted 5 Days Ago", today=today) == "2026-10-20"
    assert _workday_publication_date(posted_on="Posted 5 Days Ago", today=today) == "2026-10-20"
    assert _workday_publication_date(posted_on="Posted Yesterday", today=today) == "2026-10-24"
    assert _workday_publication_date(posted_on="Posted Today", today=today) == "2026-10-25"
    assert _workday_publication_date(posted_on="Posted 2 Weeks Ago", today=today) == ""
    assert _workday_publication_date("2027-01-01", "", today=today) == ""


def test_official_jobposting_jsonld_uses_posted_date_only():
    payload = json.dumps({"@graph": [
        {"@type": "Organization", "datePosted": "2026-10-25"},
        {"@type": "JobPosting", "datePosted": "2020-10-19T16:34:01+02:00",
         "dateModified": "2026-10-25"},
    ]})
    assert _jsonld_job_posted(f'<script type="application/ld+json">{payload}</script>') == "2020-10-19"
    assert _jsonld_job_posted('<script type="application/ld+json">{"@type":"Organization","datePosted":"2020-10-19"}</script>') == ""


def test_vie_seed_expires_and_tracking_is_private_state(monkeypatch):
    monkeypatch.delenv("VIE_API_KEY", raising=False)
    monkeypatch.setattr("internships_project.internships.VIE_SEEDS", (
        (1, "Trading Analyst", "Bank", "London", "2999-12-31", "janvier 2027"),
        (2, "Market Analyst", "Bank", "Milan", "2000-01-01", "mars 2027"),
    ))
    jobs = _vie_jobs()
    assert len(jobs) == 1 and jobs[0].kind == "VIE"
    assert jobs[0].deadline == "2999-12-31"
    state = save_tracking({}, jobs[0], "À candidater", "Relancer mardi", "2027-01-02")
    assert "Relancer mardi" in render_tracking(state, jobs)
    assert "2027-01-02" in render_tracking(state, jobs)
    assert "Dans les flux actuels" in render_tracking(state, jobs)
    assert "Absente des flux" in render_tracking(state, [])


def test_vie_api_maps_only_vie_missions(monkeypatch):
    monkeypatch.setenv("VIE_API_KEY", "test-key")
    monkeypatch.setattr("internships_project.internships.VIE_SEEDS", ())

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"result": [
                {"id": 99, "missionType": "VIE", "missionTitle": "Trading Analyst",
                 "organizationName": "Bank", "cityName": "London", "countryName": "United Kingdom",
                 "missionStartDate": "2027-01-01"},
                {"id": 100, "missionType": "VIA", "missionTitle": "Market Analyst",
                 "organizationName": "Embassy", "cityName": "London"},
            ]}

    monkeypatch.setattr("internships_project.internships.requests.post", lambda *args, **kwargs: Response())
    jobs = _vie_jobs()
    assert len(jobs) == 1
    assert jobs[0].url.endswith("/offres/99")
    assert jobs[0].start_period == "2027-01-01"


def test_filters_by_family_and_start_month():
    job = _opportunity("FX Trading Stage", "Bank", "Paris", "",
                       "https://jobs.smartrecruiters.com/Bank/123", "2026-10-20", "janvier 2027")
    now = datetime.now(timezone.utc)
    assert "FX Trading Stage" in render_opportunities([job], [], now, family="Sales / Trading / Structuring", earliest="2027-01")
    assert "FX Trading Stage" not in render_opportunities([job], [], now, earliest="2027-02")


def test_new_and_dismissed_filters():
    job = _opportunity("Trading Intern", "Bank", "Paris", "",
                       "https://jobs.smartrecruiters.com/Bank/123", "2026-10-20")
    now = datetime.now(timezone.utc)
    assert "Trading Intern" not in render_opportunities([job], [], now, seen_urls=[job.url], only_new=True)
    tracked = save_tracking({}, job, "Écartée", "Pas adapté")
    assert "Trading Intern" not in render_opportunities([job], [], now, tracking=tracked, hide_dismissed=True)
    assert "Trading Intern" in render_opportunities([job], [], now, tracking=tracked, hide_dismissed=False)


def test_offer_feedback_hides_and_restores_cards():
    job = _opportunity("Trading Intern", "Bank", "Paris", "",
                       "https://jobs.smartrecruiters.com/Bank/feedback", "2026-10-24")
    assert job is not None
    now = datetime.now(timezone.utc)
    feedback = save_offer_feedback({}, job, "hors_cible")
    assert "Trading Intern" in render_opportunities([job], [], now, feedback=feedback)
    visible = render_opportunities([job], [], now, feedback=feedback, show_hors_cible=True)
    assert "Trading Intern" in visible
    assert 'data-feedback-verdict=' not in visible
    assert save_offer_feedback(feedback, job, "hors_cible") == {}
    relevant = save_offer_feedback({}, job, "pertinent")
    assert "Trading Intern" in render_opportunities([job], [], now, feedback=relevant)


def test_relevant_feedback_promotes_offer_within_start_priority():
    recent = _opportunity("Recent Trading Intern", "Bank", "Paris", "",
                          "https://jobs.smartrecruiters.com/Bank/recent", "2026-10-24")
    preferred = _opportunity("Preferred Trading Intern", "Bank", "Paris", "",
                             "https://jobs.smartrecruiters.com/Bank/preferred", "2026-10-20")
    feedback = save_offer_feedback({}, preferred, "pertinent")
    page = render_opportunities([recent, preferred], [], datetime.now(timezone.utc), feedback=feedback)
    assert page.index("Recent Trading Intern") < page.index("Preferred Trading Intern")


def test_local_state_migrates_browser_tracking_and_survives_new_browser(tmp_path, monkeypatch):
    monkeypatch.delenv("INTERNSHIPS_USERS_JSON", raising=False)
    path = tmp_path / "user_state.json"
    monkeypatch.setattr(state_store, "STATE_PATH", path)
    monkeypatch.setattr(state_store, "BACKUP_PATH", tmp_path / "user_state.backup.json")
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("RAILWAY_PROJECT_ID", raising=False)
    monkeypatch.delenv("SPACE_ID", raising=False)
    job = _opportunity("Trading Intern", "Bank", "Paris", "",
                       "https://jobs.smartrecruiters.com/Bank/persist", "2026-10-24")
    tracking = save_tracking({}, job, "Postulé", "Relancer lundi", follow_up="2026-10-28")
    migrated, _ = state_store.hydrate_local_state(tracking, {})
    assert migrated[job.url]["note"] == "Relancer lundi"
    reopened, _ = state_store.hydrate_local_state({}, {})
    assert reopened[job.url]["status"] == "Postulé"
    feedback = save_offer_feedback({}, job, "pertinent")
    assert state_store.persist_feedback(feedback)
    _, reopened_feedback = state_store.hydrate_local_state({}, {})
    assert reopened_feedback[job.url]["verdict"] == "pertinent"
    path.write_text("{invalid", encoding="utf-8")
    recovered_tracking, _ = state_store.hydrate_local_state({}, {})
    assert recovered_tracking[job.url]["note"] == "Relancer lundi"
    assert state_store.persist_feedback(feedback)
    stale_browser = save_tracking({}, job, "À examiner", "Ancienne version")
    disk_wins, _ = state_store.hydrate_local_state(stale_browser, {})
    assert disk_wins[job.url]["note"] == "Relancer lundi"
    assert state_store.persist_tracking({})
    deleted_stays_deleted, _ = state_store.hydrate_local_state(stale_browser, {})
    assert deleted_stays_deleted == {}


def test_cloud_mode_keeps_personal_state_out_of_shared_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, "STATE_PATH", tmp_path / "user_state.json")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    tracking, feedback = state_store.hydrate_local_state({}, {})
    assert tracking == {} and feedback == {}
    assert not state_store.persist_tracking({})
    assert not (tmp_path / "user_state.json").exists()


def test_follow_up_reminders_and_offer_badges():
    job = _opportunity("Trading Intern", "Bank", "Paris", "",
                       "https://jobs.smartrecruiters.com/Bank/123", "2026-10-24", "avril 2027")
    tracked = save_tracking({}, job, "Candidature envoyée", "Contacter le recruteur",
                            "2026-11-01", "2026-10-26", "2026-10-24")
    pipeline = render_tracking(tracked, [job], today=date(2026, 10, 24))
    assert "2026-10-26" in pipeline
    assert "2026-10-24" in pipeline
    assert "Prochaine action : 2026-10-26" in pipeline
    board = render_opportunities([job], [], datetime.now(timezone.utc), tracking=tracked)
    assert "Nouveau" not in board
    assert "Début ciblé" not in board
    assert "Postulé" in board


def test_offer_card_keeps_tracking_status_with_contract_details():
    job = _opportunity("Stage Assistant Sales", "Bank", "Paris", "",
                       "https://jobs.smartrecruiters.com/Bank/sales", "2026-10-24", "avril 2027")
    tracked = save_tracking({}, job, "OA", "")
    board = render_opportunities([job], [], datetime.now(timezone.utc), tracking=tracked)
    tags = board.split('<span class="job-card-tags">', 1)[1].split('</span></a>', 1)[0]
    assert 'class="job-fact kind"' in tags
    assert 'class="job-badge tracked">OA</span>' in tags
    assert 'class="job-badges"' not in board


def test_application_pipeline_groups_stages_and_due_actions():
    applied = _opportunity("Trading Intern", "Bank", "Paris", "",
                           "https://jobs.smartrecruiters.com/Bank/applied", "2026-10-24")
    interview = _opportunity("Markets Graduate", "Bank", "London", "",
                             "https://job-boards.greenhouse.io/bank/jobs/interview", "2026-10-24")
    state = save_tracking({}, applied, "OA", "Réviser les tests", follow_up="2026-10-26")
    state = save_tracking(state, interview, "Interview", "Préparer les questions")
    board = render_tracking(state, [applied, interview], today=date(2026, 10, 24))
    assert "En cours" in board and "Entretiens" in board
    assert "Actions sous 7 jours" in board
    assert "2026-10-26" in board
    assert "Sans prochaine action" in board
    assert 'href="https://jobs.smartrecruiters.com/Bank/applied"' in board


def test_tracking_backup_restores_notes_and_rejects_unsafe_links():
    job = _opportunity("Trading Intern", "Bank", "Paris", "",
                       "https://jobs.smartrecruiters.com/Bank/123", "2026-10-24")
    state = save_tracking({}, job, "À candidater", "Préparer CV", "2026-11-01", "2026-10-27")
    restored, message = import_tracking(export_tracking(state), {})
    assert restored[job.url]["note"] == "Préparer CV"
    assert restored[job.url]["follow_up"] == "2026-10-27"
    assert "1 offre" in message
    rejected, _ = import_tracking('{"javascript:alert(1)":{"title":"X"}}', {})
    assert rejected == {}


def test_application_stages_and_legacy_statuses():
    job = _opportunity("Trading Intern", "Bank", "Paris", "",
                       "https://jobs.smartrecruiters.com/Bank/123", "2026-10-24")
    assert normalize_status("Candidature envoyée") == "Postulé"
    assert normalize_status("Entretien") == "Interview"
    assert normalize_status("Offre reçue") == "Offer"
    assert normalize_status("Refus") == "Rejected"
    for stage in ("Postulé", "OA", "HV", "Interview", "Offer", "Rejected"):
        state = save_tracking({}, job, stage, "")
        assert state[job.url]["status"] == stage
        assert stage in render_tracking(state, [job])
    imported, _ = import_tracking(
        '{"https://jobs.smartrecruiters.com/Bank/123": {"title": "Trading Intern", "status": "Refus"}}',
        {},
    )
    assert imported[job.url]["status"] == "Rejected"
    assert "Rejected" in render_tracking(imported, [job])


def test_repeated_stage_prefix_is_deduplicated():
    assert _canonical_title("Stage - Assistant Trader Salle des marchs F/H") == _canonical_title(
        "Stage : Stage - Assistant Trader Salle des marchés F/H"
    )


def test_adzuna_is_removed_from_existing_cache_and_jobteaser_link_is_available(tmp_path, monkeypatch):
    from internships_project import internships

    direct = _opportunity("Trading Intern", "Bank", "Paris", "Stage",
                          "https://jobs.smartrecruiters.com/Bank/123", "2026-10-24")
    assert direct is not None
    legacy_adzuna = asdict(direct) | {
        "url": "https://www.adzuna.fr/details/123", "source": "Adzuna",
    }
    cache = tmp_path / "internships_cache.json"
    cache.write_text(json.dumps({"version": 3, "updated": "2026-10-25T00:00:00+00:00",
                                 "jobs": [asdict(direct), legacy_adzuna], "errors": []}), encoding="utf-8")
    monkeypatch.setattr(internships, "CACHE_PATH", cache)
    _, jobs, _ = _read_cache()
    assert [job.url for job in jobs] == [direct.url]
    page = render_opportunities(jobs, [], datetime.now(timezone.utc))
    assert "jobteaser.com/fr/job-offers" in page
    assert "Adzuna" not in page


def test_undated_offer_gets_first_detection_date_and_keeps_it(tmp_path, monkeypatch):
    from internships_project import internships

    undated = _opportunity("Trading Intern", "Bank", "Paris", "Stage",
                           "https://jobs.smartrecruiters.com/Bank/undated", "")
    assert undated is not None
    old_snapshot = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    cache = tmp_path / "internships_cache.json"
    cache.write_text(json.dumps({"version": 3, "updated": old_snapshot.isoformat(),
                                 "jobs": [asdict(undated)], "errors": []}), encoding="utf-8")
    monkeypatch.setattr(internships, "CACHE_PATH", cache)
    monkeypatch.setattr(internships, "_cache", None)
    _, migrated, _ = internships._read_cache()
    assert migrated[0].published == "2026-10-20"
    assert migrated[0].published_inferred
    monkeypatch.setattr(internships, "_fetch_opportunities", lambda: ([undated], []))
    jobs, _, _ = internships.refresh_opportunities()
    assert jobs[0].published == "2026-10-20"
    assert jobs[0].published_inferred
    assert "Détectée 2026-10-20" in render_opportunities(jobs, [], old_snapshot)
    _, reloaded, _ = internships._read_cache()
    assert reloaded[0].published == "2026-10-20"


def test_new_undated_offer_uses_current_detection_date(tmp_path, monkeypatch):
    from internships_project import internships

    undated = _opportunity("Sales Intern", "Bank", "Paris", "Stage",
                           "https://jobs.smartrecruiters.com/Bank/new", "")
    assert undated is not None
    monkeypatch.setattr(internships, "CACHE_PATH", tmp_path / "internships_cache.json")
    monkeypatch.setattr(internships, "_cache", None)
    monkeypatch.setattr(internships, "_fetch_opportunities", lambda: ([undated], []))
    jobs, _, _ = internships.refresh_opportunities()
    assert jobs[0].published == datetime.now(timezone.utc).date().isoformat()
    assert jobs[0].published_inferred


def test_official_publication_date_replaces_inferred_detection_date(tmp_path, monkeypatch):
    from internships_project import internships

    undated = _opportunity("Sales Intern", "Bank", "Paris", "Stage",
                           "https://jobs.smartrecruiters.com/Bank/dated-later", "")
    assert undated is not None
    monkeypatch.setattr(internships, "CACHE_PATH", tmp_path / "internships_cache.json")
    monkeypatch.setattr(internships, "_cache", (
        datetime(2026, 10, 20, tzinfo=timezone.utc),
        [internships.replace(undated, published="2026-10-20", published_inferred=True)], [],
    ))
    official = internships.replace(undated, published="2026-10-18")
    monkeypatch.setattr(internships, "_fetch_opportunities", lambda: ([official], []))
    jobs, _, _ = internships.refresh_opportunities()
    assert jobs[0].published == "2026-10-18"
    assert not jobs[0].published_inferred


def test_disk_snapshot_is_returned_before_refresh(tmp_path, monkeypatch):
    from internships_project import internships

    job = _opportunity("Trading Intern", "Bank", "Paris", "",
                       "https://jobs.smartrecruiters.com/Bank/123", "2026-10-20")
    monkeypatch.setattr(internships, "CACHE_PATH", tmp_path / "internships_cache.json")
    monkeypatch.setattr(internships, "_cache", None)
    monkeypatch.setattr(internships, "_last_attempt", None)
    monkeypatch.setattr(internships, "_refresh_worker", None)
    internships._write_cache(datetime(2026, 1, 1, tzinfo=timezone.utc), [job], [])
    started = []

    class FakeThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            started.append(True)

        def is_alive(self):
            return True

    monkeypatch.setattr(internships.threading, "Thread", FakeThread)
    jobs, _, _ = internships.load_opportunities()
    assert jobs == [job]
    assert started == [True]


def test_hourly_scheduler_starts_once(monkeypatch):
    from internships_project import internships
    started = []

    class FakeThread:
        def __init__(self, *args, **kwargs):
            pass
        def start(self):
            started.append(True)
        def is_alive(self):
            return True

    monkeypatch.setattr(internships, "_hourly_worker", None)
    monkeypatch.setattr(internships.threading, "Thread", FakeThread)
    internships.start_hourly_refresh()
    internships.start_hourly_refresh()
    assert started == [True]


def test_lbp_listing_associates_details_link_with_offer_heading(monkeypatch):
    from internships_project import internships

    listing = ('<h3>Stage Trading Assistant</h3>'
               '<a href="/candidats/offres-d-emploi/nos-offres-d-emploi.job-500.html/stage-trading.html">'
               "Détails de l'offre</a>")
    detail = ("<h1>Stage Trading Assistant</h1><p>Type de contrat : Stage</p>"
              "<p>Il y a 2 jours</p><p>Ville Paris</p><a>Je postule</a>"
              "<main>Support the FX trading desk and its market activity.</main>")

    class Response:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            pass

    def fake_get(url, **kwargs):
        return Response(listing if url.endswith("nos-offres-d-emploi.html") else detail)

    monkeypatch.setattr(internships.requests, "get", fake_get)
    jobs = internships._career_page_jobs("La Banque Postale", internships.CAREER_LISTINGS["La Banque Postale"])
    assert len(jobs) == 1
    assert jobs[0].company == "La Banque Postale"
    assert jobs[0].location == "Paris"
    assert jobs[0].published == (datetime.now(timezone.utc).date() - timedelta(days=2)).isoformat()
    assert "FX trading desk" in jobs[0].description


def test_lazard_oracle_connector_paginates_and_retains_full_detail(monkeypatch):
    from internships_project import internships

    calls = []
    class Response:
        def __init__(self, payload=None, text=""):
            self.payload, self.text = payload, text
        def raise_for_status(self):
            pass
        def json(self):
            return self.payload

    class FakeSession:
        def __init__(self):
            self.headers = {}
        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            if "/hcmUI/" in url:
                return Response(text='{"siteNumber":"CX_42"}')
            if "recruitingCEJobRequisitionDetails/" in url:
                return Response({"ExternalDescription": "The role supports the fixed income trading desk and rates products."})
            if kwargs.get("params", {}).get("finder", "").endswith("offset=0"):
                return Response({"items": [{"TotalJobsCount": 1, "requisitionList": [{
                    "Id": "123", "Title": "Fixed Income Trading Intern", "PrimaryLocation": "Paris, France",
                    "WorkerType": "Internship", "PostedDate": "2026-10-20",
                }]}]})
            return Response({"items": [{"TotalJobsCount": 1, "requisitionList": []}]})

    monkeypatch.setattr(internships.requests, "Session", FakeSession)
    jobs = internships._oracle_jobs("Lazard Student Careers", internships.ORACLE_CAREER_BOARDS["Lazard Student Careers"])
    assert len(jobs) == 1
    assert jobs[0].url.endswith("/job/123/")
    assert jobs[0].published == "2026-10-20"
    assert jobs[0].description.startswith("The role supports")
    assert any("siteNumber=CX_42" in str(call[1].get("params")) for call in calls)


def test_offer_pagination_covers_all_filtered_offers_without_overlap():
    from datetime import datetime, timezone

    jobs = [
        Opportunity(f"Sales Trading Intern {number:03d}", "Bank", "Paris", "Stage",
                    f"https://example.com/jobs/{number:03d}", "2026-10-25", 100)
        for number in range(263)
    ]
    updated = datetime(2026, 10, 28, tzinfo=timezone.utc)
    pages = [render_opportunities(jobs, [], updated, page=page) for page in range(1, 7)]

    assert "Offres 1–50 sur 263" in pages[0]
    assert pages[0].count('<article class="internship-card-container internship-card"') == 50
    assert "Sales Trading Intern 000" in pages[0]
    assert "Sales Trading Intern 050" not in pages[0]
    assert "Offres 51–100 sur 263" in pages[1]
    assert "Sales Trading Intern 050" in pages[1]
    assert "Sales Trading Intern 000" not in pages[1]
    assert "Offres 251–263 sur 263" in pages[5]
    assert pages[5].count('<article class="internship-card-container internship-card"') == 13
    assert "Sales Trading Intern 262" in pages[5]


def test_offer_pagination_filters_before_count_and_page_slice():
    from datetime import datetime, timezone

    jobs = [
        Opportunity(f"Sales Intern {number:03d}", "Target Bank" if number < 63 else "Other Bank",
                    "Paris", "Stage", f"https://example.com/filter/{number:03d}",
                    "2026-10-25", 100)
        for number in range(263)
    ]
    page = render_opportunities(jobs, [], datetime(2026, 10, 28, tzinfo=timezone.utc),
                                query="Target Bank", page=2)
    assert "Offres 51–63 sur 63" in page
    assert "Sales Intern 050" in page
    assert "Sales Intern 000" not in page

