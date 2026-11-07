"""Clara researches public securities-services profiles into the shared directory."""
from internships_project import network_discovery as network, state_store
from internships_project.city_specialists import DEFAULT_OPERATIONS
from internships_project.marketdesk_city import AGENT_BY_ID, CityStore, CityWorker


def test_service_roles_are_accepted_only_for_the_specialized_search():
    page = ('<a class="result__a" href="https://www.linkedin.com/in/jeanne-martin">'
            'Jeanne Martin – Collateral Manager – BP2S</a>'
            '<span class="result__snippet">Jeanne Martin · Collateral Manager chez BP2S</span>')
    assert network.parse_results(page, 'BP2S') == []
    found = network.parse_results(page, 'BP2S', service_roles=True)
    assert len(found) == 1 and found[0]['company'] == 'BP2S'


def test_clara_reads_named_roles_from_official_public_articles_only():
    results = [
        {'url': 'https://www.caceis.com/fr/actualites/market-solutions/',
         'title': 'Market Solutions | CACEIS',
         'snippet': 'Donia Rouigueb, Head of Sales Securities Finance and Repo at CACEIS, explains the service.'},
        {'url': 'https://www.euroclear.com/campaigns/en/biographies/marije-verhelst.html',
         'title': 'Marije Verhelst - Euroclear Bank',
         'snippet': 'Marije Verhelst is Head of Collateral Management at Euroclear Bank.'},
        {'url': 'https://unrelated.example/profile', 'title': 'John Smith - Other Bank',
         'snippet': 'John Smith, Head of Collateral Management at Other Bank.'},
    ]
    found = network._contacts_from_results(results, 'collateral', 'Bing RSS', service_roles=True)
    assert {lead['name'] for lead in found} == {'Donia Rouigueb', 'Marije Verhelst'}
    assert all(lead['source_type'] == 'Biographie ou article public' for lead in found)
    assert all(lead['linkedin_url'] == '' for lead in found)
    assert network._contacts_from_results(results, 'collateral', 'Bing RSS') == []


def test_clara_uses_rss_when_public_html_has_no_usable_people(monkeypatch):
    calls = []
    rss = ('<rss><channel><item><title>Donia Rouigueb - CACEIS</title>'
           '<description>Donia Rouigueb, Head of Sales Securities Finance and Repo at CACEIS.</description>'
           '<link>https://www.caceis.com/fr/actualites/market-solutions/</link>'
           '</item></channel></rss>')
    def response(url, params):
        calls.append(url)
        return ('<a class="result__a" href="https://example.org/irrelevant">Other</a>'
                if url == network.SEARCH_URL else rss)
    monkeypatch.setattr(network, '_search_response', response)
    found = network.search_public('CACEIS repo', service_roles=True)
    assert len(found) == 1 and found[0]['name'] == 'Donia Rouigueb'
    assert calls == [network.SEARCH_URL, 'https://www.bing.com/search']


def test_clara_runs_on_request_and_deduplicates_bp2s_in_shared_contacts(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    assert AGENT_BY_ID['securities_scout']['name'] == 'Clara'
    assert DEFAULT_OPERATIONS['securities_scout'] == 'discover_service_contacts'
    assert len(network.SECURITIES_ENTITIES) == 9
    queries = []

    def search(query, *, service_roles=False):
        queries.append(query)
        assert service_roles
        if 'BNP Paribas Securities Services' in query:
            return [{'name': 'Jeanne Martin', 'role': 'Collateral Manager', 'company': 'BP2S',
                     'linkedin_url': 'https://www.linkedin.com/in/jeanne-martin',
                     'source_url': 'https://www.linkedin.com/in/jeanne-martin',
                     'source_excerpt': 'Jeanne Martin Collateral Manager BP2S'}]
        if 'CACEIS' in query:
            return [{'name': 'Luc Bernard', 'role': 'Securities Lending Sales', 'company': 'CACEIS',
                     'linkedin_url': 'https://www.linkedin.com/in/luc-bernard',
                     'source_url': 'https://www.linkedin.com/in/luc-bernard',
                     'source_excerpt': 'Luc Bernard Securities Lending Sales CACEIS'},
                    {'name': 'Autre Personne', 'role': 'Collateral Manager', 'company': 'Other Bank',
                     'linkedin_url': 'https://www.linkedin.com/in/other',
                     'source_url': 'https://www.linkedin.com/in/other'}]
        return []

    monkeypatch.setattr(network, 'search_public', search)
    monkeypatch.setattr(network, '_search_service_contacts_with_codex', lambda target, **_kwargs: [])
    task = store.create_task('alice', 'securities_scout', 'Chercher des contacts en services titres',
                             {'operation': 'discover_service_contacts'}, auto_run=True)
    assert CityWorker(store).run_once()
    done = next(row for row in store.snapshot('alice')['tasks'] if row['id'] == task['id'])
    assert done['status'] == 'completed' and done['result']['count'] == 2
    assert len(queries) == 14
    assert any('site:icmagroup.org' in query for query in queries)
    contacts = network.list_contacts('alice')
    assert {row['company'] for row in contacts} == {'BNP Paribas Securities Services', 'CACEIS'}
    assert all(row['origin'] == 'securities_public_search' for row in contacts)
    assert store.securities_scout_status('alice')['status'] == 'completed'
    assert store.securities_scout_status('bob')['status'] == 'idle'
    assert all(row['verification_status'] == 'À vérifier' for row in contacts)
    assert network.list_contacts('bob') == []

    second = network.discover_service_contacts('alice')
    assert second['count'] == 0 and second['duplicates'] >= 2
    assert any('site:linkedin.com/in/' in query for query in queries)
    assert any('site:' in query and 'linkedin.com' not in query for query in queries)


def test_clara_without_summary_keeps_network_directory_available(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from internships_project.city_routes import add_city_routes

    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    store.create_task('alice', 'securities_scout', 'Recherche en attente',
                      {'operation': 'discover_service_contacts'}, auto_run=False)
    app = FastAPI()
    add_city_routes(app, lambda request: request.headers.get('x-test-user'), store, CityWorker(store))
    with TestClient(app) as client:
        response = client.get('/city/api/network', headers={'x-test-user': 'alice'})
    assert response.status_code == 200
    assert response.json()['clara']['summary'] == ''


def test_clara_can_be_launched_more_than_five_times_in_one_day(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    for _ in range(6):
        task = store.create_task('alice', 'securities_scout', 'Rechercher des contacts',
                                 {'operation': 'discover_service_contacts'}, auto_run=True)
        claimed = store.claim_next()
        assert claimed['id'] == task['id']
        store.finish(task['id'], result={'count': 0, 'contacts': []})


def test_clara_can_queue_behind_two_programmers(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    for agent in ('city_ui_engineer', 'quality_engineer'):
        store.create_task('alice', agent, 'Améliorer le code', {'operation': 'develop'}, auto_run=True)
    clara = store.create_task('alice', 'securities_scout', 'Rechercher des contacts',
                              {'operation': 'discover_service_contacts'}, auto_run=True)
    assert clara['status'] == 'queued'


def test_clara_uses_one_codex_search_when_public_engines_fail(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from internships_project import city_coding

    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    monkeypatch.setattr(network, 'search_public', lambda *_args, **_kwargs:
                        (_ for _ in ()).throw(ValueError('Source bloquée')))
    monkeypatch.setattr(city_coding, 'codex_binary', lambda: 'codex')
    monkeypatch.setattr(city_coding, 'codex_environment', lambda: {'PATH': 'safe'})
    monkeypatch.setattr(city_coding, 'require_chatgpt', lambda *_args: None)
    monkeypatch.setattr(city_coding, 'codex_usage_percent', lambda *_args: 20)
    calls = []
    url = 'https://example.org/caceis-speakers'
    network.save_leads('alice', [{'name': 'Eva Laurent', 'role': 'Collateral Manager',
                                  'company': 'CACEIS', 'source_url': url,
                                  'origin': 'securities_public_search'}])
    def execute(command, directory, prompt, env, *, timeout_seconds):
        calls.append((command, prompt, env, timeout_seconds))
        Path(command[command.index('--output-last-message')+1]).write_text(json.dumps({'contacts': [
            {'name': 'Luc Bernard', 'role': 'Securities Lending Sales', 'company': 'CACEIS', 'source_url': url},
            {'name': 'Eva Laurent', 'role': 'Collateral Manager', 'company': 'CACEIS', 'source_url': url},
            {'name': 'Invented Person', 'role': 'Collateral Manager', 'company': 'CACEIS', 'source_url': url},
        ]}))
        return [{'type': 'item.completed', 'item': {'type': 'web_search', 'results': [
            {'url': url, 'title': 'CACEIS speakers',
             'snippet': 'Luc Bernard, Securities Lending Sales at CACEIS. Eva Laurent, Collateral Manager at CACEIS.'}]}}]
    monkeypatch.setattr(city_coding, '_execute', execute)

    report = network.discover_service_contacts('alice')

    assert report['count'] == 1 and len(calls) == 1
    assert '--search' in calls[0][0] and calls[0][3] == 180
    assert 'Eva Laurent' in calls[0][1]
    assert 'OPENAI_API_KEY' not in calls[0][2]
    assert len(network.list_contacts('alice')) == 2
    assert network.list_contacts('bob') == []


def test_clara_uses_codex_when_public_engines_return_no_people(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    monkeypatch.setattr(network, 'search_public', lambda *_args, **_kwargs: [])
    calls = []
    def fallback(target, **kwargs):
        calls.append((target, kwargs))
        return [{'name': 'Luc Bernard', 'role': 'Securities Lending Sales',
                 'company': 'CACEIS', 'source_url': 'https://example.org/speakers',
                 'source_excerpt': 'Luc Bernard, Securities Lending Sales at CACEIS.'}]
    monkeypatch.setattr(network, '_search_service_contacts_with_codex', fallback)
    report = network.discover_service_contacts('alice')
    assert report['count'] == 1 and calls[0][0] == 10
    assert calls[0][1]['existing'] == []
    assert 'CACEIS' in calls[0][1]['priority_entities']
    assert network.list_contacts('alice')[0]['source_url'] == 'https://example.org/speakers'


def test_clara_codex_fallback_obeys_subscription_stop(tmp_path, monkeypatch):
    from internships_project import city_coding
    from internships_project.marketdesk_city import CityError
    import pytest

    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    monkeypatch.setattr(network, 'search_public', lambda *_args, **_kwargs:
                        (_ for _ in ()).throw(ValueError('Source bloquée')))
    monkeypatch.setattr(city_coding, 'codex_binary', lambda: 'codex')
    monkeypatch.setattr(city_coding, 'codex_environment', lambda: {})
    monkeypatch.setattr(city_coding, 'require_chatgpt', lambda *_args: None)
    usage = [60.0]
    monkeypatch.setattr(city_coding, 'codex_usage_percent', lambda *_args: usage[0])
    before = city_coding.require_daily_codex_budget('codex', {})
    usage[0] += city_coding.CODEX_DAILY_USAGE_PERCENT
    city_coding.record_daily_codex_usage('codex', {}, before)
    monkeypatch.setattr(city_coding, '_execute', lambda *_args, **_kwargs:
                        pytest.fail('Codex must not run at the quota stop'))

    with pytest.raises(CityError, match='budget Codex quotidien'):
        network.discover_service_contacts('alice')
