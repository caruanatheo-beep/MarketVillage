"""Guard account budgets and make City health reflect completed work."""
from datetime import datetime, timedelta, timezone

import pytest

from internships_project import llm_usage, state_store
from internships_project.city_services import _budget_guard
from internships_project.marketdesk_city import CityError, CityStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'accounts.sqlite3')
    return CityStore(state_store.USER_DB_PATH)


def test_completion_counts_use_finished_time_and_entire_history(store):
    now = datetime.now(timezone.utc)
    created = (now - timedelta(days=10)).isoformat()
    with store.db() as db:
        db.executemany('INSERT INTO city_tasks(id,username,agent_id,task_type,description,status,created_at,finished_at) '
                       'VALUES(?,?,?,?,?,?,?,?)',
                       [(str(i), 'alice', 'market_analyst', 'test', 'Test', 'completed', created, now.isoformat())
                        for i in range(105)])
    snapshot = store.snapshot('alice')
    assert len(snapshot['tasks']) == 100
    assert snapshot['today_completed'] == snapshot['week_completed'] == 105
    assert store.snapshot('bob')['today_completed'] == 0
    mira = next(a for a in snapshot['agents'] if a['id'] == 'market_analyst')
    assert mira['health']['last_success_at'] == now.isoformat()


@pytest.mark.parametrize('cost,blocked', [('0.10', False), ('1.00', True), (None, True)])
def test_iris_budget_remains_account_scoped_and_fails_closed(store, cost, blocked):
    with llm_usage._connect() as db:
        db.execute('INSERT INTO llm_usage(username,action,model,created_at,estimated_cost_usd) VALUES(?,?,?,?,?)',
                   ('alice', 'speculative_mail', 'fixture', datetime.now(timezone.utc).isoformat(), cost))
    settings = store.get_settings('alice')
    if blocked:
        with pytest.raises(CityError): _budget_guard('alice', settings)
    else:
        _budget_guard('alice', settings)
    _budget_guard('bob', store.get_settings('bob'))


def test_reserve_cannot_cross_budget(store):
    with llm_usage._connect() as db:
        db.execute('INSERT INTO llm_usage(username,action,model,created_at,estimated_cost_usd) VALUES(?,?,?,?,?)',
                   ('alice', 'speculative_mail', 'fixture', datetime.now(timezone.utc).isoformat(), '0.95'))
    with pytest.raises(CityError): _budget_guard('alice', store.get_settings('alice'), reserve_usd=0.1)
