"""Exercise the public filter menus in Chromium with synthetic offers only."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1] / 'deploy/github-pages/site'
if (ROOT.parents[2] / 'Internships' / 'deploy/github-pages/site').is_dir():
    ROOT = ROOT.parents[2] / 'Internships' / 'deploy/github-pages/site'
BASE = 'https://marketdesk.test/'


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def screen(browser):
    today = datetime.now(ZoneInfo('Europe/Paris')).date()
    def offer(title, family, start, published, kind, categories):
        return dict(title=title, company='Banque Test', location='Paris', family=family,
                    kind=kind, categories=categories, start=start, start_month=start,
                    published=str(published), date_label='Publication test', logo='',
                    url='https://careers.example.com/'+family.replace(' ','-'))
    data = {'offers':[
        offer('Assistant Sales','Sales','2027-04',today,'Stage',['Stages Paris']),
        offer('Portfolio Graduate','Asset Management','2027-06',today-timedelta(days=20),'Graduate',['Graduate'])],
        'sources':{'checked':1,'unavailable':0,'retained':0},'updated':datetime.now().astimezone().isoformat()}
    page = browser.new_page(viewport={'width':1440,'height':1000})
    page.clock.install()
    errors = []
    page.on('pageerror',lambda error:errors.append(str(error)))
    def route(request):
        name=request.request.url.removeprefix(BASE).split('?')[0] or 'index.html'
        if name=='offers.json':
            request.fulfill(body=json.dumps(data),content_type='application/json')
        elif name in {'index.html','site.css','app.js','sources.js','marketdesk-icon.svg'}:
            mime={'html':'text/html','css':'text/css','js':'application/javascript','svg':'image/svg+xml'}
            request.fulfill(body=(ROOT/name).read_bytes(),content_type=mime[name.rsplit('.',1)[1]])
        else:
            request.abort()
    page.route(BASE+'**',route)
    page.goto(BASE,wait_until='networkidle')
    page.locator('.card').first.wait_for()
    yield page,data
    assert not errors,errors
    page.close()


def choose(page,field,text):
    page.locator('#'+field+'-trigger').click()
    page.locator('#'+field+'-menu').get_by_role('option',name=text,exact=True).click()


def test_click_selection_reset_and_contract_are_connected_to_offers(screen):
    page,_=screen
    assert page.get_by_role('combobox').count()==4
    choose(page,'family','Sales')
    assert page.locator('.card').count()==1
    assert page.locator('.card h3').inner_text()=='Assistant Sales'
    assert page.locator('#family-trigger').get_attribute('aria-expanded')=='false'
    assert page.locator('#family-trigger').inner_text()=='Sales'
    choose(page,'family','Tous métiers')
    assert page.locator('.card').count()==2
    choose(page,'category','Graduate / Junior')
    assert page.locator('.card h3').inner_text()=='Portfolio Graduate'


def test_keyboard_selection_escape_tab_and_typeahead(screen):
    page,_=screen
    trigger=page.locator('#family-trigger')
    trigger.focus();trigger.press('ArrowDown');trigger.press('End');trigger.press('Enter')
    assert page.locator('.card h3').inner_text()=='Assistant Sales'
    trigger.press('ArrowUp');trigger.press('Home');trigger.press('Escape')
    assert trigger.inner_text()=='Sales'
    assert trigger.get_attribute('aria-activedescendant') is None
    trigger.press('Enter');trigger.press('Home');trigger.press('Enter')
    assert page.locator('.card').count()==2
    trigger.press('a');trigger.press('Enter')
    assert page.locator('.card h3').inner_text()=='Portfolio Graduate'
    trigger.press('Enter');trigger.press('Tab')
    assert trigger.get_attribute('aria-expanded')=='false'
    assert page.locator('#period-trigger').evaluate('(element)=>element===document.activeElement')


def test_only_one_menu_and_outside_click_closes_it(screen):
    page,_=screen
    page.locator('#family-trigger').click()
    page.locator('#category-trigger').click()
    assert page.locator('[role="listbox"]:visible').count()==1
    assert page.locator('#family-trigger').get_attribute('aria-expanded')=='false'
    page.locator('#offers-view h1').click()
    assert page.locator('[role="listbox"]:visible').count()==0


def test_dynamic_start_dates_and_publication_filter(screen):
    page,_=screen
    choose(page,'start','juin 2027')
    assert page.locator('.card h3').inner_text()=='Portfolio Graduate'
    choose(page,'start','Toutes les dates')
    choose(page,'period','Aujourd’hui')
    assert page.locator('.card h3').inner_text()=='Assistant Sales'
    choose(page,'period','Toutes les dates')
    assert page.locator('.card').count()==2


def test_reloading_data_preserves_selection_or_falls_back_when_removed(screen):
    page,data=screen
    choose(page,'family','Sales')
    page.evaluate('load()')
    assert page.locator('#family-trigger').inner_text()=='Sales'
    assert page.locator('.card').count()==1
    data['offers']=data['offers'][1:]
    page.evaluate('load()')
    assert page.locator('#family-trigger').inner_text()=='Tous métiers'
    assert page.locator('.card h3').inner_text()=='Portfolio Graduate'


def test_offer_details_align_when_one_title_wraps(screen):
    page, data = screen
    data['offers'][0]['title'] = (
        'Assistant produits financiers et coordination internationale en gestion d’actifs '
        'pour les clients institutionnels européens'
    )
    page.evaluate('load()')
    heights = page.locator('.card h3').evaluate_all(
        '(titles) => titles.map(title => title.getBoundingClientRect().height)'
    )
    assert heights[0] > heights[1]
    detail_tops = page.locator('.card .facts').evaluate_all(
        '(details) => details.map(detail => detail.getBoundingClientRect().top)'
    )
    assert detail_tops[0] == pytest.approx(detail_tops[1], abs=1)


def test_compact_offers_scroll_two_rows_on_desktop(screen):
    page, data = screen
    data['offers'] *= 5
    page.evaluate('load()')
    card = page.locator('.card').first
    title = card.locator('h3').bounding_box()
    employer = card.locator('.card-employer').bounding_box()
    assert 0 <= employer['y'] - title['y'] - title['height'] <= 8
    window = page.locator('#offers-window')
    bottom = window.bounding_box()['y'] + window.bounding_box()['height']
    fourth = page.locator('.card').nth(3).bounding_box()
    assert fourth['y'] + fourth['height'] <= bottom < page.locator('.card').nth(4).bounding_box()['y']
    window.evaluate('w => w.scrollTop = w.scrollHeight')
    position = window.evaluate('w => w.scrollTop')
    assert position > 0
    page.evaluate('load()')
    assert window.evaluate('w => w.scrollTop') == position
    choose(page, 'family', 'Sales')
    assert window.evaluate('w => w.scrollTop') == 0
    page.set_viewport_size({'width': 390, 'height': 844})
    assert window.evaluate('w => getComputedStyle(w).overflowY') == 'visible'


@pytest.mark.parametrize('motion', ['no-preference', 'reduce'])
def test_filter_motion_respects_user_preference_and_does_not_animate_typing(screen, motion):
    page, _ = screen
    page.emulate_media(reduced_motion=motion)
    result = page.evaluate('''() => {
        document.querySelector('#family-trigger').click();
        const menu = document.querySelector('#family-menu');
        const menuAnimation = getComputedStyle(menu).animationName;
        [...menu.children].find(option => option.textContent === 'Sales').click();
        const grid = document.querySelector('#offers');
        const filterAnimation = grid.getAnimations().length;
        const search = document.querySelector('#search');
        search.value = 'Sales';
        search.dispatchEvent(new Event('input'));
        return {menuAnimation, filterAnimation, typingAnimation: grid.getAnimations().length};
    }''')
    assert result == {
        'menuAnimation': 'surface-enter' if motion == 'no-preference' else 'none',
        'filterAnimation': int(motion == 'no-preference'),
        'typingAnimation': 0,
    }
    assert page.locator('.card h3').inner_text() == 'Assistant Sales'


def test_visible_page_automatically_updates_timestamp_and_keeps_filters(screen):
    page,data=screen
    choose(page,'family','Sales')
    data['offers'][0]['title']='Nouvelle publication Sales'
    data['updated']='2026-11-17T17:54:00+00:00'
    page.clock.fast_forward(5*60*1000)
    page.get_by_role('heading',name='Nouvelle publication Sales',exact=True).wait_for()
    assert page.locator('#family-trigger').inner_text()=='Sales'
    assert '18:54' in page.locator('#updated').inner_text()


def test_hidden_page_waits_for_return_before_fetching_new_data(screen):
    page,data=screen
    calls=[]
    def respond(route):
        calls.append(route.request.url)
        route.fulfill(body=json.dumps(data),content_type='application/json')
    page.route(BASE+'offers.json',respond)
    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true})")
    data['offers'][0]['title']='Publication au retour'
    page.clock.fast_forward(5*60*1000)
    assert not calls
    page.evaluate("""Object.defineProperty(document,'hidden',{configurable:true,value:false});
        document.dispatchEvent(new Event('visibilitychange'));""")
    page.get_by_role('heading',name='Publication au retour',exact=True).wait_for()
    assert len(calls)==1


def test_browser_back_forward_cache_restoration_refreshes_data(screen):
    page,data=screen
    data['offers'][0]['title']='Publication après restauration'
    page.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))")
    page.get_by_role('heading',name='Publication après restauration',exact=True).wait_for()


def test_date_menu_fits_short_mobile_viewport_and_keyboard_scrolls_options(screen):
    page,_=screen
    page.set_viewport_size({'width':390,'height':500})
    trigger=page.locator('#start-trigger')
    trigger.click()
    menu=page.locator('#start-menu')
    box=menu.bounding_box()
    assert box['y']>=0 and box['y']+box['height']<=500
    assert box['x']>=0 and box['x']+box['width']<=390
    trigger.press('End')
    active=trigger.get_attribute('aria-activedescendant')
    option=page.locator('#'+active).bounding_box()
    assert option['y']>=box['y'] and option['y']+option['height']<=box['y']+box['height']
    trigger.press('Escape')


def test_popup_hover_does_not_scroll_page(screen):
    page,_=screen
    page.locator('#family-trigger').click()
    before=page.evaluate('window.scrollY')
    page.locator('#family-menu').get_by_role('option',name='Sales',exact=True).hover()
    assert page.evaluate('window.scrollY')==before


def test_location_search_accepts_normalized_and_original_city_names(screen):
    page,data=screen
    data['offers'][0].update(location='Londres · Royaume-Uni',location_source='London, GBR')
    page.evaluate('load()')
    for query in ['London','Londres','Royaume-Uni']:
        page.locator('#search').fill(query)
        assert page.locator('.card h3').inner_text()=='Assistant Sales'
        assert page.locator('.location').inner_text()=='Londres · Royaume-Uni'
