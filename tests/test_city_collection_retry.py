"""Public synchronization is independent of local collection contention."""
from datetime import datetime, timezone

import pytest

from internships_project import city_offers, internships, state_store
from internships_project.marketdesk_city import CityStore, CityWorker


@pytest.mark.parametrize('agent_id', ['desk_manager', 'networker', 'internship_scout'])
def test_local_collector_cannot_block_public_sync(tmp_path, monkeypatch, agent_id):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    task = store.create_task('alice', agent_id, 'Actualiser les stages', {'operation': 'refresh_internships'})
    monkeypatch.setattr(internships, 'opportunities_loading', lambda: True)
    monkeypatch.setattr(internships, 'refresh_opportunities', lambda **_: pytest.fail('No employer collection'))
    monkeypatch.setattr(city_offers, 'load_catalogue', lambda **_: city_offers.Catalogue(
        [], [], datetime.now(timezone.utc), 'public'))
    assert CityWorker(store).run_once()
    detail = store.task_detail('alice', task['id'])
    assert detail['status'] == 'completed'
    assert detail['result']['catalog_source'] == 'public'
    assert not CityWorker(store).run_once()


def test_catalogue_unexpected_error_is_sanitized(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    task = store.create_task('alice', 'internship_scout', 'Stages', {'operation': 'refresh_internships'})
    def broken(**_):
        raise RuntimeError('private detail')
    monkeypatch.setattr(city_offers, 'load_catalogue', broken)
    assert CityWorker(store).run_once()
    detail = store.task_detail('alice', task['id'])
    assert detail['status'] == 'failed'
    assert detail['error'] == 'Erreur de mission (RuntimeError).'
    assert 'private detail' not in str(detail)


@pytest.mark.parametrize('failure', [TimeoutError('temporary timeout'), ConnectionError('temporary disconnect')])
def test_transient_agent_network_failure_is_rescheduled(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    task = store.create_task('alice', 'market_analyst', 'Analyse publique',
                             {'discover_public': True})

    def unavailable(*_args, **_kwargs):
        raise failure

    from internships_project import city_services
    monkeypatch.setattr(city_services, 'run_agent', unavailable)
    assert CityWorker(store).run_once()
    detail = store.task_detail('alice', task['id'])
    assert detail['status'] == 'queued'
    assert detail['error'] is None
    assert detail['scheduled_at']


@pytest.mark.parametrize('failure_name', ['ConnectError', 'ReadTimeout'])
def test_httpx_transport_failure_is_rescheduled(tmp_path, monkeypatch, failure_name):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    task = store.create_task('alice', 'market_analyst', 'Analyse publique', {'discover_public': True})
    failure_type = type(failure_name, (Exception,), {'__module__': 'httpx._exceptions'})
    from internships_project import city_services
    monkeypatch.setattr(city_services, 'run_agent', lambda *_args, **_kwargs: (_ for _ in ()).throw(
        failure_type('temporary transport failure')))

    assert CityWorker(store).run_once()
    detail = store.task_detail('alice', task['id'])
    assert detail['status'] == 'queued'
    assert detail['error'] is None
    assert detail['scheduled_at']
