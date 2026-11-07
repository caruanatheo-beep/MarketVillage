"""Contacts remain usable around malformed records, using only synthetic data."""
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from internships_project import network_discovery as network, state_store
from internships_project.city_routes import add_city_routes
from internships_project.marketdesk_city import CityStore, CityWorker


@pytest.mark.parametrize('broken', [None, [], 'invalid', 42, False])
@pytest.mark.parametrize('agent', ['networker', 'securities_scout'])
def test_directory_collection_empty_report_and_assisted_retry(tmp_path, monkeypatch, broken, agent):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'synthetic.sqlite3')
    monkeypatch.setenv('MARKETDESK_NETWORK_SEARCH_MODE', 'public')
    store = CityStore(state_store.USER_DB_PATH)
    initial = {'broken': broken, 'manual': {
        'name': 'Existing Example', 'company': 'Synthetic Bank', 'role': 'FX Sales',
        'notes': 'Keep my correction', 'origin': 'lina_assisted',
        'source_url': 'https://example.invalid/existing', 'source_excerpt': 'Existing evidence'}}
    before = deepcopy(initial)
    state_store.save_user_data('synthetic-owner', 'mail_contacts', initial)
    lead = {'name': 'Alex Exemple', 'company': 'CACEIS', 'role': 'FX Sales',
            'source_url': 'https://example.invalid/bio', 'source_excerpt': 'Alex Exemple FX Sales CACEIS',
            'origin': 'lina_public_search'}
    monkeypatch.setattr(network, 'search_public', lambda *args, **kwargs: [dict(lead)])
    monkeypatch.setattr(network, '_search_service_contacts_with_codex', lambda *args, **kwargs: [])
    app = FastAPI()
    add_city_routes(app, lambda req: req.headers.get('x-test-user'), store, None)
    headers = {'x-test-user': 'synthetic-owner', 'X-MarketDesk-City': '1'}

    def collect():
        if agent == 'networker':
            assert store.enqueue_network_daily('synthetic-owner', manual=True) == 1
        else:
            store.create_task('synthetic-owner', agent, 'Synthetic collection',
                              {'operation': 'discover_service_contacts'}, auto_run=True)
        assert CityWorker(store).run_once()

    with TestClient(app) as client:
        directory = client.get('/city/api/network', headers=headers)
        assert directory.status_code == 200
        assert [c['name'] for c in directory.json()['contacts']] == ['Existing Example']
        collect()
        directory = client.get('/city/api/network', headers=headers).json()
        assert {c['name'] for c in directory['contacts']} == {'Existing Example', 'Alex Exemple'}
        added = next(c for c in directory['contacts'] if c['name'] == 'Alex Exemple')
        assert added['source_url'] == lead['source_url']
        assert added['source_excerpt'] == lead['source_excerpt']
        report_key = 'schedule' if agent == 'networker' else 'clara'
        assert directory[report_key]['report']['count'] == 1
        collect()
        report = client.get('/city/api/network', headers=headers).json()[report_key]['report']
        assert report['count'] == 0
        assert report['duplicates'] >= 1
        assert report['duplicate_examples'] == [{
            'name': lead['name'], 'role': lead['role'], 'company': lead['company'],
            'source_url': lead['source_url'], 'reason': 'Même nom et même entreprise'}]
        assert 'doublons' in report['text']
        # A targeted assisted search can still add a new profile after the empty collection.
        selected = {'name': 'Camille Exemple', 'role': 'Rates Sales', 'company': 'Synthetic Bank',
                    'linkedin_url': 'https://www.linkedin.com/in/synthetic-camille',
                    'evidence': 'Camille Exemple Rates Sales Synthetic Bank'}
        imported = client.post('/city/api/network/assisted', headers=headers, json=selected)
        assert imported.status_code == 201
        assert imported.json()['imported'] == 1
        repeated = client.post('/city/api/network/assisted', headers=headers, json=selected)
        assert repeated.status_code == 200 and repeated.json()['duplicates'] == 1
        contacts = client.get('/city/api/network', headers=headers).json()['contacts']
        assert len(contacts) == 3
        assert next(c for c in contacts if c['name'] == selected['name'])['source_excerpt'] == selected['evidence']
        assert client.get('/city/api/network', headers={'x-test-user': 'synthetic-other'}).json()['contacts'] == []
    saved = state_store.load_user_data('synthetic-owner', 'mail_contacts')
    assert {key: saved[key] for key in before} == before
