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


def test_clara_uses_bounded_codex_topup_when_public_engines_fail(tmp_path, monkeypatch):
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

    assert report['count'] == 1 and len(calls) == 2
    assert 'passage 2' in calls[1][1] and 'Luc Bernard' in calls[1][1]
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
    monkeypatch.setattr(city_coding, 'codex_usage_percent', lambda *_args: 100.0)
    monkeypatch.setattr(city_coding, '_execute', lambda *_args, **_kwargs:
                        pytest.fail('Codex must not run at the quota stop'))

    with pytest.raises(CityError, match='quota Codex hebdomadaire épuisé'):
        network.discover_service_contacts('alice')


def test_elodie_parses_public_bank_biographies_with_verified_paris_location():
    results = [{'url': 'https://group.bnpparibas/en/news/prime-services-team',
                'title': 'Alice Martin - Prime Brokerage Sales - BNP Paribas',
                'snippet': 'Alice Martin, Prime Brokerage Sales at BNP Paribas in Paris.'},
               {'url': 'https://group.bnpparibas/en/news/prime-services-team',
                'title': 'London profile',
                'snippet': 'Bob Martin, Repo Sales at BNP Paribas in London.'}]
    found = network._prime_contacts_from_results(results, 'BNP Paris Prime Brokerage', 'Bing RSS')
    assert len(found) == 1
    assert found[0]['name'] == 'Alice Martin'
    assert found[0]['company'] == 'BNP Paribas'
    assert found[0]['sales_priority'] is True
    assert found[0]['origin'] == 'prime_services_public_search'


def test_elodie_prime_articles_are_included_in_the_public_search_parser():
    results = [{'url': 'https://group.bnpparibas/en/news/prime-services-team',
                'title': 'Alice Martin — Prime Brokerage Sales — BNP Paribas',
                'snippet': 'Alice Martin, Prime Brokerage Sales at BNP Paribas in Paris.'}]
    found = network._contacts_from_results(results, 'BNP Paris Prime Brokerage', 'Bing RSS',
                                          prime_services=True)
    assert len(found) == 1
    assert found[0]['name'] == 'Alice Martin'
    assert found[0]['origin'] == 'prime_services_public_search'


def test_elodie_saves_new_profiles_and_excludes_shared_contact_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(network, '_search_service_contacts_with_codex', lambda *args, **kwargs: [])
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    store.ensure_agents('alice')
    network.save_leads('alice', [{'name': 'Camille Dupont', 'role': 'Prime Services Sales',
                                 'company': 'CACEIS', 'location': 'Paris, France',
                                 'source_url': 'https://example.org/camille',
                                 'source_excerpt': 'Camille Dupont Prime Services Sales CACEIS Paris',
                                 'origin': 'lina_public_search'}])
    candidates = [
        {'name': 'Camille Dupont', 'role': 'Prime Services Sales', 'company': 'CACEIS',
         'location': 'Paris, France', 'linkedin_url': 'https://www.linkedin.com/in/camille-dupont',
         'source_url': 'https://www.linkedin.com/in/camille-dupont', 'source_title': 'Camille Dupont - Prime Services Sales - CACEIS',
         'source_excerpt': 'Camille Dupont Prime Services Sales at CACEIS Paris'},
        {'name': 'Luc Bernard', 'role': 'Securities Lending Sales', 'company': 'CACEIS',
         'location': 'Paris, France', 'linkedin_url': 'https://www.linkedin.com/in/luc-bernard',
         'source_url': 'https://www.linkedin.com/in/luc-bernard', 'source_title': 'Luc Bernard - Securities Lending Sales - CACEIS',
         'source_excerpt': 'Luc Bernard Securities Lending Sales at CACEIS Paris'},
        {'name': 'Eva Martin', 'role': 'Clearing Relationship Manager', 'company': 'BNP Paribas',
         'location': 'Paris, France', 'linkedin_url': 'https://www.linkedin.com/in/eva-martin',
         'source_url': 'https://www.linkedin.com/in/eva-martin', 'source_title': 'Eva Martin - Clearing Relationship Manager - BNP Paribas',
         'source_excerpt': 'Eva Martin Clearing Relationship Manager at BNP Paribas Paris'},
        {'name': 'Out of Scope', 'role': 'Repo Sales', 'company': 'CACEIS',
         'location': 'London, UK', 'linkedin_url': 'https://www.linkedin.com/in/out-of-scope',
         'source_url': 'https://www.linkedin.com/in/out-of-scope', 'source_title': 'Out of Scope - Repo Sales - CACEIS',
         'source_excerpt': 'Out of Scope Repo Sales at CACEIS London'},
    ]
    calls = []
    def search(query, *, service_roles=False, prime_services=False):
        calls.append(prime_services)
        assert prime_services and not service_roles
        return candidates
    monkeypatch.setattr(network, 'search_public', search)
    report = network.discover_prime_services_contacts('alice')
    assert report['count'] == 2
    assert report['duplicates'] >= 1
    assert len(network.list_contacts('alice')) == 3
    assert {c['name'] for c in network.list_contacts('alice')} == {'Camille Dupont', 'Luc Bernard', 'Eva Martin'}
    assert all(c['origin'] == 'prime_services_public_search' for c in network.list_contacts('alice') if c['name'] != 'Camille Dupont')
    assert calls and all(calls)


def test_elodie_manual_and_scheduled_searches_execute_through_the_worker(tmp_path, monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    store.ensure_agents('alice')
    calls = []
    def discover(username):
        calls.append(username)
        return {'count': 0, 'contacts': [], 'text': 'Recherche terminee.'}
    monkeypatch.setattr(network, 'discover_prime_services_contacts', discover)
    store.enqueue_specialist_schedules(datetime(2026, 11, 9, 9, tzinfo=ZoneInfo('Europe/Paris')))
    with store.db() as db:
        db.execute("UPDATE city_tasks SET status='cancelled' WHERE agent_id!='prime_services_scout'")
    assert CityWorker(store).run_once()
    assert store.prime_services_scout_status('alice')['status'] == 'completed'
    task = store.create_task('alice', 'prime_services_scout', 'Recherche Prime Services',
                             {'operation': 'discover_prime_services_contacts'}, auto_run=True)
    assert task['status'] == 'queued'
    assert CityWorker(store).run_once()
    assert calls == ['alice', 'alice']
    assert store.prime_services_scout_status('bob')['status'] == 'idle'


def test_elodie_prioritizes_ten_sales_and_rejects_unrelated_or_past_roles(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    CityStore(state_store.USER_DB_PATH)
    def profile(name, role, bank='CACEIS'):
        return {'name': name, 'role': role, 'company': bank, 'location': 'Paris',
                'source_url': 'https://example.org/' + name.replace(' ', '-'),
                'source_excerpt': f'{name}, {role} at {bank} in Paris. Former employer: CACEIS.'}
    sales = [profile('Alice '+surname, 'Securities Lending Sales') for surname in
             ['Martin','Dupont','Moreau','Bernard','Petit','Roux','Laurent','Michel','Simon','Robert','Garcia']]
    leads = [profile('Desk Leader', 'Head of Prime Services'),
             profile('Outside Bank', 'Repo Sales', 'Barclays'),
             profile('Past Role', 'Former Prime Brokerage Sales'),
             profile('Other Role', 'Prime Services Software Engineer'), *sales]
    monkeypatch.setattr(network, 'search_public', lambda *a, **kw: leads)
    report = network.discover_prime_services_contacts('alice')
    assert report['count'] == 10
    assert all(c['name'].startswith('Alice ') and c['sales_priority'] for c in report['contacts'])
    assert network.contact_focus({**leads[0], 'origin': 'prime_services_public_search'})['sales_priority'] is False


def test_elodie_shared_save_deduplicates_bank_aliases_in_both_directions(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    source = {'name': 'Alice Martin', 'role': 'Prime Brokerage Sales', 'company': 'BNP Paribas CIB',
              'source_url': 'https://example.org/alice', 'origin': 'lina_public_search'}
    assert len(network.save_leads('alice', [source])[0]) == 1
    prime = {**source, 'company': 'BNP Paribas', 'origin': 'prime_services_public_search'}
    assert network.save_leads('alice', [prime]) == ([], 1)
    assert len(network.save_leads('bob', [prime])[0]) == 1
    assert network.save_leads('bob', [source]) == ([], 1)
