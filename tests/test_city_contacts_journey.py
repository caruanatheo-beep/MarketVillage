"""Contacts journey with synthetic reports and no external requests."""
import json
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internships_project import network_discovery, state_store
from internships_project.city_routes import add_city_routes
from internships_project.marketdesk_city import CityStore


def test_duplicates_count_only_existing_profiles_not_unsourced_rejections(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'synthetic.sqlite3')
    lead = {'name': 'Alex Exemple', 'company': 'Banque Exemple', 'role': 'FX Sales',
            'source_url': 'https://example.invalid/bio', 'source_excerpt': 'Synthetic evidence',
            'origin': 'lina_public_search'}
    first, duplicates = network_discovery.save_leads('synthetic-owner', [lead])
    assert len(first) == 1 and duplicates == 0
    unsupported = {**lead, 'name': 'Autre Exemple', 'source_url': ''}
    added, duplicates = network_discovery.save_leads('synthetic-owner', [unsupported, lead])
    assert added == []
    assert duplicates == 1
    assert [c['name'] for c in network_discovery.list_contacts('synthetic-owner')] == ['Alex Exemple']


def test_clara_report_reaches_contacts_without_truncation_or_other_account_data(tmp_path, monkeypatch):
    store = CityStore(tmp_path / 'synthetic.sqlite3')
    task = store.create_task('synthetic-owner', 'securities_scout', 'Synthetic collection', {'operation': 'discover_service_contacts'})
    report = {'count': 0, 'duplicates': 4, 'target': 10,
              'warnings': ['Source temporairement indisponible'],
              'source': 'Sources publiques', 'text': 'Bilan complet. ' * 40,
              'contacts': [{'name': 'Not part of the report'}]}
    # Populate only this test's isolated database, without running any worker.
    with store.db() as db:
        db.execute("UPDATE city_tasks SET status='completed',result_json=? WHERE id=?",
                   (json.dumps(report), task['id']))
    monkeypatch.setattr(network_discovery, 'list_contacts', lambda username: [])
    app = FastAPI()
    add_city_routes(app, lambda request: request.headers.get('x-test-user'), store, None)
    with TestClient(app) as client:
        response = client.get('/city/api/network', headers={'x-test-user': 'synthetic-owner'})
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'private, no-store'
        clara = response.json()['clara']
        assert clara['report'] == {k: v for k, v in report.items() if k != 'contacts'}
        assert len(clara['summary']) <= 300
        other = client.get('/city/api/network', headers={'x-test-user': 'synthetic-other'}).json()
        assert other['clara'] == {'status': 'idle'}


def test_empty_clara_report_stays_compatible(tmp_path):
    store = CityStore(tmp_path / 'synthetic.sqlite3')
    store.create_task('synthetic-owner', 'securities_scout', 'Synthetic pending collection', {'operation': 'discover_service_contacts'})
    status = store.securities_scout_status('synthetic-owner')
    assert status['report'] == {}
    assert status['summary'] == ''


def test_duplicate_examples_are_bounded_public_evidence_and_do_not_modify_saved_records(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'synthetic.sqlite3')
    leads = [{'name': f'Alex Exemple {i}', 'company': 'Banque Exemple', 'role': 'FX Sales',
              'linkedin_url': f'https://www.linkedin.com/in/synthetic-{i}',
              'source_url': f'https://example.invalid/bio/{i}', 'notes': 'Synthetic private note'}
             for i in range(8)]
    network_discovery.save_leads('synthetic-owner', leads)
    before = state_store.load_user_data('synthetic-owner', 'mail_contacts')
    examples = []
    added, count = network_discovery.save_leads('synthetic-owner', leads + leads, duplicate_examples=examples)
    assert not added and count == 16
    assert len(examples) == 5
    assert examples[0] == {k: leads[0][k] for k in ('name', 'role', 'company', 'source_url')} | {
        'reason': 'Même profil LinkedIn'}
    assert all(set(example) == {'name', 'role', 'company', 'source_url', 'reason'} for example in examples)
    assert state_store.load_user_data('synthetic-owner', 'mail_contacts') == before
    assert network_discovery.save_leads('synthetic-other', leads, duplicate_examples=[])[1] == 0


def test_lina_web_research_reports_duplicates_without_an_extra_search(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'synthetic.sqlite3')
    monkeypatch.setenv('MARKETDESK_NETWORK_SEARCH_MODE', 'ai')
    known = {'name': 'Alex Exemple', 'company': 'Banque Exemple', 'role': 'FX Sales',
             'source_url': 'https://example.invalid/bio'}
    network_discovery.save_leads('synthetic-owner', [known])
    calls = []

    def research(username):
        calls.append(username)
        return [known] + [{**known, 'name': f'Autre Exemple {i}'} for i in range(10)], 0

    monkeypatch.setattr(network_discovery, 'research_contacts', research)
    report = network_discovery.discover_contacts('synthetic-owner')
    assert report['count'] == 10 and report['duplicates'] == 1
    assert report['duplicate_examples'] == [{**known, 'reason': 'Même nom et même entreprise'}]
    assert calls == ['synthetic-owner']


def test_lina_report_reaches_contacts_with_empty_collection_reasons(tmp_path, monkeypatch):
    store = CityStore(tmp_path / 'synthetic.sqlite3')
    store.enqueue_network_daily('synthetic-owner', manual=True)
    schedule = store.network_schedule('synthetic-owner')
    report = {'count': 0, 'duplicates': 2, 'rejected': 1, 'target': 10,
              'warnings': ['Recherche partiellement indisponible'],
              'source': 'Sources synthétiques', 'text': 'Aucun nouveau contact.',
              'contacts': [{'name': 'Excluded from the response report'}]}
    with store.db() as db:
        db.execute("UPDATE city_tasks SET status='completed',result_json=? WHERE id=?",
                   (json.dumps(report), schedule['last_task_id']))
    monkeypatch.setattr(network_discovery, 'list_contacts', lambda username: [])
    app = FastAPI()
    add_city_routes(app, lambda request: 'synthetic-owner', store, None)
    with TestClient(app) as client:
        response = client.get('/city/api/network')
        assert response.status_code == 200
        assert response.json()['schedule']['report'] == {
            k: v for k, v in report.items() if k != 'contacts'}


def test_desktop_contacts_empty_report_targeted_retry_and_visible_evidence():
    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[1]
    bundle = (root / 'internships_project/city_assets/city.js').read_text(encoding='utf-8')
    # Mount the shipped Contacts component alone, with synthetic API responses.
    mount = re.search(r'\.render\((\(0,\w+\.jsx\))\(\w+,\{\}\)\)', bundle)
    component = re.search(r'\(0,(\w+)\.jsx\)\((\w+),\{\}\),\(0,\1\.jsxs\)\("footer",\{className:"network-window-footer"', bundle)
    assert mount and component
    entry = mount.group(0)[len('.render('):-1]
    assert bundle.count(entry) == 1
    bundle = bundle.replace(entry, f'{mount.group(1)}({component.group(2)},{{}})')
    state = {'contacts': [], 'schedule': {'enabled': True, 'status': 'completed',
             'report': {'count': 0, 'duplicates': 3, 'rejected': 2,
                        'warnings': ['Source indisponible'],
                        'duplicate_examples': [
                            {'name': 'Alex Doublon', 'role': 'FX Sales', 'company': 'Banque Exemple',
                             'reason': 'Même nom et même entreprise', 'source_url': 'https://example.invalid/duplicate'},
                            {'name': 'Sans lien sûr', 'role': 'Trader', 'company': 'Banque Exemple',
                             'reason': 'Même profil LinkedIn', 'source_url': 'javascript:alert(1)'}]}},
             'clara': {'status': 'completed', 'report': {'count': 0, 'duplicates': 1}}}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1366, 'height': 768})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def respond(route):
            if route.request.url.endswith('/city/api/network'):
                route.fulfill(json=state)
            else:
                route.fulfill(content_type='text/html', body='<div id="root"></div>')

        page.route('**/*', respond)
        page.goto('http://city.test/')
        page.evaluate('window.__marketdeskNativePanels = true')
        page.add_style_tag(content=(root / 'internships_project/city_assets/city.css').read_text(encoding='utf-8'))
        page.add_script_tag(content=bundle)
        page.get_by_text('Ton répertoire est vide.', exact=False).wait_for()
        page.get_by_role('button', name='Voir les bilans et cibler une recherche').click()
        assert page.get_by_text('3 doublons écartés', exact=False).is_visible()
        assert page.get_by_text('2 fiches insuffisamment sourcées écartées', exact=False).is_visible()
        assert page.get_by_text('Source indisponible', exact=True).is_visible()
        assert page.get_by_text('1 doublons écartés', exact=False).is_visible()
        page.get_by_text('Voir les doublons écartés', exact=True).click()
        assert page.get_by_text('Alex Doublon', exact=True).is_visible()
        assert page.get_by_text('Même nom et même entreprise.', exact=False).is_visible()
        duplicate_link = page.get_by_role('link', name='Source du doublon')
        assert duplicate_link.count() == 1
        assert duplicate_link.get_attribute('href') == 'https://example.invalid/duplicate'
        page.get_by_label('Critères de recherche').fill('Collateral CACEIS Paris')
        page.get_by_role('button', name='Préparer dans l’import assisté').click()
        assert page.get_by_label('Requête LinkedIn').input_value() == 'Collateral CACEIS Paris'
        link = page.get_by_role('link', name='Ouvrir la recherche LinkedIn')
        assert link.get_attribute('href').endswith('keywords=Collateral%20CACEIS%20Paris')
        # All navigation remains mocked; no external site is opened.
        state['contacts'] = [{'id': 'synthetic', 'name': 'Alex Exemple', 'role': 'FX Sales',
            'company': 'Banque Exemple', 'location': '', 'linkedin_url': '', 'school': '',
            'detected_at': '2026-11-07T09:00:00Z', 'source_url': 'https://example.invalid/bio',
            'source_title': 'Biographie publique', 'source_excerpt': 'Preuve synthétique du poste.',
            'verification_status': 'À vérifier', 'employment_status': 'Poste actuel à confirmer',
            'specialty': 'FX', 'sales_priority': True, 'origin': 'securities_public_search'}]
        page.reload()
        page.evaluate('window.__marketdeskNativePanels = true')
        page.add_script_tag(content=bundle)
        page.get_by_text('Preuve synthétique du poste.', exact=True).wait_for(state='visible')
        assert page.get_by_role('link', name='Source publique').get_attribute('href') == 'https://example.invalid/bio'
        page.get_by_label('Rechercher un contact').fill('Aucun profil ne porte ce nom')
        assert page.get_by_text('Aucun contact ne correspond aux filtres.', exact=False).is_visible()
        assert page.get_by_text('Ton répertoire est vide.', exact=False).count() == 0
        page.get_by_role('button', name='Effacer les filtres').click()
        assert page.get_by_text('Preuve synthétique du poste.', exact=True).is_visible()
        # Pasted profiles can lack a public URL: explain that limitation and
        # keep the evidence visible instead of presenting an invented link.
        state['contacts'][0].update(source_url='', source_title='', origin='lina_assisted_paste')
        page.reload()
        page.evaluate('window.__marketdeskNativePanels = true')
        page.add_style_tag(content=(root / 'internships_project/city_assets/city.css').read_text(encoding='utf-8'))
        page.add_script_tag(content=bundle)
        page.get_by_text('Aucun lien public vérifiable enregistré', exact=False).wait_for(state='visible')
        assert page.get_by_text('Preuve synthétique du poste.', exact=True).is_visible()
        assert page.get_by_role('link', name='Source publique').count() == 0
        assert not errors
        browser.close()
