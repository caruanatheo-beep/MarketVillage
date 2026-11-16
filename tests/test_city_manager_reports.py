import asyncio
import json

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from internships_project import city_chat, state_store
from internships_project.city_agents import ChatDeps, build_agent
from internships_project.city_manager_reports import contacts_report, daily_report, format_contacts_report, retry_advice
from internships_project.marketdesk_city import CityStore


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'manager.sqlite3')
    return CityStore(state_store.USER_DB_PATH)


@pytest.mark.parametrize('error,category,eligible', [
    ('Délai dépassé', 'incident potentiellement temporaire', True),
    ('Temporary network timeout', 'incident potentiellement temporaire', True),
    ('Quota Codex atteint', 'limite Codex', False),
    ('Développement reporté : budget Codex quotidien atteint.', 'ancienne limite City supprimée', True),
    ('Connexion ChatGPT expirée', 'accès', False),
    ('Recherche publique indisponible : source inaccessible', 'source', False),
    ('Tests serveur en échec', 'correction nécessaire', False),
    ('Erreur non documentée', 'à examiner', False),
])
def test_retry_advice_is_conservative(error, category, eligible):
    result = retry_advice({'status': 'failed', 'error': error})
    assert (result['category'], result['eligible']) == (category, eligible)


def test_manager_cannot_bulk_retry_persistent_failure_but_can_retry_timeout(store):
    first = store.create_task('alice', 'market_analyst', 'Source problem', auto_run=True)
    assert store.claim_next()['id'] == first['id']
    store.finish(first['id'], error='Source indisponible')
    second = store.create_task('alice', 'market_analyst', 'Timeout', auto_run=True)
    assert store.claim_next()['id'] == second['id']
    store.finish(second['id'], error='Délai temporaire dépassé')
    deps = ChatDeps(username='alice', store=store, current_message='Relance les échecs')
    tool = build_agent('desk_manager', TestModel())._function_toolset.tools['resume_missions']
    async def run():
        return await tool.function_schema.call({'task_ids': [first['id'], second['id']]},
                                                RunContext(deps=deps, model=None, usage=RunUsage()))
    result = asyncio.run(run())['data']['missions']
    assert result[0]['status'] == 'refused' and 'source' in result[0]['message']
    assert result[1]['changed'] and result[1]['status'] == 'queued'
    assert store.task_detail('alice', first['id'])['status'] == 'failed'


def test_queue_reports_latest_event_heartbeat_and_account_scoped_dependency(store):
    workflow = store.create_custom_workflow('alice', 'Project', 'Dependencies', [
        {'id': 'first', 'agent_id': 'market_analyst', 'description': 'First', 'depends_on': []},
        {'id': 'next', 'agent_id': 'developer', 'operation': 'daily_questions', 'description': 'Next', 'depends_on': ['first']}])
    first, second = workflow['task_ids']
    with store.db() as db:
        db.execute("UPDATE city_tasks SET status='failed',error='Source indisponible' WHERE id=?", (first,))
    queue = store.resumable_missions('alice', 'pending')
    item = next(task for task in queue['missions'] if task['id'] == second)
    assert item['blocked_dependencies'] == [first]
    assert item['retry_advice']['category'] == 'dépendance'
    assert item['last_event']['created_at'] and item['last_event']['message']
    assert not store.resumable_missions('bob')['missions']


def test_bulk_resume_does_not_cancel_a_scheduled_quota_wait(store):
    from datetime import datetime, timedelta, timezone
    scheduled = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    task = store.create_task('alice', 'market_analyst', 'Quota wait', auto_run=True, scheduled_at=scheduled)
    with store.db() as db:
        row = db.execute('SELECT * FROM city_tasks WHERE id=?', (task['id'],)).fetchone()
        store._event(db, row, 'queued', 'Limite Codex atteinte, reprise programmée.')
    before = store.task_detail('alice', task['id'])['scheduled_at']
    deps = ChatDeps(username='alice', store=store, current_message='Reprends les missions')
    answer = asyncio.run(city_chat._resume_shortcut(deps, 'pending'))
    assert 'limite Codex' in answer and 'Reprise prévue' in answer
    assert store.task_detail('alice', task['id'])['scheduled_at'] == before


def _finish(store, agent, operation, result=None, error=None, user='alice'):
    params = {'discover_public': True} if agent == 'networker' else {'operation': operation}
    task = store.create_task(user, agent, f'{agent} task', params, auto_run=True)
    with store.db() as db:
        db.execute("UPDATE city_tasks SET status='running' WHERE id=?", (task['id'],))
    store.finish(task['id'], result=result, error=error)
    return task


def test_reports_use_saved_sources_dates_duplicates_failures_and_no_cross_account(store):
    contact = {'name': 'Test Person', 'role': 'Sales', 'company': 'Example Bank', 'source_url': 'https://example.test/person'}
    lina = _finish(store, 'networker', '', {'contacts': [contact], 'duplicates': 2, 'source': 'Source publique', 'warnings': ['Couverture partielle']})
    _finish(store, 'securities_scout', 'discover_service_contacts', {'contacts': [contact], 'duplicates': 1, 'source': 'Source Clara'})
    _finish(store, 'securities_scout', 'discover_service_contacts', error='Source inaccessible')
    _finish(store, 'prime_services_scout', 'discover_prime_services_contacts', {'contacts': [], 'duplicates': 3, 'source': 'Source Élodie'})
    _finish(store, 'networker', '', {'contacts': [{'name': 'Bob secret'}]}, user='bob')
    _finish(store, 'job_hunter', 'develop', {'integrated': True, 'plain_summary': 'Navigation corrigée',
            'server_checks': ['Tests réussis'], 'files': ['internships_project/city_chat.py'], 'commit': 'a'*40})
    _finish(store, 'internship_scout', 'refresh_internships', {'text': 'Une nouvelle offre détectée',
            'offers': [{'title': 'Stage Sales', 'company': 'Banque', 'url': 'https://example.test/job'}]})
    result = format_contacts_report(contacts_report(store, 'alice'))
    assert all(value in result for value in ['Lina', 'Clara', 'Élodie', '2 doublon', '3 doublon',
                                             'Test Person', 'https://example.test/person', 'Couverture partielle',
                                             'Dernière recherche', 'Source inaccessible', 'Résultat précédent'])
    assert 'Bob secret' not in result and f'[[mission:{lina["id"]}]]' in result
    report = daily_report(store, 'alice')
    assert all(value in report for value in ['Navigation corrigée', 'Tests réussis', 'Activation inconnue',
                                              'Une nouvelle offre détectée', 'Stage Sales', 'https://example.test/job'])
    assert 'Bob secret' not in report


def test_unrelated_recent_missions_do_not_hide_contact_discovery(store):
    discovery = _finish(store, 'securities_scout', 'discover_service_contacts',
                        {'contacts': [{'name': 'Visible contact'}]})
    with store.db() as db:
        db.execute("UPDATE city_tasks SET finished_at='2026-01-01T00:00:00+00:00' WHERE id=?", (discovery['id'],))
    for index in range(50):
        task = store.create_task('alice', 'networker', f'Unrelated {index}', {}, auto_run=True)
        with store.db() as db:
            db.execute("UPDATE city_tasks SET status='completed',finished_at=? WHERE id=?",
                       (f'2026-01-02T00:{index:02}:00+00:00', task['id']))

    clara = next(agent for agent in contacts_report(store, 'alice')['agents'] if agent['name'] == 'Clara')
    assert clara['latest']['id'] == discovery['id']
    assert not clara['today_truncated']


def test_daily_and_contact_shortcuts_never_start_codex(store, monkeypatch):
    async def no_codex(*args):
        pytest.fail('A factual report must not start Codex')
    monkeypatch.setattr(city_chat, '_run_codex_turn', no_codex)
    async def run(intent):
        return [json.loads(item) async for item in city_chat.stream_chat(store, 'alice', 'desk_manager', 'Bilan', {'intent': intent})]
    for intent in ('daily_summary', 'contacts_report'):
        events = asyncio.run(run(intent))
        assert any(e['type'] == 'done' for e in events)
        assert not any(e['type'] == 'error' for e in events)
