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
    assert store.enqueue_specialist_schedules(moment) == 4
    assert store.enqueue_specialist_schedules(moment) == 0
    # Free Axel's daily slot; weekly mock interview then becomes due once.
    with store.db() as db:
        db.execute("UPDATE city_tasks SET status='completed' WHERE agent_id='developer'")
    assert store.enqueue_specialist_schedules(moment) == 1
    assert store.enqueue_specialist_schedules(moment) == 0
    store.ensure_agents('bob')
    settings = store.get_settings('bob')
    settings['auto_tasks'] = False
    store.save_settings('bob', settings)
    assert store.enqueue_specialist_schedules(moment) == 0


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
