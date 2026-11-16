import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from internships_project import state_store, city_chat
from internships_project.marketdesk_city import CityStore, CityError, AGENT_BY_ID
from internships_project.city_agents import ChatDeps, build_agent


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'manager.sqlite3')
    return CityStore(state_store.USER_DB_PATH)


@pytest.mark.parametrize('approval', [False, True])
def test_manager_resumes_existing_pending_task_without_duplicate(store, approval):
    store.save_settings('alice', {'auto_tasks': not approval})
    task = store.create_task('alice', 'market_analyst', 'Market brief',
        scheduled_at=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat())
    result = store.resume_mission('alice', task['id'])
    assert result['changed'] and result['status']=='queued' and result['id']==task['id']
    assert store.task_detail('alice', task['id'])['scheduled_at'] is None
    assert store.resume_mission('alice', task['id'])['changed'] is False
    assert len(store.snapshot('alice')['tasks'])==1
    assert store.claim_next()['id']==task['id']
    assert store.resume_mission('alice', task['id'])['status']=='running'


@pytest.mark.parametrize('agent,parameters', [('market_analyst', {}), ('job_hunter', {'operation':'develop'})])
def test_failed_resume_runs_even_with_auto_tasks_off_and_is_idempotent(store, agent, parameters):
    task=store.create_task('alice',agent,'Retry test',parameters,auto_run=True)
    store.claim_next()
    store.finish(task['id'],error='Temporary test error')
    store.save_settings('alice',{'auto_tasks':False})
    result=store.resume_mission('alice',task['id'])
    assert result['changed'] and result['status']=='queued'
    repeat=store.resume_mission('alice',task['id'])
    assert not repeat['changed'] and repeat['id']==result['id']
    assert len([t for t in store.snapshot('alice')['tasks'] if t['status']=='queued'])==1


def test_account_isolation_cancellation_and_dependencies(store):
    task=store.create_task('alice','market_analyst','Private mission')
    with pytest.raises(CityError,match='introuvable'):
        store.resume_mission('bob',task['id'])
    assert store.resumable_missions('bob')['total']==0
    assert store.cancel_queued('alice',task['id'])
    with pytest.raises(CityError,match='annulée'):
        store.resume_mission('alice',task['id'])
    workflow=store.create_custom_workflow('alice','Project','Dependencies',[
        {'id':'market','agent_id':'market_analyst','description':'Market step','depends_on':[]},
        {'id':'interview','agent_id':'developer','operation':'daily_questions','description':'Interview step','depends_on':['market']}])
    child=workflow['task_ids'][1]
    assert store.resume_mission('alice',child)['status']=='queued'
    assert store.claim_next()['id']==workflow['task_ids'][0]
    assert store.claim_next() is None


def test_manager_tools_return_real_results_and_bound_retries(store):
    task=store.create_task('alice','market_analyst','Queued task')
    deps=ChatDeps(username='alice',store=store,current_message='Reprends la mission')
    tools=build_agent('desk_manager',TestModel())._function_toolset.tools
    assert 'resume_missions' not in build_agent('networker',TestModel())._function_toolset.tools
    ctx=RunContext(deps=deps,model=None,usage=RunUsage())
    async def run():
        read=await tools['inspect_mission_queue'].function_schema.call({'status':'pending','page':1},ctx)
        assert read['data']['missions'][0]['id']==task['id']
        result=await tools['resume_missions'].function_schema.call({'task_ids':[task['id'],'other-account-id']},ctx)
        assert [x['status'] for x in result['data']['missions']]==['queued','refused']
        assert '1 mission(s)' in deps.calls[-1]['text']
        repeat=await tools['resume_missions'].function_schema.call({'task_ids':[task['id']]},ctx)
        assert not repeat['data']['missions'][0]['changed']
        excess=await tools['resume_missions'].function_schema.call({'task_ids':[str(i) for i in range(9)]},ctx)
        assert excess['status']=='unavailable'
    asyncio.run(run())


def test_resume_keeps_specific_code_proposal_validation(store):
    task=store.create_task('alice','job_hunter','Proposition de correction',
                           {'operation':'code_change','request':'Corriger un exemple'},auto_run=False)
    before=store.task_detail('alice',task['id'])['status']
    with pytest.raises(CityError,match='proposition'):
        store.resume_mission('alice',task['id'])
    assert store.task_detail('alice',task['id'])['status']==before


def test_chat_failure_after_action_keeps_receipt_and_actual_task_state(store, monkeypatch):
    task=store.create_task('alice','market_analyst','Retry via chat')
    async def interrupted(deps,message,queue,timeout):
        tool=build_agent('desk_manager',TestModel())._function_toolset.tools['resume_missions']
        await tool.function_schema.call({'task_ids':[task['id']]},RunContext(deps=deps,model=None,usage=RunUsage()))
        raise CityError('Synthetic response failure')
    monkeypatch.setattr(city_chat,'_run_codex_turn',interrupted)
    async def run():
        return [json.loads(event) async for event in city_chat.stream_chat(store,'alice','desk_manager','Reprends la mission')]
    events=asyncio.run(run())
    assert any(e['type']=='error' for e in events)
    history=store.chat_history('alice','desk_manager')
    assert history[-1]['role']=='assistant' and history[-1]['tool_calls'][-1]['status']=='completed'
    assert 'interromp' in history[-1]['content'] or 'failure' in history[-1]['content']
    assert store.task_detail('alice',task['id'])['status']=='queued'


@pytest.mark.parametrize('intent', ['resume_pending', 'resume_failed'])
def test_resume_shortcuts_work_without_codex_and_limit_to_eight(store, monkeypatch, intent):
    agents = [agent for agent in AGENT_BY_ID if agent != 'desk_manager'][:10]
    tasks = [store.create_task('alice', agent, f'Mission {i}', {'operation': 'develop'}, auto_run=True,
             scheduled_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()) for i, agent in enumerate(agents)]
    if intent == 'resume_failed':
        for task in tasks:
            with store.db() as db:
                db.execute("UPDATE city_tasks SET status='running' WHERE id=?", (task['id'],))
            store.finish(task['id'], error='Temporary error')
    store.save_settings('bob', {'auto_tasks': False})
    other = store.create_task('bob', 'market_analyst', 'Other account', auto_run=False)
    async def no_codex(*args):
        pytest.fail('Shortcuts must not depend on Codex')
    monkeypatch.setattr(city_chat, '_run_codex_turn', no_codex)
    async def run():
        return [json.loads(event) async for event in city_chat.stream_chat(
            store, 'alice', 'desk_manager', 'Reprends les missions', {'intent': intent})]
    events = asyncio.run(run())
    assert not any(e['type'] == 'error' for e in events), events
    answer = ''.join(e.get('text', '') for e in events if e['type'] == 'delta')
    assert '8 mission(s) remise(s) en file' in answer
    assert 'huit missions les plus récentes' in answer
    assert 'Other account' not in answer
    assert store.task_detail('bob', other['id'])['status'] == 'waiting_approval'
    assert store.task_detail('alice', tasks[0]['id'])['scheduled_at'] is not None
    assert store.chat_history('alice', 'desk_manager')[-1]['content'] == answer


def test_resume_shortcut_reports_refusals_and_preserves_dependencies(store):
    store.save_settings('alice', {'auto_tasks': False})
    proposal = store.create_task('alice', 'job_hunter', 'Specific approval required',
        {'operation': 'code_change', 'request': 'Fix example'}, auto_run=False)
    workflow = store.create_custom_workflow('alice', 'Steps', 'Keep dependencies', [
        {'id': 'first', 'agent_id': 'market_analyst', 'description': 'First', 'depends_on': []},
        {'id': 'next', 'agent_id': 'developer', 'operation': 'daily_questions', 'description': 'Next', 'depends_on': ['first']}])
    deps = ChatDeps(username='alice', store=store, current_message='Reprends')
    answer = asyncio.run(city_chat._resume_shortcut(deps, 'pending'))
    assert 'validation' in answer and 'Specific approval required' in answer
    assert 'Dépendances conservées' in answer
    assert store.task_detail('alice', proposal['id'])['status'] == 'waiting_approval'
    assert store.claim_next()['id'] == workflow['task_ids'][0]
    assert store.claim_next() is None


def test_codex_permission_error_is_actionable_and_redacted():
    error = str(city_chat._closed_codex_error(b'failed to initialize sqlite state runtime under C:/private/token-secret'))
    assert 'droits' in error
    assert 'private' not in error and 'token-secret' not in error
