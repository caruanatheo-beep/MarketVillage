import asyncio
import json
from datetime import datetime, timezone

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from internships_project import marketdesk_city as city, state_store
from internships_project.city_agents import ChatDeps, build_agent


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'accounts.sqlite3')
    return city.CityStore(state_store.USER_DB_PATH)


def complete(store, description, result=None, error=''):
    task = store.create_task('alice', 'job_hunter', description, {'operation': 'develop'})
    store.claim_next()
    store.finish(task['id'], result=result, error=error)
    return task['id']


def test_report_separates_delivery_analysis_failure_and_queue(store):
    delivered = complete(store, 'Corriger les dates', {'integrated': True, 'plain_summary': 'Les dates de début sont lisibles.',
        'files': ['internships_project/internships.py'], 'commit': 'abc123',
        'server_checks': ['tests/test_dates.py'], 'checks': [{'command': 'git status', 'exit_code': 0}],
        'limitations': 'À vérifier sur les futures annonces.'})
    analysis = complete(store, 'Analyser les cartes', {'integrated': False, 'plain_summary': 'La correction existe déjà.',
        'already_present': True, 'files': []})
    failed = complete(store, 'Vérifier le filtre', error='Tests serveur en échec.')
    queued = store.create_task('alice', 'city_ui_engineer', 'Améliorer les onglets', {'operation': 'develop'})
    store.claim_next()
    store.defer_coding(queued['id'], 'Reprise prévue après libération du dépôt.')
    store.active_revision = 'older'
    store.active_commits = set()
    report = store.daily_coding_changes('alice')
    assert [item['id'] for item in report['changes']] == [delivered]
    assert report['changes'][0]['server_checks'] == ['tests/test_dates.py']
    assert report['changes'][0]['live'] is None
    assert report['changes'][0]['limitations'].startswith('À vérifier')
    assert [item['id'] for item in report['not_integrated']] == [analysis]
    assert report['not_integrated'][0]['already_present']
    assert [item['id'] for item in report['blocked']] == [failed]
    assert report['blocked'][0]['error'] == 'Tests serveur en échec.'
    assert [item['id'] for item in report['active']] == [queued['id']]
    assert 'Reprise prévue' in report['active'][0]['last_event']['message']
    assert store.coding_history('alice')['report']['count'] == 1
    for section in ('changes', 'not_integrated', 'blocked', 'active'):
        assert store.daily_coding_changes('bob')[section] == []


def test_paris_day_and_old_active_tasks_remain_visible(store, monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 9, 0, 30, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(city, 'datetime', Clock)
    finished = complete(store, 'Mission ancienne enfin intégrée', {'integrated': True, 'plain_summary': 'Corrigé.'})
    queued = store.create_task('alice', 'city_ui_engineer', 'Ancienne mission en attente', {'operation': 'develop'})
    with store.db() as db:
        db.execute("UPDATE city_tasks SET created_at='2026-01-01T00:00:00+00:00' WHERE id IN (?,?)", (finished, queued['id']))
        db.execute("UPDATE city_tasks SET finished_at='2026-11-08T23:10:00+00:00' WHERE id=?", (finished,))
    report = store.daily_coding_changes('alice')
    assert report['date'] == '2026-11-09'
    assert report['count'] == 1
    assert report['active'][0]['id'] == queued['id']


def test_manager_can_read_complete_sections_without_raw_json_truncation(store):
    for index in range(5):
        complete(store, f'Corriger la carte {index}', {'integrated': True, 'plain_summary': 'Explication précise. ' * 300,
            'server_checks': ['tests/test_cards.py']})
    complete(store, 'Vérification échouée', error='Test ciblé en échec')

    async def scenario():
        agent = build_agent('desk_manager', TestModel())
        tool = agent._function_toolset.tools['read_daily_coding_changes']
        deps = ChatDeps(username='alice', store=store)
        ctx = RunContext(deps=deps, model=TestModel(), usage=RunUsage(), tool_name='read_daily_coding_changes')
        async def read(args):
            return await tool.function_schema.call(tool.function_schema.validator.validate_python(args), ctx)
        overview = await read({})
        assert overview['status'] == 'completed'
        assert overview['data']['totals']['changes'] == 5
        assert overview['data']['totals']['blocked'] == 1
        assert overview['data']['blocked'][0]['error'] == 'Test ciblé en échec'
        assert 'Changements intégrés (5)' in overview['data']['text']
        assert 'Échecs et annulations (1)' in overview['data']['text']
        assert deps.coding_report['count'] == 5
        first = (await read({'section': 'changes', 'page': 1}))['data']
        second = (await read({'section': 'changes', 'page': 2}))['data']
        assert 'truncated' not in first and 'truncated' not in second
        ids = [item['id'] for item in first['changes'] + second['changes']]
        assert len(ids) == len(set(ids)) == 5
        assert all(call['status'] == 'completed' for call in deps.calls)
    asyncio.run(scenario())


@pytest.mark.parametrize('meter_available', [True, False])
def test_budget_bypass_never_fails_after_codex_or_before_preparation(store, monkeypatch, meter_available):
    from internships_project import city_coding as coding
    def usage(*_):
        if not meter_available:
            raise city.CityError('Quota indisponible')
        return 20.0
    monkeypatch.setattr(coding, 'codex_usage_percent', usage)
    before = coding.require_daily_codex_budget('fixture', {})
    coding.record_daily_codex_usage('fixture', {}, before)
    coding.release_unused_codex_reservation(before)
    with store.db() as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='city_codex_agent_usage'").fetchone() is None


def test_codex_transport_reads_report_and_returns_final_answer(store, monkeypatch):
    from internships_project import city_chat
    complete(store, 'Corriger les dates', {'integrated': True, 'plain_summary': 'Dates corrigées.'})
    monkeypatch.setattr(city_chat, 'codex_binary', lambda: 'fixture-codex')
    monkeypatch.setattr(city_chat, 'require_chatgpt', lambda *_: None)
    written = []
    class Input:
        def write(self, data):
            written.append(json.loads(data))
        async def drain(self):
            pass
    class Process:
        stdin = Input()
        stderr = None
        returncode = None
        def terminate(self):
            self.returncode = 0
        async def wait(self):
            return 0
    async def scenario():
        process = Process()
        process.stdout = asyncio.StreamReader()
        for event in [
            {'id': 1, 'result': {}},
            {'id': 2, 'result': {'thread': {'id': 'preview-thread'}}},
            {'id': 3, 'result': {}},
            {'id': 'report-call', 'method': 'item/tool/call', 'params': {'tool': 'read_daily_coding_changes', 'arguments': {}}},
            {'id': 'report-again', 'method': 'item/tool/call', 'params': {'tool': 'read_daily_coding_changes', 'arguments': {'section': 'overview', 'page': 1}}},
            {'method': 'item/agentMessage/delta', 'params': {'itemId': 'intro', 'delta': 'Je consulte le bilan.'}},
            {'method': 'item/completed', 'params': {'item': {'type': 'agentMessage', 'id': 'intro', 'text': 'Je consulte le bilan.'}}},
            {'method': 'item/completed', 'params': {'item': {'type': 'agentMessage', 'id': 'final', 'text': 'Jules a corrigé les dates.'}}},
            {'method': 'turn/completed', 'params': {'turn': {'status': 'completed'}}},
        ]:
            process.stdout.feed_data((json.dumps(event)+'\n').encode())
        async def spawn(*command, **_):
            assert command[:4] == ('fixture-codex', 'app-server', '--listen', 'stdio://')
            assert 'forced_login_method="chatgpt"' in command
            assert ('--disable', 'apps', '--disable', 'plugins') == command[4:8]
            return process
        monkeypatch.setattr(city_chat.asyncio, 'create_subprocess_exec', spawn)
        deps = ChatDeps(username='alice', store=store)
        answer = await city_chat._run_codex_turn(deps, 'Bilan du code', deps.events, 10)
        assert answer == 'Je consulte le bilan.\n\nJules a corrigé les dates.'
        response = next(item for item in written if item.get('id') == 'report-call')
        data = json.loads(response['result']['contentItems'][0]['text'])['data']
        assert data['totals']['changes'] == 1
        assert data['changes'][0]['summary'] == 'Dates corrigées.'
        repeated = next(item for item in written if item.get('id') == 'report-again')
        assert repeated['result'] == response['result']
        assert len(deps.calls) == 1
        assert process.returncode == 0
    asyncio.run(scenario())


def test_report_button_is_immediate_scoped_and_persisted(store, monkeypatch):
    from internships_project import city_chat
    complete(store, 'Dates', {'integrated': True, 'plain_summary': 'Dates corrigées.', 'server_checks': ['test_dates: passed']})
    complete(store, 'Analyse', {'integrated': False, 'plain_summary': 'Déjà présent.'})
    complete(store, 'Tests', error='Vérification échouée.')
    queued = store.create_task('alice', 'city_ui_engineer', 'Améliorer les onglets', {'operation': 'develop'})
    async def forbidden(*args):
        pytest.fail('The report button must not start Codex')
    monkeypatch.setattr(city_chat, '_run_codex_turn', forbidden)
    async def scenario():
        for username in ('alice', 'bob'):
            events = [json.loads(event) async for event in city_chat.stream_chat(
                store, username, 'desk_manager', 'Bilan', {'intent': 'development_report'})]
            assert [e['type'] for e in events] == ['status', 'tool', 'delta', 'done']
            answer = events[2]['text']
            assert ('Dates corrigées.' in answer) == (username == 'alice')
            assert events[-1]['model'] == 'Bilan enregistré · City'
            history = store.chat_history(username, 'desk_manager', 2)
            assert history[-1]['content'] == answer
            if username == 'alice':
                for text in ('test_dates: passed', 'Terminés sans intégration (1)',
                             'Échecs et annulations (1)', 'En cours et en attente (1)', 'Activation inconnue.'):
                    assert text in answer
        with store.db() as db:
            assert db.execute('SELECT status FROM city_tasks WHERE id=?', (queued['id'],)).fetchone()[0] == 'queued'
    asyncio.run(scenario())


def test_large_report_keeps_every_category_and_stays_bounded():
    from internships_project.city_development_report import format_coding_report
    row = dict(agent='Jules', summary='Résumé vérifié. ' * 100, description='Travail demandé. ' * 100,
               error='Erreur détaillée. ' * 100, status='queued', server_checks=['Test réussi. ' * 100],
               limitations='Limite réelle. ' * 100, live=None)
    report = dict(date='2026-11-09', overview='Bilan volumineux.', **{
        key: [dict(row) for _ in range(100)] for key in ('changes','not_integrated','blocked','active')})
    for limit in (4500, 9000):
        text = format_coding_report(report, max_chars=limit)
        assert len(text) <= limit
        for title in ('Changements intégrés', 'Terminés sans intégration', 'Échecs et annulations', 'En cours et en attente'):
            assert title + ' (100)' in text
        assert text.count('autre(s) résultat(s)') == 4


@pytest.mark.parametrize('failure', [TimeoutError, city.CityError])
def test_saved_report_survives_model_failure_and_replaces_partial_text(store, monkeypatch, failure):
    from internships_project import city_chat
    complete(store, 'Dates', {'integrated': True, 'plain_summary': 'Dates corrigées.'})
    async def stalled(deps, message, queue, timeout):
        tool = build_agent('desk_manager', TestModel())._function_toolset.tools['read_daily_coding_changes']
        ctx = RunContext(deps=deps, model=TestModel(), usage=RunUsage())
        await tool.function_schema.call(tool.function_schema.validator.validate_python({}), ctx)
        await queue.put({'type': 'delta', 'text': 'Je consulte…'})
        raise failure('synthetic failure')
    monkeypatch.setattr(city_chat, '_run_codex_turn', stalled)
    async def scenario():
        events = [json.loads(event) async for event in city_chat.stream_chat(store, 'alice', 'desk_manager', 'Bilan')]
        assert not any(e['type'] == 'error' for e in events)
        assert [e['type'] for e in events[-3:]] == ['replace', 'delta', 'done']
        history = store.chat_history('alice', 'desk_manager', 2)
        assert history[-1]['content'] == events[-2]['text']
        assert 'Dates corrigées.' in history[-1]['content']
        assert 'n’a pas abouti' in history[-1]['content']
        assert history[-1]['tool_calls'][0]['status'] == 'completed'
    asyncio.run(scenario())
