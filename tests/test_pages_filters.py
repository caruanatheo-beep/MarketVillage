"""Exercise the public filter menus in Chromium with synthetic offers only."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1] / 'deploy/github-pages/site'
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
