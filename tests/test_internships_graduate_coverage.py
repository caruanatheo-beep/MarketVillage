"""Graduate audit regressions, using public-shaped synthetic catalogues."""
import json
from types import SimpleNamespace

import pytest

from internships_project import internships as jobs


@pytest.mark.parametrize("title,contract,expected", [
    ("Junior Quantitative Analyst", "CDI", "Graduate"),
    ("Analyste junior - gestion actions", "Permanent", "Graduate"),
    ("Jr. Equity Research Analyst", "Full time", "Graduate"),
    ("Junior Trading Analyst Internship", "", "Stage"),
    ("Stage Analyste Junior Trading", "", "Stage"),
    ("Junior Trading Analyst VIE", "", "VIE"),
    ("Senior / Junior Trading Analyst", "CDI", None),
])
def test_junior_classification_preserves_internships(title, contract, expected):
    assert jobs._kind(title, contract) == expected


def junior_offer(title="Junior Analyst", context=""):
    return jobs._opportunity(title, "Bank", "Paris", "CDI",
        "https://group.bnpparibas/emploi-carriere/offre-emploi/junior-analyst", "",
        role_context=context)


@pytest.mark.parametrize("context,expected", [
    ("", False),
    ("Financial analysis of companies", False),
    ("You will join our trading desk. No experience required.", True),
    ("Work with equity investment teams and portfolio managers.", True),
    ("You will join our middle office. Collaborate with the trading desk.", False),
    ("Join the trading desk. At least 3 years of experience required.", False),
    ("Join the trading desk. Minimum of three years of experience.", False),
    ("Trading desk. Au moins 3 ans d'expérience.", False),
    ("Trading desk. Expérience de 3 ans minimum.", False),
    ("Trading desk. 0-2 years of experience required.", True),
    ("Trading desk. Three years of experience preferred.", True),
    ("Trading desk. 12 month contract. No experience required.", True),
])
def test_generic_junior_requires_verified_desk_and_entry_level(context, expected):
    assert bool(junior_offer(context=context)) is expected


@pytest.mark.parametrize("title", ["Junior KYC Analyst", "Junior Middle Office Analyst",
    "Junior Corporate Finance Analyst", "Junior M&A Analyst", "Junior Fund Accounting Analyst"])
def test_junior_non_market_roles_are_excluded(title):
    assert not junior_offer(title, "You will collaborate with our trading desk.")


def test_greenhouse_generic_junior_uses_description(monkeypatch):
    monkeypatch.setattr(jobs.requests, "get", lambda *a, **kw: SimpleNamespace(
        json=lambda: {"jobs": [{"title": "Junior Analyst", "location": {"name": "Amsterdam"},
            "absolute_url": "https://job-boards.eu.greenhouse.io/imc/jobs/123",
            "content": "<p>You will join our trading desk. No experience required.</p>"}]},
        raise_for_status=lambda: None))
    found = jobs._greenhouse_jobs("imc", "IMC Trading")
    assert len(found) == 1 and found[0].kind == "Graduate"
    assert jobs._eligible_offer(found[0])


@pytest.mark.parametrize("detail", ["entry", "experienced", "unavailable", "non_market"])
def test_workday_junior_search_verifies_detail(monkeypatch, detail):
    terms = []
    def post(url, **kwargs):
        term = kwargs['json']['searchText']; terms.append(term)
        rows = [{"title": "Junior Analyst", "locationsText": "London", "externalPath": "/job/London/Junior-Analyst_123"}] if term == "" else []
        return SimpleNamespace(json=lambda: {"jobPostings": rows, "total": len(rows)}, raise_for_status=lambda: None)
    def get(url, **kwargs):
        if detail == "unavailable":
            raise jobs.requests.ReadTimeout()
        description = {"entry": "Join our trading desk. 0-2 years of experience required.",
            "experienced": "Join our trading desk. At least 3 years of experience required.",
            "non_market": "You will join our middle office. Collaborate with the trading desk."}[detail]
        return SimpleNamespace(json=lambda: {"jobPostingInfo": {"location": "London", "jobDescription": description}}, raise_for_status=lambda: None)
    monkeypatch.setattr(jobs.requests, "post", post)
    monkeypatch.setattr(jobs.requests, "get", get)
    monkeypatch.setattr(jobs, "_cached_detail", lambda job: None)
    board = ("db.wd3.myworkdayjobs.com", "db", "DBWebsite")
    if detail == "unavailable":
        with pytest.raises(jobs._PartialSourceError) as failure:
            jobs._workday_jobs("Deutsche Bank", board)
        assert not failure.value.jobs
        assert any('/Junior-Analyst_123' in url for url in failure.value.failed_urls)
    else:
        found = jobs._workday_jobs("Deutsche Bank", board)
        assert len(found) == (1 if detail == "entry" else 0)
        if found:
            assert found[0].kind == "Graduate" and jobs._eligible_offer(found[0])
    assert terms == [""]


@pytest.mark.parametrize("title,employment,expected", [
    ("2027 MUFG UK Summer Analyst Programme: Global Client Sales", "", "Stage"),
    ("Global Markets Summer Associate Programme 2027", "Full time", "Stage"),
    ("2027 MUFG UK Analyst Programme: Global Markets", "", "Graduate"),
    ("Global Markets Graduate Programme", "Permanent contract", "Graduate"),
    ("Graduate Quantitative Researcher", "CDI", "Graduate"),
    ("Global Markets Graduates Programme", "CDD", "Graduate"),
    ("Markets - Sales and Trading, Full Time Analyst, London, 2027", "Permanent", "Graduate"),
    ("Markets, Quantitative Analysis, Full-Time Associate, London, 2027", "", "Graduate"),
    ("International Talent Programme - Financial Markets", "", "Graduate"),
    ("Traineeprogramm Capital Markets", "", "Graduate"),
    ("New Analyst - Equities", "Permanent", "Graduate"),
    ("Senior Sales", "Permanent contract", None),
    ("Full Time Analyst - Global Markets", "", None),
    ("Sales Intern", "Permanent contract", None),
    ("Graduate Programme Markets", "Apprenticeship", None),
    ("Stage Sales", "Alternance", None),
])
def test_programme_contracts(title, employment, expected):
    assert jobs._kind(title, employment) == expected


@pytest.mark.parametrize("labels", [
    "Job type Fixed Term Contract Location Milan, Lombardy, Italy Reference BNPSA_272026 Last update 09.11.2026",
    "Type de contrat CDD Localisation Milan, Lombardie, Italie Référence BNPSA_272026 Mise à jour 09.11.2026",
])
def test_bnp_milan_sales_graduate_detail(labels):
    title = 'JUNIOR SALES (Graduate Program, Global Markets)'
    url = 'https://group.bnpparibas/en/careers/job-offer/junior-sales-graduate-program-global-markets-1'
    detail = f'<h1>{title}</h1><p>{labels}</p><p>Global Markets Graduate Program is a 12-month program. '
    detail += 'You will be supporting the activity of our Global Markets Front Office team, '
    detail += 'with interactions with middle office and back office.</p>'
    job = jobs._career_detail(url, 'BNP Paribas', title, html_override=detail)
    assert job and job.kind == 'Graduate' and job.location.startswith('Milan')
    assert jobs.matching_opportunities([job], category='Graduate', query='Milan') == [job]


@pytest.mark.parametrize("first_fails", [False, True])
def test_bnp_searches_graduate_and_fixed_term_catalogues(monkeypatch, first_fails):
    job = jobs._opportunity('JUNIOR SALES (Graduate Program, Global Markets)', 'BNP Paribas', 'Milan', 'CDD',
                           'https://group.bnpparibas/en/careers/job-offer/junior-sales-graduate-program-global-markets-1', '')
    calls = []
    def collect(company, listing):
        assert company == 'BNP Paribas'
        calls.append(listing)
        if listing.endswith('/graduate-programme-cdi'):
            if first_fails:
                raise jobs.requests.ReadTimeout()
            return []
        if listing.endswith('/je-recherche-mon-premier-emploi'):
            return []
        assert listing.endswith('/cdd')
        return [job,job]
    monkeypatch.setattr(jobs, '_bnp_group_jobs', collect)
    if first_fails:
        with pytest.raises(jobs._PartialSourceError) as error:
            jobs._bnp_graduate_jobs()
        found = error.value.jobs
        assert error.value.preserve_cached
    else:
        found = jobs._bnp_graduate_jobs()
    assert found == [job]
    assert len(calls) == 3


def test_bnp_both_graduate_catalogues_failing_is_not_empty_success(monkeypatch):
    def fail(*args):
        raise jobs.requests.ReadTimeout()
    monkeypatch.setattr(jobs, '_bnp_group_jobs', fail)
    with pytest.raises(ValueError, match='indisponibles'):
        jobs._bnp_graduate_jobs()


@pytest.mark.parametrize("city", ["Paris", "London", "Frankfurt", "Amsterdam", "Zurich",
                                   "Geneva", "Luxembourg", "Madrid", "Milan", "Dublin",
                                   "Stockholm", "Copenhagen"])
def test_european_cities_do_not_exclude_graduates(city):
    job = jobs._opportunity("Global Markets Graduate Programme", "Bank", city, "CDI",
                            "https://jobs.smartrecruiters.com/bank/123", "")
    assert job and job.kind == "Graduate"
    assert jobs.matching_opportunities([job], category="Graduate") == [job]


@pytest.mark.parametrize("title", [
    "Graduate Middle Office - Global Markets", "Graduate Corporate Finance",
    "Asset Management, Controls Governance & Testing | New Analyst",
    "Graduate Quantitative Researcher - Expression of Interest",
    "Graduate Trading Talent Pool", "Graduate Real Estate Fund Management",
])
def test_non_desk_and_interest_only_roles_stay_excluded(title):
    assert not jobs._opportunity(title, "Bank", "London", "",
                                 "https://jobs.smartrecruiters.com/bank/123", "")


def test_greenhouse_eu_is_trusted_but_not_a_lookalike(monkeypatch):
    url = "https://job-boards.eu.greenhouse.io/imc/jobs/123"
    monkeypatch.setattr(jobs.requests, "get", lambda *a, **kw: SimpleNamespace(
        json=lambda: {"jobs": [{"title": "Graduate Quantitative Researcher",
            "location": {"name": "Amsterdam"}, "absolute_url": url, "content": "Quantitative research"}]},
        raise_for_status=lambda: None))
    assert [j.url for j in jobs._greenhouse_jobs("imc", "IMC Trading")] == [url]
    assert not jobs.is_trusted_offer_url(url.replace("greenhouse.io", "greenhouse.io.evil.invalid"))


@pytest.mark.parametrize("second_page_fails", [False, True])
def test_optiver_new_catalogue_pagination(monkeypatch, second_page_fails):
    rows = [{"title": "Senior Trader", "location": "Amsterdam", "experience": "Experienced",
             "href": f"/join-us/jobs/trading/amsterdam/senior-{i}/"} for i in range(16)]
    graduate = {"title": "Graduate Quantitative Researcher (2027 Start)", "location": "Amsterdam",
                "experience": "Graduate", "href": "/join-us/jobs/quant/amsterdam/graduate/"}
    if second_page_fails:
        rows[0] = graduate
    offsets = []
    def get(url, **kwargs):
        if url.endswith('/en/api/v1/jobs'):
            offset = kwargs['params']['from']; offsets.append(offset)
            if offset and second_page_fails:
                raise jobs.requests.ReadTimeout()
            payload = {'items': rows if offset == 0 else [graduate], 'totalCount': 17}
            return SimpleNamespace(json=lambda: payload, raise_for_status=lambda: None)
        assert url == 'https://www.optiver.com' + graduate['href']
        detail = {'@type':'JobPosting','datePosted':'2026-11-10',
                  'description':'Quantitative research on our trading floor. Start date: September 2027.'}
        return SimpleNamespace(text='<script type="application/ld+json">'+json.dumps(detail)+'</script>',
                               raise_for_status=lambda: None)
    monkeypatch.setattr(jobs.requests, 'get', get)
    monkeypatch.setattr(jobs, '_cached_detail', lambda job: None)
    if second_page_fails:
        with pytest.raises(jobs._PartialSourceError) as failure:
            jobs._optiver_jobs()
        found = failure.value.jobs
        assert failure.value.preserve_cached
    else:
        found = jobs._optiver_jobs()
    assert offsets == ([0,16,16] if second_page_fails else [0,16])
    assert len(found) == 1 and found[0].kind == 'Graduate' and found[0].location == 'Amsterdam'
