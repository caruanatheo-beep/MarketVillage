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
    assert page.get_by_role('combobox').count()==5
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
    choose(page,'start','Tous les débuts')
    choose(page,'period','Aujourd’hui')
    assert page.locator('.card h3').inner_text()=='Assistant Sales'
    choose(page,'period','Toutes publications')
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


@pytest.mark.parametrize('width', [1440, 760, 320])
def test_offer_cards_keep_the_same_height_with_long_fields(screen, width):
    page, data = screen
    page.set_viewport_size({'width': width, 'height': 900})
    long_title = (
        'Assistant produits financiers et coordination internationale en gestion d’actifs '
        'pour les clients institutionnels européens'
    )
    short, long = data['offers'][0], dict(data['offers'][1], title=long_title)
    locations = 'Aarhus · Danemark / Budapest · Hongrie / Dubaï · Émirats arabes unis / Londres · Royaume-Uni / Paris · France / Zurich · Suisse'
    multi_city = dict(short, title='Internship, Quantitative Research and Trading',
                      company='Qube Research & Technologies', location=locations)
    data['offers'] = [short, long, short, short, long, long, multi_city]
    page.evaluate('load()')
    cards = page.locator('.card')
    heights = cards.evaluate_all('(cards) => cards.map(card => card.offsetHeight)')
    assert len(set(heights)) == 1
    assert cards.first.locator('h3').evaluate(
        'h => h.offsetHeight === 2 * parseFloat(getComputedStyle(h).lineHeight)'
    )
    for selector in ('.card-employer', 'h3', '.facts'):
        offsets = cards.evaluate_all('''(cards, selector) => cards.map(card =>
            card.querySelector(selector).getBoundingClientRect().top - card.getBoundingClientRect().top
        )''', selector)
        assert max(offsets) - min(offsets) <= 1
    location = cards.last.locator('.location')
    assert location.evaluate('el => el.scrollWidth > el.clientWidth && el.clientWidth > 0')
    assert location.get_attribute('title') == locations
    assert cards.last.locator('.fact-start').evaluate('''start => {
        const date = start.getBoundingClientRect();
        const location = start.previousElementSibling.getBoundingClientRect();
        const card = start.closest('.card').getBoundingClientRect();
        return date.right <= card.right && Math.abs(date.top - location.top) <= 1;
    }''')
    facts = cards.first.locator('.fact').all_inner_texts()
    assert [text.replace('\xa0', ' ').strip() for text in facts] == ['Paris', 'Début : 2027-04']


@pytest.mark.parametrize('motion', ['no-preference', 'reduce'])
def test_offer_hover_respects_reduced_motion(screen, motion):
    page, _ = screen
    page.emulate_media(reduced_motion=motion)
    card = page.locator('.card').first
    card.hover()
    offset = card.evaluate('''card => {
        card.getAnimations().forEach(animation => animation.finish());
        const transform = getComputedStyle(card).transform;
        return transform === 'none' ? 0 : new DOMMatrixReadOnly(transform).m42;
    }''')
    assert offset == (-2 if motion == 'no-preference' else 0)


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
    page.locator('#filters-toggle').click()
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


def test_filters_are_shareable_removable_and_restored_from_the_url(screen):
    page,_=screen
    choose(page,'family','Sales')
    page.locator('#search').fill('assistant')
    page.locator('[data-sort="recent"]').click()
    url=page.url
    assert 'metier=Sales' in url and 'q=assistant' in url and 'tri=recent' in url
    chips=page.locator('#active-filters .filter-chip')
    assert [chip.locator('span').first.inner_text() for chip in chips.all()]==['« assistant »','Sales']
    assert page.locator('#active-filters .filter-reset').is_visible()
    page.goto(url,wait_until='networkidle')
    page.locator('.card').first.wait_for()
    assert page.locator('#family-trigger').inner_text()=='Sales'
    assert page.locator('#search').input_value()=='assistant'
    assert page.locator('[data-sort="recent"]').get_attribute('aria-pressed')=='true'
    page.get_by_role('button',name='Retirer le filtre Sales').click()
    assert page.locator('.card').count()==1 and 'metier=' not in page.url
    page.locator('#search').fill('')
    assert page.locator('#active-filters').is_hidden()
    assert page.locator('.card').count()==2


def test_load_more_replaces_pagination(screen):
    page,data=screen
    base=data['offers'][0]
    data['offers']=[dict(base,title=f'Offre {i}',url=f'https://careers.example.com/{i}') for i in range(120)]
    page.evaluate('load()')
    assert page.locator('.card').count()==50
    assert page.locator('#count').inner_text()=='120 offres'
    page.locator('#more').click()
    assert page.locator('.card').count()==100
    page.locator('#more').click()
    assert page.locator('.card').count()==120 and page.locator('#more').is_hidden()


def test_trailing_variants_are_grouped_without_losing_links(screen):
    page,data=screen
    base=data['offers'][0]
    data['offers']=[dict(base,title=f'Sales Programme (May class, {lang} Speaker)',url=f'https://careers.example.com/{lang}')
                    for lang in ('Thai','Japanese','Tagalog')]+[dict(base,title='Sales Programme (Equities) Paris desk',url='https://careers.example.com/other')]
    page.evaluate('load()')
    cards=page.locator('.card')
    assert cards.count()==2
    grouped=cards.first
    assert grouped.locator('h3').inner_text()=='Sales Programme'
    grouped.locator('.card-variants summary').click()
    links=grouped.locator('.card-variants a')
    assert links.count()==3 and links.first.inner_text()=='May class, Thai Speaker'
    assert links.last.get_attribute('href')=='https://careers.example.com/Tagalog'
    page.keyboard.press('Escape')
    assert links.first.is_hidden()


def test_relative_dates_flag_new_offers(screen):
    page,_=screen
    dates=page.locator('.card .date')
    assert dates.first.inner_text()=='Nouveau · aujourd’hui'
    assert 'is-new' in dates.first.get_attribute('class')
    assert dates.last.inner_text()=='Il y a 20 j'
    assert dates.last.get_attribute('title')=='Publication test'


def test_mobile_filters_open_in_a_sheet_with_sticky_search(screen):
    page,_=screen
    page.set_viewport_size({'width':390,'height':844})
    assert page.locator('#category-trigger').is_hidden()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.locator('#offers-view .filters').evaluate('el => getComputedStyle(el).position')=='sticky'
    page.locator('#filters-toggle').click()
    assert page.locator('#filter-panel').get_attribute('role')=='dialog'
    choose(page,'category','VIE')
    assert page.locator('#sheet-apply').inner_text()=='Aucune offre'
    page.locator('#sheet-reset').click()
    assert page.locator('#sheet-apply').inner_text()=='Voir 2 offres'
    choose(page,'family','Sales')
    assert page.locator('#filters-count').inner_text()=='1'
    page.locator('#sheet-apply').click()
    assert page.locator('#filter-panel').is_hidden()
    assert page.locator('.card').count()==1
    page.locator('#filters-toggle').click()
    page.keyboard.press('Escape')
    assert page.locator('#filter-panel').is_hidden()
    assert page.locator('#filters-toggle').evaluate('el => el === document.activeElement')


def test_place_filter_groups_cities_under_countries_and_is_shareable(screen):
    page,data=screen
    base=data['offers'][0]
    rows=[('Paris · France',3),('Montrouge · France',2),('Londres · Royaume-Uni',2),('Singapour',2),('Paris 8e · France / Londres · Royaume-Uni',1),('Non précisé',1)]
    data['offers']=[dict(base,title=f'{loc} {i}',location=loc,url=f'https://careers.example.com/{n}-{i}')
                    for n,(loc,count) in enumerate(rows) for i in range(count)]
    page.evaluate('load()')
    page.locator('#place-trigger').click()
    labels=page.locator('#place-menu [role=option]').all_inner_texts()
    assert labels[:4]==['Tous les lieux','France (6)','Paris (4)','Montrouge (2)']
    assert 'Royaume-Uni (3)' in labels and 'Singapour (2)' in labels and not any('Non précisé' in l for l in labels)
    page.keyboard.press('Escape')
    choose(page,'place','Paris (4)')
    assert page.locator('.card').count()==4 and 'lieu=c%3AParis' in page.url
    assert page.locator('#active-filters .filter-chip span').first.inner_text()=='Paris'
    choose(page,'place','Royaume-Uni (3)')
    assert page.locator('.card').count()==3


def test_phone_cards_show_city_only_and_unknown_start_is_explicit(screen):
    page,data=screen
    data['offers'][0].update(location='Londres · Royaume-Uni / Paris · France',start='Non précisé')
    page.evaluate('load()')
    location=page.locator('.card .location').first
    assert location.inner_text()=='Londres · Royaume-Uni / Paris · France'
    assert page.locator('.card .start').first.inner_text()=='à confirmer'
    page.set_viewport_size({'width':390,'height':844})
    assert location.inner_text()=='Londres / Paris'
    assert location.get_attribute('title')=='Londres · Royaume-Uni / Paris · France'
