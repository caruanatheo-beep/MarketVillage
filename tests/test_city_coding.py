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
        assert client.post('/city/api/develop/city_ui_engineer', headers={'x-user':'alice'}, json={}).status_code == 403
        assert client.post('/city/api/develop/unknown', headers=headers, json={}).status_code == 404
        for agent_id in AGENT_BY_ID:
            response = client.post(f'/city/api/develop/{agent_id}', headers=headers, json={})
            assert response.status_code == 201, (agent_id, response.text)
            assert store.cancel_queued('alice', response.json()['task']['id'])
        autonomous = client.post('/city/api/develop/city_ui_engineer', headers=headers, json={})
        assert autonomous.status_code == 201
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
    def implement(task_id, proposal, *, agent_id, auto_integrate):
        called.append((agent_id, auto_integrate))
        return {'title': 'Développement intégré', 'integrated': True, 'commit': 'fixture', 'text': 'Tests validés'}
    monkeypatch.setattr(city_coding, 'implement_change', implement)
    task = store.create_task('alice', 'market_analyst', 'Améliorer Markets',
                             {'operation': 'develop', 'request': 'Améliore le collecteur Markets'}, auto_run=True)
    assert CityWorker(store).run_once()
    result = next(row for row in store.snapshot('alice')['tasks'] if row['id'] == task['id'])
    assert result['status'] == 'completed' and called == [('market_analyst', True)]


def test_codex_failure_and_missing_completion_never_report_success(monkeypatch,tmp_path):
    class Process:
        returncode=1
        def communicate(self,*args,**kwargs):return ('private output','private error')
    monkeypatch.setattr(subprocess,'Popen',lambda *args,**kwargs:Process())
    with pytest.raises(CityError,match='pas terminé') as exc:coding._execute(['codex'],tmp_path,'task',{})
    assert 'private' not in str(exc.value)
    Process.returncode=0
    with pytest.raises(CityError,match='pas confirmé'):coding._execute(['codex'],tmp_path,'task',{})
