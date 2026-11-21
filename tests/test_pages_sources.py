"""Anonymous source suggestions: browser checks with a simulated storage receiver."""
import pytest
from playwright.sync_api import expect
from tests.test_pages_filters import browser, ROOT, BASE

ENDPOINT = 'https://marketdesk-source-suggestions.source-suggestions.workers.dev/suggestions'


@pytest.fixture
def sources_screen(browser):
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    calls, errors = [], []
    state = {'enabled': True, 'success': True, 'proposals': []}
    page.on('pageerror', lambda error: errors.append(str(error)))
    def route(request):
        if request.request.url == ENDPOINT:
            if request.request.method=='GET':
                request.fulfill(json={'suggestions':state['proposals']})
                return
            calls.append(request.request.post_data_json)
            if state['success']:
                state['proposals'].append(calls[-1])
            request.fulfill(json={'success': state['success']})
            return
        name = request.request.url.removeprefix(BASE).split('?')[0] or 'index.html'
        if name == 'sources.json':
            request.fulfill(json={'request_endpoint': ENDPOINT if state['enabled'] else '', 'sources': [
                dict(name='BNP Paribas', category='Banques & services titres', url='https://example.com/bnp', logo='',
                     added_on=state.get('bnp_added', ''),
                     feeds=[dict(name='BNP France', url='https://example.com/fr'), dict(name='BNP Monde', url='https://example.com/global')]),
                dict(name='Candriam', category='Gestion d’actifs', url='https://example.com/candriam', logo='',
                     added_on=state.get('candriam_added', ''),
                     feeds=[dict(name='Candriam', url='https://example.com/candriam')])]})
        elif name == 'offers.json':
            request.fulfill(json={'offers': [], 'sources': {}, 'updated': ''})
        elif name in {'index.html', 'site.css', 'app.js', 'sources.js', 'marketdesk-icon.svg'}:
            body = (ROOT / name).read_text(encoding='utf-8')
            if name == 'index.html':
                body = body.replace("connect-src 'self';", "connect-src 'self' https://marketdesk-source-suggestions.source-suggestions.workers.dev;")
            mime = {'html': 'text/html', 'css': 'text/css', 'js': 'application/javascript', 'svg': 'image/svg+xml'}
            request.fulfill(body=body, content_type=mime[name.rsplit('.', 1)[1]])
        else:
            request.abort()
    page.route('**/*', route)
    page.goto(BASE + '#sources', wait_until='networkidle')
    page.locator('.source-card').first.wait_for()
    yield page, calls, state
    assert not errors, errors
    page.close()


def fill_suggestion(page):
    page.locator('#source-name').fill('Nouvelle banque')
    page.locator('#source-url').fill('https://careers.example.com/jobs')
    page.locator('#source-reason').fill('Des stages Sales à Paris')


def test_catalog_navigation_search_and_mobile(sources_screen):
    page, calls, _ = sources_screen
    assert page.locator('.source-card').count() == 2
    page.locator('.source-card details').first.locator('summary').click()
    assert page.locator('.source-card details a:visible').count() == 2
    page.locator('[data-category="Banques & services titres"]').click()
    assert page.locator('.source-card h3').inner_text() == 'BNP Paribas'
    page.locator('[data-category=""]').click()
    page.locator('#source-search').fill('candriam')
    assert page.locator('.source-card').count() == 1
    page.locator('#nav-offers').click()
    expect(page.locator('#offers-view')).to_be_visible()
    page.locator('#nav-sources').click()
    expect(page.locator('#sources-view')).to_be_visible()
    assert page.locator('#source-search').input_value() == 'candriam'
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not calls


def test_anonymous_submission_success(sources_screen):
    page, calls, _ = sources_screen
    fill_suggestion(page)
    page.locator('#source-submit').click()
    page.get_by_text('Ta suggestion a été enregistrée. Merci !', exact=True).wait_for()
    assert len(calls) == 1
    assert calls[0]['company'] == 'Nouvelle banque'
    assert calls[0]['url'] == 'https://careers.example.com/jobs'
    assert not any(key in calls[0] for key in ['email', 'password', 'token'])
    assert page.locator('#source-name').input_value() == ''
    expect(page.locator('#proposed-list h3')).to_have_text('Nouvelle banque')


def test_compact_cards_link_directly_and_portals_do_not_move_grid(sources_screen):
    page, calls, _ = sources_screen
    card = page.locator('#source-list .source-card').first
    link = card.locator('.source-link')
    expect(link).to_have_attribute('href', 'https://example.com/bnp')
    expect(link).to_have_attribute('target', '_blank')
    assert 'example.com' not in card.inner_text()
    before = card.bounding_box()
    assert before['height'] <= 100
    assert link.bounding_box()['width'] >= before['width'] - 2
    summary = card.locator('summary')
    summary.click()
    expect(card.locator('details a').first).to_be_visible()
    assert card.bounding_box() == before
    expect(card.locator('details a').last).to_have_attribute('href', 'https://example.com/global')
    page.keyboard.press('Escape')
    expect(card.locator('details a').first).not_to_be_visible()
    expect(summary).to_be_focused()
    summary.click()
    page.locator('#source-search').click()
    expect(card.locator('details a').first).not_to_be_visible()
    assert not calls


def test_failed_submission_preserves_fields_and_can_retry(sources_screen):
    page, calls, state = sources_screen
    state['success'] = False
    fill_suggestion(page)
    page.locator('#source-submit').click()
    page.locator('#source-request-status.is-error').wait_for()
    assert page.locator('#source-name').input_value() == 'Nouvelle banque'
    assert page.locator('#source-submit').is_enabled()
    state['success'] = True
    page.locator('#source-submit').click()
    page.get_by_text('Ta suggestion a été enregistrée. Merci !', exact=True).wait_for()
    assert len(calls) == 2


def test_unconfigured_receiver_disables_submission(sources_screen):
    page, calls, state = sources_screen
    state['enabled'] = False
    page.reload(wait_until='networkidle')
    assert page.locator('#source-name').is_disabled()
    assert page.locator('#source-submit').is_disabled()
    assert not calls


def test_sources_badge_disappears_after_visit_and_persists(sources_screen):
    page, calls, _ = sources_screen
    expect(page.locator('#sources-badge')).to_be_hidden()
    page.evaluate('localStorage.clear()')
    page.goto(BASE, wait_until='networkidle')
    expect(page.locator('#sources-badge')).to_be_visible()
    page.locator('#nav-sources').click()
    expect(page.locator('#sources-view')).to_be_visible()
    expect(page.locator('#sources-badge')).to_be_hidden()
    page.locator('#nav-offers').click()
    page.reload(wait_until='networkidle')
    expect(page.locator('#sources-badge')).to_be_hidden()
    assert not calls


def test_badge_works_without_browser_storage_and_mobile_suggestion_button(sources_screen):
    page, calls, _ = sources_screen
    page.add_init_script("Object.defineProperty(window, 'localStorage', {get(){throw new Error('blocked')}})")
    page.set_viewport_size({'width':390,'height':844})
    page.goto(BASE, wait_until='networkidle')
    expect(page.locator('#sources-badge')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#nav-sources').click()
    expect(page.locator('#sources-badge')).to_be_hidden()
    button = page.locator('#suggest-source')
    assert button.evaluate('el => getComputedStyle(el).position') == 'fixed'
    # With two sources the form is already on screen, so the floating shortcut steps aside.
    expect(page.locator('#source-request-title')).to_be_in_viewport()
    expect(button).to_have_class('secondary-action is-form-visible')
    page.locator('#nav-offers').scroll_into_view_if_needed()
    page.evaluate("document.querySelector('#source-list').style.minHeight = '3000px'; scrollTo(0, 0)")
    expect(button).to_have_class('secondary-action')
    button.click()
    expect(page.locator('#source-request-title')).to_be_in_viewport()
    assert not calls


@pytest.mark.parametrize('now,recent', [
    ('2026-11-14T12:00:00Z', True),
    ('2026-11-15T22:30:00Z', True),
    ('2026-11-15T23:30:00Z', True),  # Monday in Paris must retain recent Sunday-week additions.
    ('2026-11-18T22:30:00Z', True),  # Today and the previous six Paris dates.
    ('2026-11-18T23:30:00Z', False), # Seven days old in Paris, still six in UTC.
])
def test_recent_additions_use_last_seven_paris_dates_and_keep_filters(sources_screen, now, recent):
    page, calls, state = sources_screen
    state['candriam_added'] = '2026-11-12'
    page.add_init_script('''{
      const OriginalDate = Date;
      window.Date = class extends OriginalDate {
        constructor(...args) { super(...(args.length ? args : ["'''+now+'''"])); }
      };
    }''')
    page.reload(wait_until='networkidle')
    cards = page.locator('#source-list .source-card')
    assert cards.count() == 2
    assert page.locator('.is-new-source').count() == int(recent)
    assert cards.first.locator('h3').inner_text() == ('Candriam' if recent else 'BNP Paribas')
    assert page.locator('.source-group-title').count() == (2 if recent else 0)
    if recent:
        expect(page.locator('.source-group-title').first).to_contain_text('Ajoutées ces 7 derniers jours')
        assert cards.first.bounding_box()['height'] == cards.last.bounding_box()['height']
        expect(cards.first).to_have_css('background-color', 'rgb(255, 255, 255)')
        page.set_viewport_size({'width':390,'height':844})
        expect(cards.first).to_have_css('background-color', 'rgb(255, 255, 255)')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#source-search').fill('bnp')
    assert cards.count() == 1 and page.locator('.source-group-title').count() == 0
    assert not calls


@pytest.mark.parametrize('added', ['2026-11-16', '2026-02-30', 'invalid', ''])
def test_future_invalid_or_unknown_addition_is_not_new(sources_screen, added):
    page, _, state = sources_screen
    state['candriam_added'] = added
    page.add_init_script('''{
      const OriginalDate = Date;
      window.Date = class extends OriginalDate {
        constructor(...args) { super(...(args.length ? args : ["2026-11-14T12:00:00Z"])); }
      };
    }''')
    page.reload(wait_until='networkidle')
    assert page.locator('.is-new-source').count() == 0
