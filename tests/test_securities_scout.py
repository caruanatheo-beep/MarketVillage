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
    task = store.create_task('alice', 'securities_scout', 'Chercher des contacts en services titres',
                             {'operation': 'discover_service_contacts'}, auto_run=True)
    assert CityWorker(store).run_once()
    done = next(row for row in store.snapshot('alice')['tasks'] if row['id'] == task['id'])
    assert done['status'] == 'completed' and done['result']['count'] == 2
    assert len(queries) == 9
    contacts = network.list_contacts('alice')
    assert {row['company'] for row in contacts} == {'BNP Paribas Securities Services', 'CACEIS'}
    assert all(row['origin'] == 'securities_public_search' for row in contacts)
    assert store.securities_scout_status('alice')['status'] == 'completed'
    assert store.securities_scout_status('bob')['status'] == 'idle'
    assert all(row['verification_status'] == 'À vérifier' for row in contacts)
    assert network.list_contacts('bob') == []

    second = network.discover_service_contacts('alice')
    assert second['count'] == 0 and second['duplicates'] == 2
