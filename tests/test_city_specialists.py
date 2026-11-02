import json
import subprocess
from datetime import datetime, timezone

import pandas as pd
import pytest

from internships_project import city_services, city_specialists as specialists
from internships_project.marketdesk_city import AGENT_BY_ID, CityError, CityStore, CityWorker


@pytest.fixture
def store(tmp_path, monkeypatch):
    from internships_project import state_store
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'private.db')
    return CityStore(tmp_path / 'city.db')


@pytest.mark.parametrize('agent,legacy', [('job_hunter', {'cached_only': True}),
                                       ('finance_tutor', {'operation': 'daily_questions'}),
                                       ('developer', {'operation': 'repository_audit'}),
                                       ('innovation_lab', {'operation': 'prepare_branch'})])
def test_roles_reject_legacy_and_cross_role_tools(store, agent, legacy):
    with pytest.raises(CityError):
        store.create_task('alice', agent, 'ancienne mission', legacy)


def test_registry_tools_and_prompts():
    from pydantic_ai.models.test import TestModel
    from internships_project.city_agents import build_agent, PROMPTS
    assert len(AGENT_BY_ID) == 9
    for agent in specialists.SPECIALISTS:
        tools = build_agent(agent, TestModel())._function_toolset.tools
        assert 'execute_specialist_operation' in tools
        assert not {'delegate_to_agent', 'search_market_jobs', 'create_market_exercise', 'inspect_authorized_log', 'create_technical_quiz'}.intersection(tools)
        assert specialists.ROLE_NAMES[agent].split()[0].casefold() in PROMPTS[agent].casefold()


def test_migration_archives_pending_keeps_history_and_is_idempotent(store):
    with store.db() as db:
        db.execute('DELETE FROM city_role_migrations')
        for state in ['queued', 'running', 'completed']:
            db.execute("INSERT INTO city_tasks(id,username,agent_id,task_type,description,status,created_at,result_json) VALUES(?,?,'job_hunter','agent:job_hunter','Offres',?,'2026-01-01','{}')", (state, 'alice', state))
    store.migrate_roles()
    store.migrate_roles()
    with store.db() as db:
        rows = dict(db.execute('SELECT id,status FROM city_tasks'))
    assert rows == {'queued': 'cancelled', 'running': 'cancelled', 'completed': 'completed'}
    assert store.snapshot('alice')['agents'][3]['latest'] is None


def test_scheduler_once_per_day_and_week_and_disabled_accounts(store):
    store.ensure_agents('alice')
    moment = datetime(2026, 11, 2, 9, tzinfo=timezone.utc)
    assert store.enqueue_specialist_schedules(moment) == 3
    assert store.enqueue_specialist_schedules(moment) == 0
    assert {task['agent_id'] for task in store.snapshot('alice')['tasks']} == {'job_hunter','internship_scout','innovation_lab'}
    with store.db() as db:
        db.execute("UPDATE city_tasks SET status='completed'")
    assert store.enqueue_specialist_schedules(moment) == 0
    # Thursday starts Nova's second weekly slot, alongside two daily missions.
    thursday = datetime(2026, 11, 5, 9, tzinfo=timezone.utc)
    assert store.enqueue_specialist_schedules(thursday) == 3
    assert store.enqueue_specialist_schedules(thursday) == 0
    store.ensure_agents('bob')
    settings = store.get_settings('bob')
    settings['auto_tasks'] = False
    store.save_settings('bob', settings)
    assert store.enqueue_specialist_schedules(thursday) == 0


def test_retired_automatic_tasks_cancel_but_manual_and_history_survive(store):
    for agent,operation in [('developer','daily_questions'),('finance_tutor','quant_report')]:
        task=store.create_task('alice',agent,'Automatic',{'operation':operation})
        with store.db() as db:
            db.execute('INSERT INTO city_specialist_schedule VALUES(?,?,?,?)',('alice',operation,'old',task['id']))
    store.create_task('bob','developer','Manual interview',{'operation':'daily_questions'})
    store.enqueue_specialist_schedules()
    assert all(task['status']=='cancelled' for task in store.snapshot('alice')['tasks'] if task['agent_id'] in {'developer','finance_tutor'})
    assert next(task for task in store.snapshot('bob')['tasks'] if task['agent_id']=='developer')['status']=='queued'


def test_old_weekly_nova_review_counts_as_first_slot(store):
    store.ensure_agents('alice')
    with store.db() as db:
        db.execute('INSERT INTO city_specialist_schedule VALUES(?,?,?,?)',('alice','innovation_review','2026-W45','old-nova'))
    assert store.enqueue_specialist_schedules(datetime(2026,11,2,9,tzinfo=timezone.utc))==2
    assert not any(t['agent_id']=='innovation_lab' for t in store.snapshot('alice')['tasks'])
    assert store.enqueue_specialist_schedules(datetime(2026,11,5,9,tzinfo=timezone.utc))==1


def test_offline_periods_are_grouped_persisted_and_never_queued_twice(store):
    import json
    from concurrent.futures import ThreadPoolExecutor
    store.ensure_agents('alice')
    assert store.enqueue_specialist_schedules(datetime(2026,11,2,9,tzinfo=timezone.utc))==3
    with store.db() as db:
        db.execute("UPDATE city_tasks SET status='completed'")
    restart=datetime(2026,11,16,9,tzinfo=timezone.utc)
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert sum(pool.map(lambda _:store.enqueue_specialist_schedules(restart),range(3)))==3
    with store.db() as db:
        tasks=db.execute("SELECT agent_id,parameters_json FROM city_tasks WHERE status='queued'").fetchall()
    details={row[0]:json.loads(row[1]) for row in tasks}
    assert details['job_hunter']['catch_up']['periods']==14
    assert details['internship_scout']['catch_up']['periods']==14
    assert details['innovation_lab']['catch_up']['periods']==4
    assert details['innovation_lab']['catch_up']['from']=='2026-11-05'
    assert CityStore(store.path).enqueue_specialist_schedules(restart)==0
    task=store.claim_next()
    store.finish(task['id'],result={'title':'Current result','text':'Current sources'})
    completed=next(t for t in store.snapshot('alice')['tasks'] if t['id']==task['id'])
    assert completed['result']['catch_up']['periods'] in (4,14)
    assert 'ne sont pas reconstitués' in completed['result']['text']
    assert not store.snapshot('bob')['tasks']


def test_catchup_waits_for_active_task_and_respects_pause(store):
    store.ensure_agents('alice')
    store.enqueue_specialist_schedules(datetime(2026,11,2,9,tzinfo=timezone.utc))
    assert store.enqueue_specialist_schedules(datetime(2026,11,16,9,tzinfo=timezone.utc))==0
    with store.db() as db:
        db.execute("UPDATE city_tasks SET status='completed'")
    store.save_settings('alice',{'auto_tasks':False})
    assert store.enqueue_specialist_schedules(datetime(2026,11,16,9,tzinfo=timezone.utc))==0


def test_catchup_periods_handle_iso_year_and_first_use():
    from datetime import date
    from internships_project.marketdesk_city import _due_schedule_periods
    assert _due_schedule_periods('innovation_review',['2026-W53-Thu'],date(2027,1,4))==[('2027-W01-Mon',date(2027,1,4))]
    assert _due_schedule_periods('repository_audit',[],date(2026,11,2))==[('2026-11-02',date(2026,11,2))]
    assert [period for period,_ in _due_schedule_periods('repository_audit',['2026-03-28'],date(2026,3,30))]==['2026-03-29','2026-03-30']


def test_worker_never_executes_injected_legacy_task(store):
    with store.db() as db:
        db.execute("INSERT INTO city_tasks(id,username,agent_id,task_type,description,status,created_at) VALUES('legacy','alice','job_hunter','agent:job_hunter','Offres','queued','2026-01-01')")
    assert store.claim_next() is None
    assert store.snapshot('alice')['tasks'][0]['status'] == 'cancelled'


def test_quant_lag_costs_drawdown_and_chart():
    prices = pd.Series([100+i*.2+(i%6)*.5 for i in range(160)], index=pd.date_range('2025-01-01', periods=160))
    free = specialists.backtest(prices, lookback=20, cost_bps=0)
    paid = specialists.backtest(prices, lookback=20, cost_bps=20)
    assert free['metrics']['total_return'] > paid['metrics']['total_return']
    assert paid['metrics']['max_drawdown'] <= 0
    assert paid['equity'][0]['date'] == '2025-01-22'
    assert '<svg' in paid['chart_svg']
    # A future final-price change cannot affect earlier returns.
    modified = prices.copy(); modified.iloc[-1] *= 2
    assert specialists.backtest(modified, lookback=20)['equity'][:-1] == specialists.backtest(prices, lookback=20)['equity'][:-1]
    with pytest.raises(CityError):
        specialists.backtest(prices, strategy='fx_carry')


def test_noe_history_uses_existing_markets_collector(monkeypatch):
    from src import data
    calls = []
    def history(self, ids, days):
        calls.append((ids, days))
        return pd.DataFrame({'Date': pd.date_range('2025-01-01', periods=200), 'S&P 500': [100+i for i in range(200)]}), []
    monkeypatch.setattr(data.FredCollector, 'fetch_history', history)
    result = specialists.quant_report({})
    assert calls == [(['SP500'], 1825)]
    assert result['source'].endswith('/SP500')
    assert result['metrics']['observations'] > 60


def test_axel_daily_mock_and_answer_persist_across_restart(store):
    worker = CityWorker(store)
    for operation in ['daily_questions', 'mock_interview', 'evaluate_answer']:
        task = store.create_task('alice', 'developer', 'Entretien', {'operation':operation, 'question_id':'rates', 'answer':'Le prix baisse avec la duration et la convexité.'})
        assert worker.run_once()
        result = store.snapshot('alice')['tasks'][0]['result']
        if operation != 'evaluate_answer':
            assert len(result['questions']) == 5
        else:
            assert result['question_id'] == 'rates' and result['rubric_coverage'] == 4
    assert CityStore(store.path).snapshot('alice')['tasks'][0]['result']['question_id'] == 'rates'
    assert not CityStore(store.path).snapshot('bob')['tasks']


def test_nova_public_research_two_real_sources_and_no_install(monkeypatch):
    class Response:
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): pass
        def json(self): return self.payload
    def get(url, **kwargs):
        if '/search/' in url:
            return Response({'items':[{'full_name':f'org/tool{i}', 'html_url':f'https://github.com/org/tool{i}', 'license':{'spdx_id':'MIT'}} for i in range(2)]})
        return Response({'html_url':url.replace('api.github.com/repos','github.com'), 'name':url.split('/')[-1], 'license':{'spdx_id':'MIT'}})
    monkeypatch.setattr('requests.get', get)
    result = specialists.innovation_review()
    assert len(result['ideas']) == 2
    assert all(idea['approval_required'] and idea['license'] == 'MIT' for idea in result['ideas'])


def test_full_nova_review_handoff_is_private_deduplicated_and_requires_click(store, monkeypatch):
    monkeypatch.setattr(specialists, 'innovation_review', lambda *args: {'title':'Deux idées', 'text':'Prototype isolé', 'approval_required':True, 'role_version':2, 'ideas':[{'specification':'Tests typés'}]})
    task = store.create_task('alice', 'innovation_lab', 'Innovation', {'operation':'innovation_review'})
    worker = CityWorker(store)
    assert worker.run_once()
    with pytest.raises(CityError): store.review_specialist_proposal('bob', task['id'], True)
    handoff = store.review_specialist_proposal('alice', task['id'], True)
    assert handoff['task_id'] and store.review_specialist_proposal('alice', task['id'], True)['reused']
    monkeypatch.setattr(specialists, 'repository_audit', lambda: {'title':'Revue', 'text':'Revue datée', 'role_version':2})
    assert worker.run_once()
    assert store.snapshot('alice')['tasks'][0]['agent_id'] == 'job_hunter'


def test_prepare_branch_is_isolated_and_never_merges(tmp_path, monkeypatch):
    repo = tmp_path/'repository'; repo.mkdir()
    def git(*args): subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True)
    git('init'); git('config','user.name','Test'); git('config','user.email','test@example.invalid')
    (repo/'internships_project').mkdir(); (repo/'internships_project/city_sample.py').write_text('x=1\n')
    git('add','.'); git('commit','-m','Fixture')
    monkeypatch.setattr(specialists,'repo_root',lambda:repo)
    audit = specialists.repository_audit()
    with pytest.raises(CityError): specialists.prepare_branch('a'*32,audit,False)
    result = specialists.prepare_branch('a'*32,audit,True)
    assert result['tests']['passed'] == 2
    assert (repo/result['file']).is_file()
    assert not (repo/'tests/test_city_syntax_audit.py').exists()
    assert specialists.git(repo,'rev-parse','HEAD') == audit['revision']


def test_collectors_work_without_running_gradio(monkeypatch):
    monkeypatch.setattr(city_services, 'refresh_jobs_workflow', lambda:{'new_count':3})
    assert city_services.run_agent('networker','alice',{'operation':'refresh_internships'})['new_count'] == 3
    monkeypatch.setattr(city_services, 'market_snapshot', lambda:{'points':[{'series_id':'SP500','value':1}], 'status':{}, 'retrieved_at':'2026-11-02'})
    result = city_services.run_agent('finance_tutor','alice',{'operation':'collect_markets'})
    assert result['market_data'][0]['series_id'] == 'SP500'


def test_http_collectors_and_approval_remain_authenticated_and_origin_protected(store):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from internships_project.city_routes import add_city_routes
    class Worker:
        def start(self): pass
    app = FastAPI()
    add_city_routes(app, lambda request: request.headers.get('test-user'), store, Worker())
    with TestClient(app) as client:
        assert client.post('/city/api/collect/markets').status_code == 401
        assert client.post('/city/api/collect/markets', headers={'test-user':'alice'}).status_code == 403
        headers = {'test-user':'alice', 'X-MarketDesk-City':'1'}
        assert client.post('/city/api/collect/markets', headers={**headers,'Origin':'https://evil.invalid'}).status_code == 403
        first = client.post('/city/api/collect/markets', headers=headers)
        assert first.status_code == 201 and first.json()['task']['agent_id'] == 'finance_tutor'
        assert client.post('/city/api/collect/markets', headers=headers).json()['already_running']
        assert client.post('/city/api/collect/internships', headers=headers).json()['task']['agent_id'] == 'internship_scout'
        assert client.post('/city/api/proposals/missing/review', headers=headers, json={'approved':True}).status_code == 400
        assert client.post('/city/api/proposals/missing/review', headers=headers, json=[]).status_code == 400


def test_deleted_account_removes_schedules_reviews_and_private_progress(store):
    store.ensure_agents('alice')
    store.enqueue_specialist_schedules()
    store.delete_account('alice')
    with store.db() as db:
        for table in ['city_tasks','city_specialist_schedule','city_proposal_reviews','city_network_schedule']:
            assert db.execute(f'SELECT COUNT(*) FROM {table} WHERE username=?',('alice',)).fetchone()[0] == 0
