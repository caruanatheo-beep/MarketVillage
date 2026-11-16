import json
from pathlib import Path

import pytest

from internships_project import city_coding, network_discovery as network, state_store
from internships_project.marketdesk_city import CityStore, CityError


@pytest.mark.parametrize('scope,company,role', [
    ({'markets': True}, 'BNP Paribas', 'FX Sales'),
    ({}, 'CACEIS', 'Securities Lending Sales'),
    ({'prime_services': True}, 'BNP Paribas', 'Prime Brokerage Sales'),
])
def test_candidate_pool_keeps_valid_tail_and_profiles_omitted_by_model(monkeypatch, scope, company, role):
    for name, value in [('codex_binary', lambda: 'codex'), ('codex_environment', lambda: {}),
                        ('require_chatgpt', lambda *a: None),
                        ('require_daily_codex_budget', lambda *a, **k: None),
                        ('record_daily_codex_usage', lambda *a: None)]:
        monkeypatch.setattr(city_coding, name, value)
    monkeypatch.setattr(network, '_prime_employer_evidence', lambda url: '')
    def execute(command, directory, prompt, env, **kwargs):
        queries = json.loads(prompt.split('Plan de requêtes : ')[-1])
        assert len(queries) == len(set(queries)) == 8
        records = [dict(name=name, role=role, company=company,
                        source_url=f'https://www.linkedin.com/in/{key}',
                        location_source_url=f'https://www.linkedin.com/in/{key}')
                   for name, key in [('Invented Person', 'missing'), ('Other Invented', 'missing'),
                                     ('Alice Martin', 'alice')]]
        Path(command[command.index('--output-last-message')+1]).write_text(json.dumps({'contacts': records}))
        return [{'type': 'item.completed', 'item': {'type': 'web_search', 'results': [
            dict(url=f'https://www.linkedin.com/in/{key}', title=f'{name} - {role} - {company}',
                 snippet=f'{name}, {role} at {company}, based in Paris.')
            for name, key in [('Alice Martin', 'alice'), ('Luc Bernard', 'luc')]
        ]}}]
    monkeypatch.setattr(city_coding, '_execute', execute)
    found = network._search_service_contacts_with_codex(2, **scope)
    assert [lead['name'] for lead in found] == ['Alice Martin', 'Luc Bernard']
    found = network._search_service_contacts_with_codex(2, existing=found, **scope)
    assert found == []


def test_manual_public_biography_is_supported_and_stays_account_private(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    CityStore(state_store.USER_DB_PATH)
    payload = dict(name='Alice Martin', role='FX Sales', company='BNP Paribas',
                   source_url='https://group.bnpparibas/team/alice',
                   evidence='Alice Martin, FX Sales at BNP Paribas, based in Paris.')
    assert network.import_assisted_contact('alice', payload)['imported'] == 1
    assert network.import_assisted_contact('alice', payload)['duplicates'] == 1
    saved = network.list_contacts('alice')[0]
    assert saved['source_url'] == payload['source_url'] and not saved['linkedin_url']
    assert network.list_contacts('bob') == []
    with pytest.raises(CityError):
        network.import_assisted_contact('alice', {**payload, 'source_url': 'javascript:alert(1)'})
    with pytest.raises(CityError):
        network.import_assisted_contact('alice', {**payload, 'evidence': 'Unrelated person'})
