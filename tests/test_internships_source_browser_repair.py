"""Public-source repairs: ordinary virtual browser and Altays pagination."""
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock

import pytest

from internships_project import internships as jobs


def test_bnp_catalogue_is_not_truncated_at_40_pages(monkeypatch):
    from playwright import sync_api
    root='https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/cdd'
    offer='https://group.bnpparibas/emploi-carriere/offre-emploi/junior-sales'
    provider=MagicMock()
    page=provider.__enter__.return_value.chromium.launch.return_value.new_page.return_value
    current=[1]
    def navigate(url,**kwargs):
        if '?page=' in url:current[0]=int(url.rsplit('=',1)[1])
        return SimpleNamespace(status=200)
    page.goto.side_effect=navigate
    page.content.side_effect=lambda: f'<a href="{offer}">Graduate Global Markets Sales</a>' if current[0]==43 else '<a href="/emploi-carriere/offre-emploi/stage-rh">Stage RH</a>'
    page.locator.return_value.evaluate_all.side_effect=lambda script: [{'href':root+f'?page={current[0]+1}','label':'Suivant'}] if current[0]<43 else []
    monkeypatch.setattr(sync_api,'sync_playwright',lambda:provider)
    monkeypatch.setattr(jobs,'_career_detail',lambda *a,**k:jobs.Opportunity('Graduate Global Markets Sales','BNP Paribas','Paris','Graduate',offer,'',90))
    assert len(jobs._bnp_group_jobs_browser('BNP Paribas',root))==1
    assert current[0]==43


def test_bnp_disabled_next_link_is_not_a_pagination_failure(monkeypatch):
    from playwright import sync_api
    root='https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/stage'
    provider=MagicMock()
    page=provider.__enter__.return_value.chromium.launch.return_value.new_page.return_value
    page.goto.return_value.status=200
    page.content.return_value='<a href="/emploi-carriere/offre-emploi/stage-rh">Stage RH</a>'
    page.locator.return_value.evaluate_all.return_value=[{'href':root,'label':'Suivant','disabled':True}]
    monkeypatch.setattr(sync_api,'sync_playwright',lambda:provider)
    assert jobs._bnp_group_jobs_browser('BNP Paribas',root)==[]
    assert page.goto.call_count==1


@pytest.mark.parametrize('status',[404,410,403])
def test_bnp_expired_details_are_removed_but_access_failures_remain_partial(monkeypatch,status):
    from playwright import sync_api
    root='https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/stage'
    offer='https://group.bnpparibas/emploi-carriere/offre-emploi/stage-sales'
    provider=MagicMock()
    page=provider.__enter__.return_value.chromium.launch.return_value.new_page.return_value
    page.goto.side_effect=[SimpleNamespace(status=200),SimpleNamespace(status=status)]
    page.content.return_value=f'<a href="{offer}">Stage Sales</a>'
    page.locator.return_value.evaluate_all.return_value=[]
    monkeypatch.setattr(sync_api,'sync_playwright',lambda:provider)
    if status==403:
        with pytest.raises(jobs._PartialSourceError) as failure:jobs._bnp_group_jobs_browser('BNP Paribas',root)
        assert failure.value.failed_urls=={offer}
    else:assert jobs._bnp_group_jobs_browser('BNP Paribas',root)==[]


@pytest.mark.parametrize("environment,headless", [
    ({}, True), ({"DISPLAY": ":99"}, True),
    ({"GITHUB_ACTIONS": "true", "DISPLAY": ":99"}, False),
])
def test_bnp_uses_virtual_display_only_on_github(monkeypatch, environment, headless):
    monkeypatch.setattr(jobs, "os", SimpleNamespace(name="posix", getenv=environment.get))
    browser = Mock(return_value=[])
    monkeypatch.setattr(jobs, "_bnp_group_jobs_browser", browser)
    assert jobs._bnp_group_jobs("BNP Paribas", "https://group.bnpparibas/listing") == []
    browser.assert_called_once_with("BNP Paribas", "https://group.bnpparibas/listing", headless=headless)


@pytest.mark.parametrize("shell_unavailable", [False, True])
def test_oddo_reads_ajax_pages_and_official_pdfs(monkeypatch, shell_unavailable):
    import pypdf
    description = "Localisation : Paris Type de contrat : Stage Date de publication : 10/11/2026"
    monkeypatch.setattr(pypdf, "PdfReader", lambda stream: SimpleNamespace(
        pages=[SimpleNamespace(extract_text=lambda: description)]))
    detail = "https://recrutement.altays-progiciels.com/oddo/fr/offres/stage-sales-123.pdf"
    seen_pages = []

    def get(url, **kwargs):
        if url == jobs.ODDO_ALTAYS_LISTING:
            if shell_unavailable:
                raise jobs.requests.ConnectTimeout("legacy search unavailable")
            text = '<div style="display:none">An error has occurred</div>'
        elif url == detail:
            return SimpleNamespace(content=b"synthetic PDF", raise_for_status=lambda: None)
        else:
            assert url == "https://recrutement.altays-progiciels.com/oddo/fr/offres.html"
            number = kwargs["params"]["page"]
            seen_pages.append(number)
            text = {1: '<a href="/oddo/fr/offres/stage-sales-123.html?page=1">Stage Sales</a>'
                       '<a href="https://evil.invalid/oddo/fr/offres/stage-sales-456.html">Stage Sales</a>',
                    2: '<a href="/oddo/fr/offres/comptable-222.html">Comptable CDI</a>',
                    3: ''}[number]
        return SimpleNamespace(text=text, raise_for_status=lambda: None)

    monkeypatch.setattr(jobs.requests, "get", get)
    found = jobs._oddo_jobs()
    assert seen_pages == [1, 2, 3]
    assert len(found) == 1
    assert (found[0].url, found[0].location, found[0].published) == (detail, "Paris", "2026-11-10")


def test_oddo_does_not_accept_repeating_or_broken_listing(monkeypatch):
    monkeypatch.setattr(jobs.requests, "get", lambda *a, **kw: SimpleNamespace(
        text='<a href="/oddo/fr/offres/stage-sales-123.html">Stage Sales</a>',
        raise_for_status=lambda: None))
    with pytest.raises(ValueError, match="pagination Altays répétée"):
        jobs._oddo_jobs()


def test_cib_retries_unreachable_archives_in_virtual_browser(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("DISPLAY", ":99")
    monkeypatch.setattr(jobs.requests, "get", Mock(side_effect=jobs.requests.ReadTimeout()))
    render = Mock(return_value='<a href="/jobs/trading-intern/">Trading intern</a>')
    monkeypatch.setattr(jobs, "_render_public_career_page", render)
    monkeypatch.setattr(jobs, "_career_detail", lambda url, company, title: jobs._opportunity(
        title, company, "Paris", "Stage", url, ""))
    found = jobs._bnp_cib_jobs()
    assert len(found) == 1
    assert render.call_count == 10


def test_cib_failed_details_are_not_reported_as_empty_success(monkeypatch):
    monkeypatch.setattr(jobs.requests, "get", lambda *a, **kw: SimpleNamespace(
        text='<a href="/jobs/trading-intern/">Trading intern</a>', raise_for_status=lambda: None))
    monkeypatch.setattr(jobs, "_career_detail", Mock(side_effect=jobs.requests.ReadTimeout()))
    monkeypatch.delenv("DISPLAY", raising=False)
    with pytest.raises(jobs._PartialSourceError) as error:
        jobs._bnp_cib_jobs()
    assert error.value.failed_urls == {'https://careers.cib.bnpparibas/jobs/trading-intern/'}


@pytest.mark.parametrize("prefix", ["/emploi-carriere/offre-emploi/", "/en/careers/job-offer/"])
def test_bnp_readable_non_market_jobs_are_empty_success(monkeypatch, prefix):
    from playwright import sync_api
    provider = MagicMock()
    browser = provider.__enter__.return_value.chromium.launch.return_value
    page = browser.new_page.return_value
    page.goto.return_value.status = 200
    page.get_by_text.return_value.last.is_visible.return_value = False
    page.content.return_value = f'<a href="{prefix}stage-rh">Stage Ressources humaines</a>'
    monkeypatch.setattr(sync_api, "sync_playwright", lambda: provider)
    assert jobs._bnp_group_jobs_browser("BNP Paribas", "https://group.bnpparibas/listing") == []
    browser.close.assert_called_once()


@pytest.mark.parametrize("pagination_fails", [False, True])
def test_bnp_recovers_market_jobs_after_first_page(monkeypatch, pagination_fails):
    from playwright import sync_api
    root = "https://group.bnpparibas/emploi-carriere/toutes-offres-emploi/stage"
    offer = "https://group.bnpparibas/emploi-carriere/offre-emploi/stage-sales"
    provider = MagicMock()
    page = provider.__enter__.return_value.chromium.launch.return_value.new_page.return_value
    current = [root]
    def navigate(url, **kwargs):
        if pagination_fails and url == root + '?page=2':
            raise sync_api.TimeoutError("pagination unavailable")
        current[0] = url
        return SimpleNamespace(status=200)
    page.goto.side_effect = navigate
    page.content.side_effect = lambda: (
        '<a href="/emploi-carriere/offre-emploi/stage-rh">Stage RH</a>' if current[0] == root
        else '<a href="' + offer + '">Stage Sales</a>')
    page.locator.return_value.evaluate_all.side_effect = lambda script: (
        [{"href": root+'?page=2', "label":"Suivant"}] if current[0] == root else
        [{"href": "https://evil.invalid/next", "label":"Suivant"}])
    monkeypatch.setattr(sync_api, "sync_playwright", lambda: provider)
    monkeypatch.setattr(jobs, "_career_detail", lambda url, company, title, **kw: jobs._opportunity(
        title, company, "Paris", "Stage", url, ""))
    if pagination_fails:
        with pytest.raises(jobs._PartialSourceError) as failure:
            jobs._bnp_group_jobs_browser("BNP Paribas", root)
        assert failure.value.preserve_cached
    else:
        assert [j.url for j in jobs._bnp_group_jobs_browser("BNP Paribas", root)] == [offer]
        assert [call.args[0] for call in page.goto.call_args_list] == [root,root+'?page=2',offer]
