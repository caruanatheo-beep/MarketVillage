import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel

from internships_project import city_coding as coding, city_specialists as specialists, state_store
from internships_project.city_agents import ChatDeps, build_agent
from internships_project.city_routes import add_city_routes
from internships_project.marketdesk_city import AGENT_BY_ID, CityStore, CityWorker, CityError


@pytest.fixture
def store(tmp_path,monkeypatch):
    monkeypatch.setattr(state_store,'USER_DB_PATH',tmp_path/'accounts.sqlite3')
    return CityStore(state_store.USER_DB_PATH)


@pytest.fixture
def repo(tmp_path,monkeypatch):
    root=tmp_path/'repo';root.mkdir()
    def git(*args):
        return subprocess.run(['git','-c','core.hooksPath=NUL' if os.name=='nt' else 'core.hooksPath=/dev/null',*args],cwd=root,check=True,capture_output=True,text=True).stdout.strip()
    git('init');git('config','user.name','test');git('config','user.email','test@example.invalid')
    (root/'sample.py').write_text('value = 1\n')
    (root/'tests').mkdir()
    (root/'tests/test_internships_start_dates.py').write_text('def test_baseline():\n    assert True\n')
    git('add','.');git('-c','commit.gpgsign=false','commit','-m','fixture')
    monkeypatch.setattr(coding,'repo_root',lambda:root)
    monkeypatch.setattr(coding,'codex_binary',lambda:'fixture-codex')
    monkeypatch.setattr(coding,'require_chatgpt',lambda *args:None)
    monkeypatch.setattr(coding,'codex_usage_percent',lambda *_:0)
    return root,git


def test_coding_validation_allows_internship_feature_but_not_shell():
    assert specialists.validate_mission('job_hunter',{'operation':'code_change','request':'Corrige le filtre des stages'},'Corriger les stages')['request']
    for request in ('short','x'*3001):
        with pytest.raises(CityError):specialists.validate_mission('job_hunter',{'operation':'code_change','request':request})
    with pytest.raises(CityError):specialists.validate_mission('job_hunter',{'operation':'code_change','request':'Corrige le filtre','shell':'whoami'})


def test_codex_auth_rejects_api_and_environment_has_no_application_secrets(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-private')
    monkeypatch.setenv('CODEX_API_KEY','test-private')
    monkeypatch.setenv('MARKETDESK_SESSION_SECRET','test-private')
    env=coding.codex_environment()
    assert not any(k in env for k in ('OPENAI_API_KEY','CODEX_API_KEY','MARKETDESK_SESSION_SECRET'))
    monkeypatch.setattr(subprocess,'run',lambda *args,**kwargs:SimpleNamespace(returncode=0,stdout='',stderr='Logged in using an API key'))
    with pytest.raises(CityError,match='ChatGPT'):coding.require_chatgpt('codex',env)


def test_codex_environment_restores_windows_home_without_exposing_api_keys(monkeypatch, tmp_path):
    monkeypatch.delenv('HOME', raising=False)
    monkeypatch.delenv('CODEX_HOME', raising=False)
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    monkeypatch.setenv('OPENAI_API_KEY', 'private')
    env = coding.codex_environment()
    if os.name == 'nt':
        assert env['HOME'] == str(tmp_path)
        assert env['CODEX_HOME'] == str(tmp_path / '.codex')
    assert 'OPENAI_API_KEY' not in env


def test_coding_runs_only_after_human_approval_and_keeps_main_untouched(repo,store,monkeypatch):
    root,git=repo
    monkeypatch.setattr(specialists,'repo_root',lambda:root)
    calls=[]
    def execute(command,directory,prompt,env):
        calls.append(command)
        assert '--sandbox' in command and command[command.index('--sandbox')+1]=='workspace-write'
        assert 'forced_login_method="chatgpt"' in command and '--ignore-user-config' in command
        assert 'danger-full-access' not in command
        assert 'Corrige sample' in prompt
        (directory/'sample.py').write_text('value = 2\n')
        (directory/'test_sample.py').write_text('def test_value():\n    assert 2 == 2\n')
        Path(command[command.index('--output-last-message')+1]).write_text(json.dumps({'summary':'Valeur corrigée','tests':'1 test passé','limitations':'Test de fixture'}))
        return [{'type':'item.completed','item':{'type':'command_execution','command':'python -m pytest test_sample.py','exit_code':0}}, {'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':4}}]
    monkeypatch.setattr(coding,'_execute',execute)
    task=store.create_task('alice','job_hunter','Corrige sample',{'operation':'code_change','request':'Corrige sample pour renvoyer deux'})
    assert CityWorker(store).run_once()
    proposal=next(t for t in store.snapshot('alice')['tasks'] if t['id']==task['id'])
    assert proposal['result']['approval_required'] and calls==[]
    with pytest.raises(CityError):store.review_specialist_proposal('bob',task['id'],True)
    approved=store.review_specialist_proposal('alice',task['id'],True)
    assert store.review_specialist_proposal('alice',task['id'],True)['reused']
    assert CityWorker(store).run_once()
    done=next(t for t in store.snapshot('alice')['tasks'] if t['id']==approved['task_id'])
    assert done['status']=='completed',done.get('error')
    assert len(calls)==1 and (root/'sample.py').read_text()=='value = 1\n'
    assert done['result']['files']==['sample.py','test_sample.py']
    assert '+value = 2' in done['result']['diff'] and '+def test_value' in done['result']['diff']
    assert done['result']['checks'][0]['exit_code']==0
    assert not done['result']['approval_required']
    assert git('status','--porcelain','--untracked-files=no')==''


def test_autonomous_engineer_integrates_validated_code_without_approval(repo, monkeypatch):
    root, git = repo
    packages = root/'.venv'/'Lib'/'site-packages'
    packages.mkdir(parents=True)
    monkeypatch.setattr(coding, 'codex_usage_percent', lambda *_: 12)
    original_run = subprocess.run
    def run(command, **kwargs):
        if command[:2] == [sys.executable, '-c']:
            return SimpleNamespace(returncode=0)
        return original_run(command, **kwargs)
    monkeypatch.setattr(coding.subprocess, 'run', run)
    def execute(command, directory, prompt, env):
        assert '--model' in command and command[command.index('--model') + 1] == 'gpt-6.1-sol'
        assert 'Sacha' in prompt
        assert 'choisis celui qui gêne le plus l’utilisateur' in prompt
        assert 'accélérer la collecte' in prompt
        assert 'Ne prétends pas avoir validé un site externe' in prompt
        assert 'pages et flux publics des sites carrières' in prompt
        assert 'sandbox_workspace_write.network_access=true' in command
        assert 'scripts/city_test.py' in prompt
        assert env['MARKETDESK_TEST_SITE_PACKAGES'] == str(packages)
        target = directory/'internships_project/city_sample.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('value = 2\n')
        Path(command[command.index('--output-last-message') + 1]).write_text(json.dumps(
            {'summary': 'Source corrigée', 'tests': 'Test ciblé passé', 'limitations': 'Aucune'}))
        return [{'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 5}}]
    monkeypatch.setattr(coding, '_execute', execute)
    result = coding.implement_change('c'*32, {'coding_request': ''},
                                    agent_id='internships_engineer', auto_integrate=True)
    assert result['integrated'] and result['commit'] == git('rev-parse', 'HEAD')
    assert 'intégrée' in result['base_note']
    assert (root/'internships_project/city_sample.py').read_text() == 'value = 2\n'


def test_every_autonomous_engineer_has_a_distinct_product_focus():
    assert set(coding.AUTONOMOUS_FOCUS) == set(specialists.CODING_AGENTS)
    assert len(set(coding.AUTONOMOUS_FOCUS.values())) == len(specialists.CODING_AGENTS)


def test_codex_daily_budget_prevents_a_new_worktree(repo, store, monkeypatch):
    root, _ = repo
    monkeypatch.setattr(coding, 'codex_usage_percent', lambda *_: 60)
    before = coding.require_daily_codex_budget('codex', {})
    monkeypatch.setattr(coding, 'codex_usage_percent', lambda *_: 60 + coding.CODEX_DAILY_USAGE_PERCENT)
    coding.record_daily_codex_usage('codex', {}, before)
    monkeypatch.setattr(coding, '_execute', lambda *_args: pytest.fail('Codex must stay stopped'))
    with pytest.raises(CityError, match='budget Codex quotidien'):
        coding.implement_change('9'*32, {'coding_request': ''}, agent_id='job_hunter', auto_integrate=True)
    assert not (root/'.city-worktrees'/('9'*32)).exists()


def test_git_failure_does_not_consume_codex_fallback_budget(repo, store, monkeypatch):
    root, _ = repo
    original_git = coding.git
    monkeypatch.setattr(coding, 'codex_usage_percent', lambda *_: (_ for _ in ()).throw(CityError('Quota indisponible')))
    def locked_git(directory, *args):
        if args[:2] == ('worktree', 'add'):
            raise CityError('Git indisponible pour cette opération.')
        return original_git(directory, *args)
    monkeypatch.setattr(coding, 'git', locked_git)
    with pytest.raises(CityError, match='Git indisponible'):
        coding.implement_change('f' * 32, {'coding_request': ''}, agent_id='job_hunter', auto_integrate=True)
    with store.db() as db:
        consumed, calls = db.execute('SELECT consumed,fallback_calls FROM city_codex_agent_usage').fetchone()
    assert consumed == 0 and calls == 0
    assert not (root / '.city-worktrees' / ('f' * 32)).exists()


def test_codex_daily_budget_reads_weekly_window_only():
    assert coding._weekly_usage_percent({'codex': {
        'primary': {'usedPercent': 85, 'windowDurationMins': 300},
        'secondary': {'usedPercent': 23, 'windowDurationMins': 10080}}}) == 23
    assert coding._weekly_usage_percent({'codex': {
        'primary': {'usedPercent': 23, 'windowDurationMins': 10080}}}) == 23
    with pytest.raises(CityError, match='Quota Codex indisponible'):
        coding._weekly_usage_percent({'codex': {'primary': {'usedPercent': 85, 'windowDurationMins': 300}}})


def test_codex_daily_budget_resets_on_new_day_and_weekly_reset(store, monkeypatch):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    today = datetime(2026, 11, 6, 10, tzinfo=ZoneInfo('Europe/Paris'))
    current = [today]
    used = [62.0]
    monkeypatch.setattr(coding, 'datetime', SimpleNamespace(now=lambda _tz: current[0]))
    monkeypatch.setattr(coding, 'codex_usage_percent', lambda *_: used[0])
    before = coding.require_daily_codex_budget('codex', {})
    used[0] = 75.0
    coding.record_daily_codex_usage('codex', {}, before)
    before = coding.require_daily_codex_budget('codex', {})
    used[0] = 77.0
    coding.record_daily_codex_usage('codex', {}, before)
    with pytest.raises(CityError, match='budget Codex quotidien'):
        coding.require_daily_codex_budget('codex', {})
    current[0] = today + timedelta(days=1)
    before = coding.require_daily_codex_budget('codex', {})
    used[0] = 2.0  # Subscription's weekly window reset during the day.
    coding.record_daily_codex_usage('codex', {}, before)
    before = coding.require_daily_codex_budget('codex', {})
    used[0] = 13.0
    coding.record_daily_codex_usage('codex', {}, before)
    before = coding.require_daily_codex_budget('codex', {})
    used[0] = 15.0
    coding.record_daily_codex_usage('codex', {}, before)
    with pytest.raises(CityError, match='budget Codex quotidien'):
        coding.require_daily_codex_budget('codex', {})


def test_codex_budget_excludes_usage_between_agent_calls(store, monkeypatch):
    used = [60.0]
    monkeypatch.setattr(coding, 'codex_usage_percent', lambda *_: used[0])
    before = coding.require_daily_codex_budget('codex', {})
    used[0] = 62.0
    coding.record_daily_codex_usage('codex', {}, before)
    used[0] = 80.0  # Usage outside City between its calls.
    before = coding.require_daily_codex_budget('codex', {})
    used[0] = 81.0
    coding.record_daily_codex_usage('codex', {}, before)
    with store.db() as db:
        consumed = db.execute('SELECT consumed FROM city_codex_agent_usage').fetchone()[0]
    assert consumed == 3.0


def test_codex_budget_allows_bounded_calls_when_meter_is_unavailable(store, monkeypatch):
    def unavailable(*_args):
        raise CityError('Quota Codex indisponible : missions de développement suspendues.')
    monkeypatch.setattr(coding, 'codex_usage_percent', unavailable)
    for _ in range(coding.CODEX_DAILY_FALLBACK_CALLS):
        assert coding.require_daily_codex_budget('codex', {}) is None
    with pytest.raises(CityError, match='budget Codex quotidien'):
        coding.require_daily_codex_budget('codex', {})


def test_autonomous_worktree_resumes_after_main_becomes_clean(repo, monkeypatch):
    root, git = repo
    monkeypatch.setattr(coding, 'codex_usage_percent', lambda *_: 12)
    monkeypatch.setattr(coding, '_integration_checks', lambda *_args, **_kwargs: 'focused tests')
    calls = []
    def execute(command, directory, prompt, env):
        calls.append(command)
        target = directory/'internships_project/city_sample.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('value = 2\n')
        Path(command[command.index('--output-last-message') + 1]).write_text(json.dumps(
            {'summary': 'Une valeur a été corrigée.', 'tests': 'Test ciblé réussi.', 'limitations': 'Aucune.'}))
        (root/'sample.py').write_text('value = 9\n')
        return [{'type': 'turn.completed'}]
    monkeypatch.setattr(coding, '_execute', execute)
    task_id = 'a'*32
    with pytest.raises(CityError, match='modifications locales suivies'):
        coding.implement_change(task_id, {'coding_request': ''}, agent_id='job_hunter', auto_integrate=True)
    worktree = root/'.city-worktrees'/task_id
    assert (worktree/'.jules-complete.json').exists()
    assert len(calls) == 1
    (root/'sample.py').write_text('value = 1\n')
    monkeypatch.setattr(coding, '_execute', lambda *_args: pytest.fail('Codex must not run again'))
    result = coding.implement_change(task_id, {'coding_request': ''}, agent_id='job_hunter', auto_integrate=True)
    assert result['integrated'] and result['plain_summary'] == 'Une valeur a été corrigée.'
    assert git('status', '--porcelain', '--untracked-files=no') == ''
    assert not (worktree/'.jules-complete.json').exists()
    assert len(calls) == 1


def test_autonomous_worktree_resumes_after_branch_commit(repo, monkeypatch):
    root, git = repo
    monkeypatch.setattr(coding, 'codex_usage_percent', lambda *_: 12)
    monkeypatch.setattr(coding, '_integration_checks', lambda *_args, **_kwargs: 'focused tests')
    def execute(command, directory, prompt, env):
        target = directory/'internships_project/city_sample.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('value = 2\n')
        Path(command[command.index('--output-last-message') + 1]).write_text(json.dumps(
            {'summary': 'Une valeur a été corrigée.', 'tests': 'Test ciblé réussi.', 'limitations': 'Aucune.'}))
        (root/'sample.py').write_text('value = 9\n')
        return [{'type': 'turn.completed'}]
    monkeypatch.setattr(coding, '_execute', execute)
    task_id = 'f'*32
    with pytest.raises(CityError, match='modifications locales suivies'):
        coding.implement_change(task_id, {'coding_request': ''}, agent_id='job_hunter', auto_integrate=True)
    directory = root/'.city-worktrees'/task_id
    coding.git(directory, 'add', '--', 'internships_project/city_sample.py')
    coding.git(directory, '-c', 'commit.gpgsign=false', 'commit', '-m', 'Improve MarketDesk with job_hunter')
    (root/'sample.py').write_text('value = 1\n')
    monkeypatch.setattr(coding, '_execute', lambda *_args: pytest.fail('Codex must not run again'))
    result = coding.implement_change(task_id, {'coding_request': ''}, agent_id='job_hunter', auto_integrate=True)
    assert result['integrated'] and result['commit'] == git('rev-parse', 'HEAD')
    assert 'internships_project/city_sample.py' in result['files']


def test_resume_does_not_mistake_same_agent_base_commit_for_current_work(repo, monkeypatch):
    root, git = repo
    source = root/'internships_project/city_sample.py'
    source.parent.mkdir(parents=True)
    source.write_text('value = 1\n')
    git('add', 'internships_project/city_sample.py')
    git('-c', 'commit.gpgsign=false', 'commit', '-m', 'Improve MarketDesk with city_ui_engineer')
    task_id = 'b'*32
    branch = 'marketdesk/city-ui-engineer-'+task_id[:12]
    directory = root/'.city-worktrees'/task_id
    coding.git(root, 'worktree', 'add', '-b', branch, directory.relative_to(root).as_posix(), 'HEAD')
    (directory/'internships_project/city_sample.py').write_text('value = 2\n')
    (directory/'tests/test_city_sample.py').write_text('def test_value():\n    assert True\n')
    (directory/'.jules-complete.json').write_text(json.dumps(
        {'summary': 'Valeur corrigée.', 'tests': 'Test réussi.', 'limitations': 'Aucune.'}))
    (root/'sample.py').write_text('value = 3\n')
    git('add', 'sample.py')
    git('-c', 'commit.gpgsign=false', 'commit', '-m', 'Other agent')
    monkeypatch.setattr(coding, '_integration_checks', lambda *_args, **_kwargs: 'focused tests')
    result = coding.implement_change(task_id, {'coding_request': ''},
                                    agent_id='city_ui_engineer', auto_integrate=True)
    assert result['integrated'] and result['rebased']
    assert set(result['files']) == {'internships_project/city_sample.py', 'tests/test_city_sample.py'}
    assert source.read_text() == 'value = 2\n'


def test_dirty_main_requeues_development_and_retry_keeps_task_id(store, monkeypatch):
    task = store.create_task('alice', 'job_hunter', 'Développement autonome', {'operation': 'develop'})
    def blocked(*_args, **_kwargs):
        raise CityError('Intégration suspendue : le dépôt courant contient des modifications locales suivies.')
    monkeypatch.setattr(coding, 'implement_change', blocked)
    assert CityWorker(store).run_once()
    with store.db() as db:
        status, scheduled = db.execute('SELECT status,scheduled_at FROM city_tasks WHERE id=?',
                                       (task['id'],)).fetchone()
    assert status == 'queued' and scheduled > task['created_at']
    with store.db() as db:
        db.execute("UPDATE city_tasks SET status='failed',error='Temporary failure' WHERE id=?", (task['id'],))
    retried = store.retry_task('alice', task['id'])
    assert retried['id'] == task['id'] and retried['status'] == 'queued'
    with store.db() as db:
        assert db.execute('SELECT scheduled_at FROM city_tasks WHERE id=?', (task['id'],)).fetchone()[0] is None


def test_coding_history_is_private_compact_and_keeps_full_detail(store):
    task = store.create_task('alice', 'job_hunter', 'Corriger une date', {'operation': 'develop'})
    store.claim_next()
    store.progress(task['id'], 'Tests ciblés réussis ; intégration en cours.')
    store.finish(task['id'], result={'plain_summary': 'Date corrigée.', 'integrated': True,
                                    'files': ['internships_project/city_services.py'], 'diff': 'large diff'})
    history = store.coding_history('alice')
    assert len(history['tasks']) == 1
    assert history['tasks'][0]['result']['plain_summary'] == 'Date corrigée.'
    assert 'diff' not in history['tasks'][0]['result']
    assert any(event['task_id'] == task['id'] and 'Tests ciblés' in event['message'] for event in history['events'])
    assert store.coding_history('bob')['tasks'] == []
    assert store.task_detail('bob', task['id']) is None
    assert store.task_detail('alice', task['id'])['result']['diff'] == 'large diff'

    duplicate = store.create_task('alice', 'city_ui_engineer', 'Corriger les dates', {'operation': 'develop'})
    store.claim_next()
    store.finish(duplicate['id'], result={'plain_summary': 'Correction déjà présente dans le projet.',
                                          'already_present': True, 'files': []})
    compact = next(task for task in store.coding_history('alice')['tasks'] if task['id'] == duplicate['id'])
    assert compact['result']['already_present'] is True


def test_automatic_coding_history_is_shared_but_manual_work_stays_private(store):
    automatic = store.create_task('alice', 'job_hunter', 'Améliorer City',
                                  {'operation': 'develop', 'period': '2026-11-07'})
    store.claim_next()
    store.progress(automatic['id'], 'Tests ciblés en cours.')
    store.finish(automatic['id'], result={'plain_summary': 'City améliorée.', 'integrated': True})
    manual = store.create_task('alice', 'job_hunter', 'Demande privée',
                               {'operation': 'code_change', 'request': 'Corriger un bouton dans City.'})
    with store.db() as db:
        db.execute('INSERT INTO city_specialist_schedule VALUES(?,?,?,?)',
                   ('alice', 'develop:job_hunter:1', '2026-11-07', automatic['id']))
    history = store.coding_history('bob')
    assert [task['id'] for task in history['tasks']] == [automatic['id']]
    assert any(event['task_id'] == automatic['id'] and event['message'] == 'Tests ciblés en cours.'
               for event in history['events'])
    assert store.task_detail('bob', automatic['id'])['description'] == 'Améliorer City'
    assert store.task_detail('bob', manual['id']) is None


def test_coding_history_distinguishes_integrated_from_live(store):
    task = store.create_task('alice', 'job_hunter', 'Corriger un affichage', {'operation': 'develop'})
    store.claim_next()
    store.finish(task['id'], result={'integrated': True, 'commit': 'abc123', 'files': ['internships_project/city_services.py']})
    store.active_revision = 'older'
    store.active_commits = {'older'}
    assert store.coding_history('alice')['tasks'][0]['result']['live'] is False
    store.active_revision = 'newer'
    store.active_commits = {'older', 'abc123', 'newer'}
    assert store.coding_history('alice')['tasks'][0]['result']['live'] is True


def test_stale_completed_codex_work_is_requeued_without_another_call(store, tmp_path, monkeypatch):
    from internships_project import city_specialists
    monkeypatch.setattr(city_specialists, 'repo_root', lambda: tmp_path)
    task = store.create_task('alice', 'job_hunter', 'Corriger un affichage', {'operation': 'develop'})
    store.claim_next()
    marker = tmp_path / '.city-worktrees' / task['id'] / '.jules-complete.json'
    marker.parent.mkdir(parents=True)
    marker.write_text('{}', encoding='utf-8')
    with store.db() as db:
        db.execute("UPDATE city_tasks SET heartbeat_at='2020-01-01T00:00:00+00:00' WHERE id=?", (task['id'],))
    assert store.recover_stale() == 1
    with store.db() as db:
        recovered = db.execute('SELECT status,retry_count FROM city_tasks WHERE id=?', (task['id'],)).fetchone()
    assert tuple(recovered) == ('queued', 1)


def test_parallel_coding_claims_are_bounded_per_agent_and_globally(store):
    from internships_project.city_specialists import VERSION
    for user in ('alice', 'bob'):
        store.ensure_agents(user)
        with store.db() as db:
            db.execute('INSERT INTO city_settings(username,settings_json,updated_at) VALUES(?,?,?)',
                       (user, json.dumps({'max_concurrent_tasks': 4, 'auto_tasks': True}),
                        '2026-11-04T00:00:00+00:00'))
    jobs = [('alice', 'job_hunter'), ('alice', 'city_ui_engineer'),
            ('alice', 'job_hunter'), ('bob', 'quality_engineer'),
            ('bob', 'internships_engineer'), ('bob', 'city_ui_engineer')]
    with store.db() as db:
        for index, (user, agent) in enumerate(jobs):
            db.execute("INSERT INTO city_tasks(id,username,agent_id,task_type,description,status,created_at,parameters_json) "
                       "VALUES(?,?,?,?,?,'queued',?,?)",
                       (format(index + 1, '032x'), user, agent, 'agent:'+agent,
                        'Développement autonome', f'2026-11-04T00:00:0{index}+00:00',
                        json.dumps({'operation': 'develop', 'role_version': VERSION})))
    claimed = [store.claim_next() for _ in range(4)]
    assert [job['agent_id'] for job in claimed] == [
        'job_hunter', 'city_ui_engineer', 'quality_engineer', 'internships_engineer']
    assert store.claim_next() is None
    store.finish(claimed[0]['id'], result={'title': 'Done', 'text': 'Done'})
    assert store.claim_next()['id'] == format(3, '032x')


@pytest.mark.parametrize('reason', [
    'Quota Codex indisponible : missions de développement suspendues.',
    'Connecte Codex avec ton abonnement ChatGPT : codex login. Aucun repli sur une clé API.',
])
def test_unavailable_codex_quota_defers_coding_without_losing_mission(store, monkeypatch, reason):
    task = store.create_task('alice', 'job_hunter', 'Développement autonome',
                             {'operation': 'develop'})
    def unavailable(*args, **kwargs):
        raise CityError(reason)
    monkeypatch.setattr(coding, 'implement_change', unavailable)
    assert CityWorker(store).run_once()
    with store.db() as db:
        status, scheduled = db.execute('SELECT status,scheduled_at FROM city_tasks WHERE id=?',
                                       (task['id'],)).fetchone()
    assert status == 'queued' and scheduled > task['created_at']
    assert store.claim_next() is None


def test_daily_codex_budget_retries_on_next_paris_day(store, monkeypatch):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    task = store.create_task('alice', 'job_hunter', 'Développement autonome', {'operation': 'develop'})
    monkeypatch.setattr(coding, 'implement_change', lambda *_args, **_kwargs: (
        (_ for _ in ()).throw(CityError('Développement reporté : budget Codex quotidien atteint.'))))
    assert CityWorker(store).run_once()
    with store.db() as db:
        status, scheduled = db.execute('SELECT status,scheduled_at FROM city_tasks WHERE id=?',
                                       (task['id'],)).fetchone()
    tomorrow = datetime.now(ZoneInfo('Europe/Paris')).date() + timedelta(days=1)
    assert status == 'queued'
    assert datetime.fromisoformat(scheduled).astimezone(ZoneInfo('Europe/Paris')).date() == tomorrow


def test_market_collection_without_data_is_retried(store, monkeypatch):
    from internships_project import city_services
    def unavailable():
        raise CityError("Markets n'a retourné aucune observation exploitable.")
    monkeypatch.setattr(city_services, 'market_brief', unavailable)
    task = store.create_task('alice', 'market_analyst', 'Brief quotidien des marchés',
                             {'operation': 'collect_markets'}, auto_run=True)
    assert CityWorker(store).run_once()
    with store.db() as db:
        status, scheduled = db.execute('SELECT status,scheduled_at FROM city_tasks WHERE id=?',
                                       (task['id'],)).fetchone()
    assert status == 'queued' and scheduled > task['created_at']


def test_internships_gate_uses_offline_tests_and_names_a_failure(repo, monkeypatch):
    root, _ = repo
    (root/'tests/test_internships_start_dates.py').write_text('def test_dates():\n    assert True\n')
    target = root/'tests/test_internships_weekly_dates.py'
    target.write_text('def test_weekly():\n    assert True\n')
    original_run = subprocess.run
    commands = []
    def run(command, **kwargs):
        if command[:2] == [sys.executable, '-c']:
            commands.append(command[2])
            return SimpleNamespace(returncode=1,
                                   stdout='FAILED tests\\test_internships_weekly_dates.py::test_weekly\n')
        return original_run(command, **kwargs)
    monkeypatch.setattr(coding.subprocess, 'run', run)
    with pytest.raises(CityError, match='test_internships_weekly_dates.py::test_weekly'):
        coding._integration_checks(root, root, ['tests/test_internships_weekly_dates.py'],
                                   'internships_engineer')
    assert 'tests/test_internships_weekly_dates.py' in commands[0]
    assert 'tests/test_internships.py' not in commands[0]
    assert 'tests/test_internships_location_filters.py' not in commands[0]
    basetemp = re.search(r"--basetemp=([^']+)", commands[0])
    assert basetemp and Path(basetemp.group(1)).is_relative_to(tempfile.gettempdir())
    assert not Path(basetemp.group(1)).is_relative_to(root)


def test_autonomous_engineer_rebases_after_another_mission_integrates(repo, monkeypatch):
    root, git = repo
    monkeypatch.setattr(coding, 'codex_usage_percent', lambda *_: 12)
    original_run = subprocess.run
    def run(command, **kwargs):
        if command[:2] == [sys.executable, '-c']:
            return SimpleNamespace(returncode=0)
        return original_run(command, **kwargs)
    monkeypatch.setattr(coding.subprocess, 'run', run)
    def execute(command, directory, prompt, env):
        (root/'other.py').write_text('other = True\n')
        git('add', 'other.py')
        git('-c', 'commit.gpgsign=false', 'commit', '-m', 'Other agent')
        target = directory/'internships_project/city_sample.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('value = 2\n')
        Path(command[command.index('--output-last-message') + 1]).write_text(json.dumps(
            {'summary': 'Source corrigée', 'tests': 'Test ciblé passé', 'limitations': 'Aucune'}))
        return [{'type': 'turn.completed'}]
    monkeypatch.setattr(coding, '_execute', execute)
    result = coding.implement_change('d'*32, {'coding_request': ''},
                                    agent_id='internships_engineer', auto_integrate=True)
    assert result['integrated'] and result['commit'] == git('rev-parse', 'HEAD')
    assert result['rebased'] and 'adaptée' in result['base_note']
    assert (root/'other.py').exists() and (root/'internships_project/city_sample.py').exists()


def test_parallel_conflict_keeps_main_and_branch_for_review(repo, monkeypatch):
    root, git = repo
    target = root/'internships_project/city_sample.py'
    target.parent.mkdir(parents=True)
    target.write_text('value = 1\n')
    git('add', 'internships_project/city_sample.py')
    git('-c', 'commit.gpgsign=false', 'commit', '-m', 'Baseline')
    monkeypatch.setattr(coding, 'codex_usage_percent', lambda *_: 12)
    original_run = subprocess.run
    def run(command, **kwargs):
        if command[:2] == [sys.executable, '-c']:
            return SimpleNamespace(returncode=0)
        return original_run(command, **kwargs)
    monkeypatch.setattr(coding.subprocess, 'run', run)
    def execute(command, directory, prompt, env):
        target.write_text('value = 3\n')
        git('add', 'internships_project/city_sample.py')
        git('-c', 'commit.gpgsign=false', 'commit', '-m', 'Other agent')
        (directory/'internships_project/city_sample.py').write_text('value = 2\n')
        Path(command[command.index('--output-last-message') + 1]).write_text(json.dumps(
            {'summary': 'Source corrigée', 'tests': 'Test ciblé passé', 'limitations': 'Conflit'}))
        return [{'type': 'turn.completed'}]
    monkeypatch.setattr(coding, '_execute', execute)
    with pytest.raises(CityError, match='conflit'):
        coding.implement_change('e'*32, {'coding_request': ''},
                                agent_id='internships_engineer', auto_integrate=True)
    assert target.read_text() == 'value = 3\n'
    assert git('status', '--porcelain', '--untracked-files=no') == ''
    assert (root/'.city-worktrees'/('e'*32)/'internships_project/city_sample.py').read_text() == 'value = 2\n'


def test_coding_uses_approved_revision_despite_new_commits_and_dirty_main(repo,monkeypatch):
    root,git=repo
    proposal=coding.change_proposal('Corrige sample pour renvoyer deux')
    (root/'sample.py').write_text('value = 9\n')
    git('add','sample.py');git('-c','commit.gpgsign=false','commit','-m','changed')
    current=git('rev-parse','HEAD')
    revisions=[current]
    (root/'sample.py').write_text('uncommitted = True\n')
    def execute(command,directory,*args):
        assert (directory/'sample.py').read_text()=='value = 1\n'
        (root/'parallel.py').write_text('other_change = True\n')
        git('add','parallel.py');git('-c','commit.gpgsign=false','commit','-m','Concurrent City update')
        revisions.append(git('rev-parse','HEAD'))
        (directory/'sample.py').write_text('value = 2\n')
        Path(command[command.index('--output-last-message')+1]).write_text(json.dumps(
            {'summary':'Valeur corrigée','tests':'Analyse fixture','limitations':'Revue nécessaire'}))
        return [{'type':'turn.completed'}]
    monkeypatch.setattr(coding,'_execute',execute)
    result=coding.implement_change('b'*32,proposal)
    assert result['base_revision']==proposal['revision']
    assert result['current_revision']==revisions[-1] and revisions[-1]!=current and not result['base_is_current']
    assert result['working_tree_dirty']
    assert (root/'sample.py').read_text()=='uncommitted = True\n'
    assert git('rev-parse','HEAD')==revisions[-1]
    assert 'avant intégration' in result['text']


def test_missing_approved_commit_blocks_without_codex(repo,monkeypatch):
    monkeypatch.setattr(coding,'_execute',lambda *args:pytest.fail('Must not execute'))
    with pytest.raises(CityError,match='plus disponible'):
        coding.implement_change('a'*32,{'coding_request':'Corrige sample pour renvoyer deux','revision':'f'*40})


def test_failed_approved_branch_retries_with_same_identity(repo,store,monkeypatch):
    root,git=repo
    monkeypatch.setattr(specialists,'repo_root',lambda:root)
    audit={'revision':git('rev-parse','HEAD'),'role_version':2,'approval_required':True}
    monkeypatch.setattr(specialists,'repository_audit',lambda:audit)
    source=store.create_task('alice','job_hunter','Audit',{'operation':'repository_audit'})
    worker=CityWorker(store);assert worker.run_once()
    prepared=store.review_specialist_proposal('alice',source['id'],True)['task_id']
    original=specialists.prepare_branch
    def stale(*args):raise CityError('Le dépôt a changé : demande une nouvelle revue à Jules.')
    monkeypatch.setattr(specialists,'prepare_branch',stale)
    assert worker.run_once()
    with pytest.raises(CityError):store.retry_task('bob',prepared)
    monkeypatch.setattr(specialists,'prepare_branch',original)
    (root/'sample.py').write_text('value = 9\n')
    git('add','sample.py');git('-c','commit.gpgsign=false','commit','-m','new version')
    retried=store.retry_task('alice',prepared)
    assert retried['id']==prepared and retried['reused_approval']
    assert worker.run_once()
    done=next(t for t in store.snapshot('alice')['tasks'] if t['id']==prepared)
    assert done['status']=='completed',done.get('error')
    assert done['result']['base_revision']==audit['revision']
    assert not done['result']['base_is_current']
    assert (root/'sample.py').read_text()=='value = 9\n'
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM city_tasks WHERE username='alice'").fetchone()[0]==2


def test_branch_retry_does_not_create_human_approval(store):
    task=store.create_task('alice','job_hunter','Préparer une branche',{'operation':'prepare_branch','source_task_id':'missing'})
    assert store.claim_next()['id']==task['id']
    store.finish(task['id'],error='No approval')
    with pytest.raises(CityError,match='explicitement validée'):store.retry_task('alice',task['id'])
    assert store.snapshot('alice')['tasks'][0]['status']=='failed'


def test_codex_without_edits_is_a_blocked_mission(repo,monkeypatch):
    root,_=repo
    proposal=coding.change_proposal('Corrige sample pour renvoyer deux')
    def no_edits(command,directory,*args):
        Path(command[command.index('--output-last-message')+1]).write_text(json.dumps(
            {'summary':'Aucun changement','tests':'Aucun test','limitations':'Outils indisponibles'}))
        return [{'type':'turn.completed'}]
    monkeypatch.setattr(coding,'_execute',no_edits)
    with pytest.raises(CityError,match='aucun changement'):coding.implement_change('d'*32,proposal)


def test_codex_review_proposes_from_source_without_writes_or_code_execution(repo,monkeypatch):
    root,git=repo
    source=root/'internships_project/city_example.py';source.parent.mkdir()
    source.write_text('def display():\n    return []\n')
    git('add',str(source.relative_to(root)));git('-c','commit.gpgsign=false','commit','-m','City source')
    revision=git('rev-parse','HEAD')
    def review(command,directory,prompt,env):
        assert command[command.index('--sandbox')+1]=='read-only'
        assert 'features.shell_tool=false' in command
        assert 'city_example.py' in prompt and 'def display' in prompt
        assert 'OPENAI_API_KEY' not in env
        Path(command[command.index('--output-last-message')+1]).write_text(json.dumps({
            'summary':'Améliorer le résultat vide','request':'Ajoute une explication au résultat vide et un test.',
            'evidence':'internships_project/city_example.py retourne []','limitations':'Extraits seulement'}))
        return [{'type':'turn.completed','usage':{'input_tokens':20}}]
    monkeypatch.setattr(coding,'_execute',review)
    result=coding.review_repository()
    assert result['revision']==revision and result['coding_request'].startswith('Ajoute')
    assert result['approval_required'] and 'branch' not in result
    assert result['reviewed_files']==['internships_project/city_example.py']
    assert git('status','--porcelain','--untracked-files=no')==''


def test_coding_http_auth_payload_and_manager_preserve_user_request(store):
    app=FastAPI();add_city_routes(app,lambda r:r.headers.get('x-user'),store,CityWorker(store))
    headers={'x-user':'alice','X-MarketDesk-City':'1'}
    request='Ajoute un filtre aux stages affichés'
    with TestClient(app) as client:
        assert client.post('/city/api/develop/city_ui_engineer', json={}).status_code == 401
        assert client.get('/city/api/coding-history').status_code == 401
        assert client.get('/city/api/coding-history', headers=headers).status_code == 200
        assert client.post('/city/api/develop/city_ui_engineer', headers={'x-user':'alice'}, json={}).status_code == 403
        assert client.post('/city/api/develop/unknown', headers=headers, json={}).status_code == 404
        for agent_id in AGENT_BY_ID:
            response = client.post(f'/city/api/develop/{agent_id}', headers=headers, json={})
            assert response.status_code == 201, (agent_id, response.text)
            assert store.cancel_queued('alice', response.json()['task']['id'])
        autonomous = client.post('/city/api/develop/city_ui_engineer', headers=headers, json={})
        assert autonomous.status_code == 201
        task_id = autonomous.json()['task']['id']
        assert client.get(f'/city/api/tasks/{task_id}', headers=headers).status_code == 200
        assert client.get(f'/city/api/tasks/{task_id}', headers={'x-user':'bob'}).status_code == 404
        assert store.cancel_queued('alice', autonomous.json()['task']['id'])
        assert client.post('/city/api/jules/change',json={'request':request}).status_code==401
        assert client.post('/city/api/jules/change',headers={'x-user':'alice'},json={'request':request}).status_code==403
        assert client.post('/city/api/jules/change',headers=headers,json={'request':request,'shell':'test'}).status_code==400
        response=client.post('/city/api/jules/change',headers=headers,json={'request':request})
        assert response.status_code==201
        assert client.post('/city/api/jules/review',json={}).status_code==401
        assert client.post('/city/api/jules/review',headers=headers,json={'operation':'prepare_branch'}).status_code==400
        assert client.post('/city/api/jules/review',headers=headers,json={}).status_code==400
        assert store.cancel_queued('alice',response.json()['task']['id'])
        response=client.post('/city/api/jules/review',headers=headers,json={})
        assert response.status_code==201,response.json()
    tool=build_agent('desk_manager',TestModel())._function_toolset.tools['start_specialist_mission'].function
    asyncio.run(tool(SimpleNamespace(deps=ChatDeps('bob',store,current_message=request)),'Jules','code_change'))
    with store.db() as db:
        params=json.loads(db.execute("SELECT parameters_json FROM city_tasks WHERE username='bob'").fetchone()[0])
    assert params['request']==request


def test_market_agent_development_uses_codex_runner_not_market_collector(store, monkeypatch):
    from internships_project import city_coding
    called = []
    def implement(task_id, proposal, *, agent_id, auto_integrate, on_progress=None):
        called.append((agent_id, auto_integrate))
        if on_progress:
            on_progress('Tests ciblés réussis ; intégration de la branche en cours.')
        return {'title': 'Développement intégré', 'integrated': True, 'commit': 'fixture', 'text': 'Tests validés'}
    monkeypatch.setattr(city_coding, 'implement_change', implement)
    task = store.create_task('alice', 'market_analyst', 'Améliorer Markets',
                             {'operation': 'develop', 'request': 'Améliore le collecteur Markets'}, auto_run=True)
    assert CityWorker(store).run_once()
    result = next(row for row in store.snapshot('alice')['tasks'] if row['id'] == task['id'])
    assert result['status'] == 'completed' and called == [('market_analyst', True)]
    assert any(event['task_id'] == task['id'] and 'Tests ciblés' in event['message']
               for event in store.snapshot('alice')['events'])


def test_supervised_worker_drains_after_integrating_code(store, monkeypatch):
    from internships_project import city_coding
    monkeypatch.setenv('MARKETDESK_CITY_SUPERVISED', '1')
    monkeypatch.setattr(city_coding, 'implement_change', lambda *_args, **_kwargs:
                        {'integrated': True, 'commit': 'fixture'})
    store.create_task('alice', 'job_hunter', 'Améliorer City', {'operation': 'develop'}, auto_run=True)
    worker = CityWorker(store)
    assert worker.run_once()
    assert worker._stop.is_set()


def test_codex_failure_and_missing_completion_never_report_success(monkeypatch,tmp_path):
    class Process:
        returncode=1
        def communicate(self,*args,**kwargs):return ('private output','private error')
    monkeypatch.setattr(subprocess,'Popen',lambda *args,**kwargs:Process())
    with pytest.raises(CityError,match='pas terminé') as exc:coding._execute(['codex'],tmp_path,'task',{})
    assert 'private' not in str(exc.value)
    Process.returncode=0
    with pytest.raises(CityError,match='pas confirmé'):coding._execute(['codex'],tmp_path,'task',{})
