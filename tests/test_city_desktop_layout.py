"""Exercise the shipped City interface offline with synthetic data."""

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


ASSETS = Path(__file__).resolve().parents[1] / 'internships_project' / 'city_assets'


@pytest.mark.parametrize('width', [1024, 1180, 1280, 1440])
def test_desktop_navigation_actions_do_not_overlap(width):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': 768})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def respond(route):
            url = route.request.url
            if '/city/api/state' in url:
                route.fulfill(json={'agents': [], 'tasks': [], 'events': [],
                                    'workflows': [], 'today_completed': 0})
            elif '/city/api/' in url:
                route.fulfill(json={})
            else:
                route.fulfill(content_type='text/html', body='<div id="root"></div>')

        page.route('**/*', respond)
        page.goto('http://city.test/')
        page.add_style_tag(content=(ASSETS / 'city.css').read_text(encoding='utf-8'))
        page.add_script_tag(content=(ASSETS / 'city.js').read_text(encoding='utf-8'))
        page.get_by_role('navigation', name='Espaces MarketDesk City').wait_for()
        boxes = page.locator('.command-topbar > *').evaluate_all(
            '(elements) => elements.map(e => {const r=e.getBoundingClientRect();'
            'return {left:r.left,right:r.right,top:r.top,bottom:r.bottom};})')
        for box in boxes:
            assert box['left'] >= 0 and box['right'] <= width, boxes
        for first, second in zip(boxes, boxes[1:]):
            assert (first['right'] <= second['left'] or first['bottom'] <= second['top']), boxes
        for button in page.locator('.game-hud button').all():
            assert button.is_visible()
            button.click(trial=True)
        assert not errors
        browser.close()


@pytest.mark.parametrize('width,height', [(1024, 768), (1366, 768), (1440, 900)])
@pytest.mark.parametrize('workspace', ['Missions', 'Équipe', 'Développement'])
def test_search_keeps_all_results_reachable_over_open_workspace(width, height, workspace):
    agents = [{'id': f'fixture_{i}', 'name': f'Agent exemple {i:02}',
               'role': 'Analyse', 'area': 'career', 'description': 'Exemple synthétique',
               'available': True, 'xp': 0, 'level': 1, 'level_progress': 0,
               'achievements': [], 'status': 'idle', 'latest': None} for i in range(24)]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': height})
        page.set_default_timeout(5000)

        def respond(route):
            if '/city/api/state' in route.request.url:
                route.fulfill(json={'agents': agents, 'tasks': [], 'events': [],
                                    'workflows': [], 'today_completed': 0})
            elif '/city/api/' in route.request.url:
                route.fulfill(json={'tasks': [], 'events': []})
            else:
                route.fulfill(content_type='text/html', body='<div id="root"></div>')

        page.route('**/*', respond)
        page.goto('http://city.test/')
        page.add_style_tag(content=(ASSETS / 'city.css').read_text(encoding='utf-8'))
        page.add_script_tag(content=(ASSETS / 'city.js').read_text(encoding='utf-8'))
        page.get_by_role('button', name='Équipe', exact=True).wait_for()
        page.get_by_role('button', name=workspace, exact=True).click()
        search = page.get_by_role('textbox', name='Rechercher un agent ou une mission')
        search.fill('Agent exemple')
        last_result = page.locator('.command-search-results').get_by_role('button', name='Agent exemple 23')
        last_result.wait_for()
        bounds = page.locator('.command-search-results').bounding_box()
        assert bounds['y'] + bounds['height'] <= height - 8, bounds
        page.locator('.command-search-results').get_by_role('button', name='Agent exemple 00').click(trial=True)
        if width == 1366 and workspace == 'Missions':
            output = ASSETS.parents[1] / '.pytest_city_tmp'
            output.mkdir(exist_ok=True)
            page.screenshot(path=str(output / 'city-desktop-search.png'))
        last_result.click()
        assert search.input_value() == ''
        assert page.get_by_role('dialog', name='Fiche de l’agent').is_visible()
        search.fill('Agent exemple')
        page.get_by_role('button', name='Fermer la recherche', exact=True).click()
        assert page.locator('.command-search-results').count() == 0
        page.get_by_role('button', name=workspace, exact=True).click()
        page.locator('.game-popup-heading').get_by_role('button', name='Fermer', exact=True).click()
        assert page.locator('.game-popup').count() == 0
        browser.close()
