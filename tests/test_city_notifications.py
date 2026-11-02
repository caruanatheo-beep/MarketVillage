import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

from internships_project import city_specialists, state_store
from internships_project.city_agents import ChatDeps, build_agent
from internships_project.city_routes import add_city_routes
from internships_project.marketdesk_city import CityStore, CityWorker, CityError


@pytest.fixture
def store(tmp_path,monkeypatch):
    monkeypatch.setattr(state_store,'USER_DB_PATH',tmp_path/'private.sqlite3')
    return CityStore(state_store.USER_DB_PATH)


@pytest.mark.parametrize('name',['Jules','job_hunter'])
def test_manager_starts_jules_by_name_or_id_with_safe_default(store,monkeypatch,name):
    manager=build_agent('desk_manager',TestModel())
    tool=manager._function_toolset.tools['start_specialist_mission'].function
    result=asyncio.run(tool(SimpleNamespace(deps=ChatDeps('alice',store)),name))
    assert result['status']=='completed'
    task=store.snapshot('alice')['tasks'][0]
    assert task['agent_id']=='job_hunter'
    monkeypatch.setattr(city_specialists,'repository_audit',lambda:{'title':'Local audit','revision':'abc','role_version':2})
    assert CityWorker(store).run_once()
    assert store.snapshot('alice')['tasks'][0]['status']=='completed'
    assert store.snapshot('bob')['tasks']==[]


def test_manager_still_cannot_prepare_branch_or_use_cross_role_tools(store):
    tool=build_agent('desk_manager',TestModel())._function_toolset.tools['start_specialist_mission'].function
    ctx=SimpleNamespace(deps=ChatDeps('alice',store))
    with pytest.raises(CityError,match='Valider la proposition'):
        asyncio.run(tool(ctx,'Jules','prepare_branch'))
    with pytest.raises(CityError,match='incompatible'):
        asyncio.run(tool(ctx,'Jules','daily_questions'))
    assert store.snapshot('alice')['tasks']==[]


def test_jules_named_tool_call_works_through_actual_agent_execution(store):
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai.messages import ModelResponse, ToolCallPart, TextPart
    calls=[]
    def model(messages,info):
        calls.append(1)
        if len(calls)==1:
            return ModelResponse(parts=[ToolCallPart('start_specialist_mission',{'specialist':'Jules','operation':'repository_audit'})])
        return ModelResponse(parts=[TextPart('Nouvelle revue de Jules ajoutée.')])
    agent=build_agent('desk_manager',FunctionModel(model))
    answer=asyncio.run(agent.run('Lance maintenant une nouvelle revue du code avec Jules.',deps=ChatDeps('alice',store)))
    assert 'Jules' in answer.output
    assert store.snapshot('alice')['tasks'][0]['agent_id']=='job_hunter'


def test_notification_read_state_scoped_persistent_monotonic_and_non_authorizing(store):
    task=store.create_task('alice','job_hunter','Audit',{'operation':'repository_audit'})
    store.notification_state('alice',999999)
    latest=max(e['id'] for e in store.snapshot('alice')['events'])
    assert CityStore(store.path).notification_state('alice')['last_read_event_id']==latest
    assert store.notification_state('alice',0)['last_read_event_id']==latest
    assert store.notification_state('bob')['last_read_event_id']==0
    assert store.snapshot('alice')['tasks'][0]['status']=='queued'
    for invalid in [-1,True,'3']:
        with pytest.raises(CityError):store.notification_state('alice',invalid)
    store.delete_account('alice')
    assert store.notification_state('alice')['last_read_event_id']==0


def test_old_unresolved_proposal_stays_visible_beyond_recent_task_limit(store):
    store.ensure_agents('alice')
    with store.db() as db:
        db.execute("INSERT INTO city_tasks(id,username,agent_id,task_type,description,status,created_at,result_json) VALUES('old','alice','job_hunter','agent:job_hunter','Old proposal','completed','2025-01-01',?)",
                   (json.dumps({'role_version':2,'approval_required':True,'branch':'','review_decision':''}),))
        for i in range(110):
            db.execute("INSERT INTO city_tasks(id,username,agent_id,task_type,description,status,created_at,result_json) VALUES(?,'alice','market_analyst','agent:market_analyst','Recent','completed','2026-01-01','{}')",(str(i),))
    assert 'old' in {t['id'] for t in store.snapshot('alice')['tasks']}
    assert not store.snapshot('bob')['tasks']


def test_new_endpoints_require_auth_origin_and_cannot_approve_branches(store):
    app=FastAPI()
    add_city_routes(app,lambda request:request.headers.get('x-test-user'),store,CityWorker(store))
    headers={'x-test-user':'alice','X-MarketDesk-City':'1'}
    with TestClient(app) as client:
        assert client.get('/city/api/notifications').status_code==401
        assert client.post('/city/api/agents/job_hunter/run',json={}).status_code==401
        assert client.post('/city/api/agents/job_hunter/run',headers={'x-test-user':'alice'},json={}).status_code==403
        assert client.post('/city/api/notifications/read',headers={**headers,'Origin':'https://evil.invalid'},json={'read_through':1}).status_code==403
        assert client.post('/city/api/agents/job_hunter/run',headers=headers,json={'operation':'prepare_branch'}).status_code==400
        assert client.post('/city/api/agents/job_hunter/run',headers=headers,json={}).status_code==201
        assert client.post('/city/api/agents/job_hunter/run',headers=headers,json={}).status_code==400
        assert client.post('/city/api/agents/networker/run',headers=headers,json={}).status_code==400
        assert client.post('/city/api/notifications/read',headers=headers,json={'read_through':True}).status_code==400
        assert client.post('/city/api/notifications/read',headers=headers,json={'read_through':999999}).status_code==200
        assert client.get('/city/api/notifications',headers={'x-test-user':'bob'}).json()['last_read_event_id']==0
