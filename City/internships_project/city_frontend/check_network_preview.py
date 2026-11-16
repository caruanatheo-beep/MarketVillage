"""Manual browser check against preview-command.mjs, using isolated public research data."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / '.venv/Lib/site-packages')]
from playwright.sync_api import sync_playwright
from internships_project.network_discovery import validate_research, contact_focus

out = ROOT / 'artifacts/command-center'
records, _ = validate_research(json.loads((out / 'network-public-research.json').read_text(encoding='utf-8')))
contacts = [{**c, **contact_focus(c), 'id': str(i), 'detected_at': datetime.now(timezone.utc).isoformat()} for i, c in enumerate(records)]
sales = [c for c in contacts if c['sales_priority']]
assert sales and len(sales) < len(contacts), 'The fixture must exercise both Sales and other roles.'
schedule = {'enabled': True, 'last_day': '', 'status': 'idle', 'error': '', 'report': {}}
directory = []
api_status = 200
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':1920, 'height':1080})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    def network(route):
        global directory
        if api_status != 200:
            route.fulfill(status=api_status, json={'detail':'Network fixture unavailable'})
            return
        if route.request.method == 'POST':
            body = route.request.post_data_json
            if 'enabled' in body:
                schedule['enabled'] = body['enabled']
            if body.get('collect'):
                directory = contacts
                schedule.update(last_day=datetime.now(timezone.utc).date().isoformat(), status='completed', report={'count':len(contacts), 'text':f'{len(contacts)} contacts de validation isolée.'})
        route.fulfill(json={'contacts': directory, 'schedule': schedule})
    page.route('**/city/api/network', network)
    page.goto('http://127.0.0.1:7878/city/')
    nav_fonts = page.locator('.game-hud>button>span').evaluate_all('(els)=>els.map(el=>getComputedStyle(el).fontSize)')
    assert len(nav_fonts) == 4 and len(set(nav_fonts)) == 1, nav_fonts
    page.get_by_role('button', name='Contacts', exact=True).click()
    page.wait_for_selector('.network-empty')
    assert page.get_by_role('dialog', name='Contacts', exact=True).is_visible()
    assert page.locator('.panel-tabs').get_by_role('button', name='Contacts', exact=True).count() == 0
    page.locator('.network-schedule>summary').click()
    page.get_by_role('button', name='Collecter aujourd’hui', exact=True).click()
    page.wait_for_selector('.network-contact')
    assert page.locator('.network-contact').count() == len(sales)
    normalized_name = page.locator('.network-contact h4[title="Benjamin DUSSAULT"]')
    assert normalized_name.inner_text() == 'Benjamin Dussault'
    assert any(c['name'] == 'Benjamin DUSSAULT' for c in contacts)
    page.get_by_role('button', name=re.compile('^Tous les contacts')).click()
    assert page.locator('.network-contact').count() == len(contacts)
    assert page.locator('.network-specialty').first.inner_text().startswith('Sales')
    page.get_by_role('button', name=re.compile('^Autres métiers')).click()
    assert page.locator('.network-contact').count() == len(contacts)-len(sales)
    page.get_by_role('button', name=re.compile('^Sales prioritaires')).click()
    page.get_by_label('Spécialité', exact=True).select_option(sales[0]['specialty'])
    assert page.locator('.network-contact').count() == sum(c['specialty']==sales[0]['specialty'] for c in sales)
    page.get_by_label('Spécialité', exact=True).select_option('')
    page.get_by_label('Rechercher un contact').fill(sales[0]['name'])
    assert page.locator('.network-contact').count() == 1
    page.get_by_label('Rechercher un contact').fill('')
    page.locator('.network-contact summary').first.click()
    assert page.locator('.network-contact details[open]').count() == 1
    page.locator('.network-contact summary').first.click()
    page.get_by_role('button', name='Suspendre', exact=True).click()
    page.get_by_role('button', name='Activer', exact=True).wait_for(state='visible')
    page.locator('.network-schedule>summary').click()
    for w,h in [(1920,1080),(1366,768),(1280,720),(390,844)]:
        page.set_viewport_size({'width':w,'height':h})
        page.wait_for_timeout(500)
        directory_box = page.locator('.network-directory')
        assert directory_box.is_visible()
        dims=directory_box.evaluate('(el)=>({client:el.clientWidth,scroll:el.scrollWidth})')
        assert dims['scroll'] <= dims['client'] + 1, dims
        dialog=page.locator('.network-window').bounding_box()
        assert dialog and dialog['x'] >= 0 and dialog['y'] >= 0
        assert dialog['x'] + dialog['width'] <= w and dialog['y'] + dialog['height'] <= h
        card_heights = page.locator('.network-contact').evaluate_all('(els)=>els.map(el=>Math.round(el.getBoundingClientRect().height))')
        assert max(card_heights) <= 200, (w, card_heights)
        print(f'{w}px: compact card heights {card_heights}')
        page.screenshot(path=str(out / f'network-{w}.png'))
    page.keyboard.press('Tab')
    assert page.evaluate('!!document.activeElement.closest(".network-window")')
    page.keyboard.press('Escape')
    assert page.locator('.network-window').count() == 0
    page.get_by_role('button', name='Contacts', exact=True).click()
    page.get_by_role('button', name='Fermer les contacts', exact=True).click()
    assert page.locator('.network-window').count() == 0
    # A failed collection must be visible without losing existing contacts.
    schedule.update(status='failed', error='Erreur de test : recherche indisponible.')
    page.reload()
    page.get_by_role('button', name='Contacts', exact=True).click()
    page.get_by_text('Erreur de test : recherche indisponible.').wait_for(state='visible')
    assert page.locator('.network-contact').count() == len(sales)
    # Missing old-server route must not be shown as a paused/empty collection.
    api_status = 404
    page.reload()
    page.get_by_role('button', name='Contacts', exact=True).click()
    page.get_by_text('Dossier inaccessible', exact=True).wait_for(state='visible')
    assert 'HTTP 404' in page.locator('.network-load-state').inner_text()
    assert page.locator('.network-summary').count() == 0
    assert page.get_by_role('button', name='Réessayer', exact=True).is_enabled()
    api_status = 200
    page.get_by_role('button', name='Réessayer', exact=True).click()
    page.wait_for_selector('.network-contact')
    assert page.locator('.network-load-state').count() == 0
    api_status = 401
    page.reload()
    page.get_by_role('button', name='Contacts', exact=True).click()
    page.get_by_role('link', name='Se reconnecter', exact=True).wait_for(state='visible')
    assert page.get_by_role('link', name='Se reconnecter', exact=True).get_attribute('href') == '/login'
    assert not errors, errors
    print('PASS: Sales default, all/other role views, specialty filter, Sales-first ordering, responsive modal, keyboard, HTTP errors and recovery.')
    browser.close()
