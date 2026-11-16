from types import SimpleNamespace

import pytest

from internships_project import internships as m


def teaser(slug):
    return m._jobteaser_from_sitemap_url(
        'https://www.jobteaser.com/fr/job-offers/11111111-2222-3333-4444-555555555555-' + slug)


def test_lazard_employer_suffix_and_gender_order_match_official_metadata():
    job = teaser('lazard-freres-gestion-stage-analyste-produits-structures-et-alternatifs-h-f-mars-2027')
    assert job.company == 'Lazard Frères Gestion'
    assert not job.title.startswith('Freres Gestion')
    direct = m.Opportunity('Stage H/F - Analyste Produits Structurés et Alternatifs – Mars 2027',
                           'Lazard', 'Paris, France', 'Stage',
                           'https://icbpjb.fa.ocs.oraclecloud.com/job/6341/', '2026-06-30', 100,
                           start_period='mars 2027')
    legacy = m.replace(job, company='Lazard', title='Freres Gestion ' + job.title)
    assert m._without_jobteaser_duplicates([legacy, direct]) == [direct]
    assert m._without_jobteaser_duplicates([m.replace(legacy, start_period='avril 2027'), direct]) == [m.replace(legacy, start_period='avril 2027'), direct]
    different_role = m.replace(direct, title='Stage H/F - Analyste Actions – Mars 2027')
    assert m._without_jobteaser_duplicates([legacy, different_role]) == [legacy, different_role]


def test_hsbc_public_career_pages_recover_place_start_and_second_page(monkeypatch):
    name = 'HSBC Continental Europe'
    listing, host, _ = m.CAREER_LISTINGS[name]
    offer = f'https://{host}/job/cash/1373837357/'
    other = f'https://{host}/job/sales/1375122457/'
    counters = '<script>jobRecordsFound:parseInt("2"),jobRecordsPerPage:parseInt("1")</script>'
    pages = {
        listing: counters + f'<a href="{offer}">Stage Assistant Trader Cash</a>',
        listing + '&startrow=1': counters + f'<a href="{other}">Stage Sales Trading</a>',
        offer: '<h1>Stage - Assistant Trader desk Cash &amp; Liquidité et Portefeuille (f/m/d)</h1>'
               '<span>Lieu:</span><p>PARIS, 75, FR, 75116</p><span>Date: 31 octobre 2026</span>'
               '<p>Le stage est à pourvoir pour janvier 2027.</p>',
        other: '<h1>Stage Sales Trading (f/m/d)</h1><span>Lieu:</span><p>Paris</p>'
               '<p>Date de début : février 2027</p>',
    }
    calls = []
    def get(url, **kw):
        calls.append(url)
        return SimpleNamespace(text=pages[url], raise_for_status=lambda: None)
    monkeypatch.setattr(m.requests, 'get', get)
    jobs = m._career_page_jobs(name, m.CAREER_LISTINGS[name])
    cash = next(job for job in jobs if job.url == offer)
    assert cash.start_period == 'janvier 2027'
    assert cash.location == 'PARIS, 75, FR, 75116'
    assert len(jobs) == 2 and calls.count(listing + '&startrow=1') == 1
    fallback = teaser('hsbc-continental-europe-stage-assistant-trader-desk-cash-liquidite-et-portefeuille-f-m-d')
    assert m._without_jobteaser_duplicates([fallback, cash]) == [cash]
    assert not m.is_trusted_offer_url(f'https://{host}.evil.invalid/job/1')


@pytest.mark.parametrize('text,expected', [
    ('Le stage est à pourvoir pour janvier 2027.', 'janvier 2027'),
    ('Publié le 31 octobre 2026. Candidatures pour janvier 2027.', ''),
])
def test_start_is_not_the_publication_or_application_date(text, expected):
    assert m._start_period(text) == expected


def test_lisbon_explicit_in_jobteaser_title_is_a_location():
    job = teaser('bnp-paribas-france-v-i-e-capital-market-p-l-specialist-lisbonne-h-f')
    assert job.location == 'Lisbonne'


@pytest.mark.parametrize('displayed,expected', [
    ('21 oct. 2026', '2026-10-21'),
    ('31 Oct 2026', '2026-10-31'),
    ('5 nov. 2026', '2026-11-05'),
    ('29 févr. 2024', '2024-02-29'),
    ('31 févr. 2026', ''),
    ('21 inconnu 2026', ''),
    ('21 jui 2026', ''),
    ('21 oct. 9999', ''),
])
def test_hsbc_visible_publication_is_distinct_from_start_and_deadline(displayed, expected, monkeypatch):
    monkeypatch.setattr(m, '_refresh_first_seen', {})
    page = ('<h1>Stage Assistant Trader Cash (f/m/d)</h1>'
            '<span>Lieu:</span><span>PARIS, 75, FR, 75116</span>'
            '<span>Closing Date:</span><span>30 nov. 2026</span>'
            f'<span class="joblayouttoken-label">Date:&nbsp;</span><span>{displayed}</span>'
            '<p>Le stage est à pourvoir pour janvier 2027.</p>')
    job = m._career_detail('https://apply.careers.hsbc.com/job/cash/1/',
                           'HSBC Continental Europe', html_override=page)
    assert job.published == expected
    assert not job.published_inferred
    assert job.start_period == 'janvier 2027'
    if expected:
        previous = m.replace(job, published='2026-11-14', published_inferred=True)
        dated = m._date_detected_offer(job, previous, m.date(2026, 11, 14))
        assert dated.published == expected and not dated.published_inferred


def test_hsbc_without_publication_does_not_use_start_or_closing_date():
    job = m._career_detail('https://apply.careers.hsbc.com/job/cash/1/',
                           'HSBC Continental Europe', html_override=(
        '<h1>Stage Assistant Trader Cash</h1><span>Lieu:</span><span>Paris</span>'
        '<span>Closing Date:</span><span>21 oct. 2026</span>'
        '<span>Date de début:</span><span>janvier 2027</span>'))
    assert job.published == ''
