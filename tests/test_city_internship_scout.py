"""Hugo calls the Python collector, with confirmed publication dates and no email."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from internships_project import internships, state_store
from internships_project.marketdesk_city import CityStore, CityWorker, CityError


def test_manager_hugo_refresh_and_same_day_repeat(tmp_path, monkeypatch):
    from pydantic_ai.models.test import TestModel
    from internships_project.city_agents import ChatDeps, build_agent
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    today = datetime.now(ZoneInfo('Europe/Paris')).date().isoformat()
    now = datetime.now(timezone.utc)
    def offer(name, date=today, kind='Stage', inferred=False):
        return internships.Opportunity(name, 'Bank', 'Paris', kind, 'https://example.com/'+name,
                                       date, 90, published_inferred=inferred)
    current = [offer('cached-today')]
    jobs = current + [offer('new-today'), offer('yesterday', (datetime.now(ZoneInfo('Europe/Paris')).date()-timedelta(days=1)).isoformat()),
                      offer('unknown', ''), offer('estimated', inferred=True), offer('vie', kind='VIE')]
    monkeypatch.setattr(internships, 'opportunities_loading', lambda:False)
    monkeypatch.setattr(internships, 'load_opportunities', lambda **kwargs:(current, [], now-timedelta(seconds=1)))
    calls=[]
    def refresh(**kwargs):
        calls.append(kwargs)
        return jobs, ['Source unavailable'], now
    monkeypatch.setattr(internships, 'refresh_opportunities', refresh)
    manager = build_agent('desk_manager', TestModel())
    ctx = SimpleNamespace(deps=ChatDeps('alice',store))
    tool = manager._function_toolset.tools['collect_dashboard_data'].function
    response = asyncio.run(tool(ctx, 'internships'))
    assert response['status']=='completed'
    assert store.snapshot('alice')['tasks'][0]['agent_id']=='internship_scout'
    assert CityWorker(store).run_once()
    result=store.snapshot('alice')['tasks'][0]['result']
    assert {job['title'] for job in result['offers']}=={'cached-today','new-today'}
    assert result['today_count']==2 and result['source_errors']==1
    assert calls==[{'force':True,'notify_email':False,'fail_if_busy':True}]
    assert store.snapshot('bob')['tasks']==[]
    store.create_task('alice','internship_scout','Stages du jour')
    assert CityWorker(store).run_once()
    assert len(calls)==2
    with pytest.raises(CityError):
        store.create_task('alice','internship_scout','Shell',{'command':'anything'})
    hugo=build_agent('internship_scout',TestModel())
    assert 'collect_todays_internships' in hugo._function_toolset.tools
    assert 'delegate_to_agent' not in hugo._function_toolset.tools


def test_manager_routes_markets_collection_to_mira(tmp_path, monkeypatch):
    from pydantic_ai.models.test import TestModel
    from internships_project.city_agents import ChatDeps, build_agent
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path/'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    tool = build_agent('desk_manager', TestModel())._function_toolset.tools['collect_dashboard_data'].function
    response = asyncio.run(tool(SimpleNamespace(deps=ChatDeps('alice', store)), 'markets'))
    assert response['status'] == 'completed'
    task = store.snapshot('alice')['tasks'][0]
    assert task['agent_id'] == 'market_analyst'
    with store.db() as db:
        parameters = db.execute('SELECT parameters_json FROM city_tasks WHERE id=?', (task['id'],)).fetchone()[0]
    assert json.loads(parameters)['operation'] == 'collect_markets'
    specialist_tool = build_agent('desk_manager', TestModel())._function_toolset.tools['start_specialist_mission'].function
    with pytest.raises(CityError, match='Mira'):
        asyncio.run(specialist_tool(SimpleNamespace(deps=ChatDeps('alice', store)), 'Noé', 'collect_markets'))
    with pytest.raises(CityError):
        store.create_task('alice', 'finance_tutor', 'Collecter les données Markets', {'operation': 'collect_markets'})


def test_daily_hugo_reports_detection_not_publication_and_posts_once(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store,'USER_DB_PATH',tmp_path/'accounts.sqlite3')
    now=datetime.now(timezone.utc)
    old=(now-timedelta(days=7)).date().isoformat()
    jobs=[internships.Opportunity('Older publication, new detection','Bank','Paris','Stage','https://example.com/new',old,90),
          internships.Opportunity('Known offer','Bank','Paris','Stage','https://example.com/known',old,90)]
    monkeypatch.setattr(internships,'opportunities_loading',lambda:False)
    monkeypatch.setattr(internships,'load_opportunities',lambda **kwargs:([jobs[1]],[],now-timedelta(seconds=1)))
    monkeypatch.setattr(internships,'refresh_opportunities',lambda **kwargs:(jobs,[],now))
    store=CityStore(state_store.USER_DB_PATH)
    store.ensure_agents('alice')
    store.enqueue_specialist_schedules()
    # Run only the daily Hugo task; keep unrelated services out of this test.
    with store.db() as db:
        db.execute("UPDATE city_tasks SET status='cancelled' WHERE agent_id!='internship_scout'")
    assert CityWorker(store).run_once()
    task=next(t for t in store.snapshot('alice')['tasks'] if t['agent_id']=='internship_scout')
    assert [o['url'] for o in task['result']['offers']]==['https://example.com/new']
    assert task['result']['today_count']==1
    store.finish(task['id'],result=task['result'])
    # The daily manager digest waits for Mira, Hugo and Jules before posting once.
    assert store.chat_history('alice','desk_manager')==[]
    assert store.chat_history('bob','desk_manager')==[]
    assert store.enqueue_specialist_schedules()==0


def test_daily_hugo_failure_is_reported_once(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store,'USER_DB_PATH',tmp_path/'accounts.sqlite3')
    store=CityStore(state_store.USER_DB_PATH)
    task=store.create_task('alice','internship_scout','Daily refresh',{'operation':'refresh_internships','daily_digest':True})
    assert store.claim_next()['id']==task['id']
    store.finish(task['id'],error='Source unavailable')
    store.finish(task['id'],error='Source unavailable')
    assert store.chat_history('alice','desk_manager')==[]
