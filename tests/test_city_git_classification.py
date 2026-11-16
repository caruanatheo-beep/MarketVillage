"""Permanent Git validation failures must not masquerade as temporary outages."""
import subprocess
from types import SimpleNamespace

import pytest

from internships_project import city_coding, city_specialists as services, state_store
from internships_project.marketdesk_city import CityStore, CityWorker


@pytest.mark.parametrize('args,detail,category,retryable', [
    (('show', '--check', 'HEAD'), 'sample.py:9: new blank line at EOF.\nsecret-credential', 'validation', False),
    (('diff', '--check'), 'sample.py:3: trailing whitespace.', 'validation', False),
    (('add', '.'), "Unable to create 'index.lock': File exists", 'busy', True),
    (('add', '.'), "Unable to create 'index.lock': Permission denied", 'permission', False),
    (('apply', '--check', 'patch'), 'patch failed: sample.py:1', 'conflict', False),
    (('rev-parse', 'HEAD'), 'not a git repository; secret-credential', 'command', False),
])
def test_git_classifies_without_exposing_output(tmp_path, monkeypatch, args, detail, category, retryable):
    monkeypatch.setattr(services.subprocess, 'run', lambda *a, **kw: SimpleNamespace(
        returncode=2, stdout=detail, stderr='secret-credential'))
    with pytest.raises(services.CityGitError) as raised:
        services.git(tmp_path, *args)
    assert raised.value.category == category
    assert raised.value.retryable is retryable
    assert 'secret-credential' not in str(raised.value)


@pytest.mark.parametrize('failure,category', [(PermissionError(), 'permission'),
    (FileNotFoundError(), 'unavailable'), (subprocess.TimeoutExpired('git', 25), 'timeout')])
def test_git_startup_errors(tmp_path, monkeypatch, failure, category):
    def broken(*a, **kw): raise failure
    monkeypatch.setattr(services.subprocess, 'run', broken)
    with pytest.raises(services.CityGitError) as raised:
        services.git(tmp_path, 'status')
    assert raised.value.category == category


@pytest.mark.parametrize('args,retries',[(('ls-files','-z'),True),(('branch','--show-current'),True),(('commit','-m','test'),False)])
def test_only_read_only_git_timeouts_get_one_immediate_retry(tmp_path,monkeypatch,args,retries):
    calls=[]
    def execute(*a,**kwargs):
        calls.append(kwargs['timeout'])
        if len(calls)==1:raise subprocess.TimeoutExpired('git',kwargs['timeout'])
        return SimpleNamespace(returncode=0,stdout='verified',stderr='')
    monkeypatch.setattr(services.subprocess,'run',execute)
    if retries:
        assert services.git(tmp_path,*args)=='verified'
        assert calls==[25,60]
    else:
        with pytest.raises(services.CityGitError):services.git(tmp_path,*args)
        assert len(calls)==1


@pytest.mark.parametrize('category,status', [('validation','failed'), ('conflict','failed'),
    ('permission','failed'), ('command','failed'), ('busy','queued'), ('timeout','queued')])
def test_worker_only_retries_transient_git_errors(tmp_path, monkeypatch, category, status):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    task = store.create_task('alice', 'job_hunter', 'Améliorer City', {'operation': 'develop'})
    def broken(*a, **kw): raise services.CityGitError(category, 'Diagnostic sûr')
    monkeypatch.setattr(city_coding, 'implement_change', broken)
    assert CityWorker(store).run_once()
    detail = store.task_detail('alice', task['id'])
    assert detail['status'] == status
    assert bool(detail.get('scheduled_at')) == (status == 'queued')
    assert not CityWorker(store).run_once()


def test_cockpit_shares_automatic_coding_but_keeps_manual_requests_private(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'accounts.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    private = store.create_task('alice', 'city_ui_engineer', 'private-request-content', {'operation':'develop','request':'private-request-content'})
    assert store.claim_next()['id'] == private['id']
    store.finish(private['id'], result={'plain_summary':'private-request-content'})
    auto = store.create_task('alice', 'job_hunter', 'Mission automatique', {'operation':'develop','period':'2026-11-14'})
    with store.db() as db:
        db.execute('INSERT INTO city_specialist_schedule VALUES(?,?,?,?)',
                   ('alice','develop:job_hunter:1','2026-11-14',auto['id']))
    assert store.claim_next()['id'] == auto['id']
    visible = store.snapshot('bob')
    assert visible['tasks'] == []
    assert [t['id'] for t in visible['shared_coding_tasks']] == [auto['id']]
    assert visible['shared_coding_tasks'][0]['read_only']
    assert next(a for a in visible['agents'] if a['id']=='job_hunter')['status'] == 'running'
    assert 'private-request-content' not in str(visible)
    assert private['id'] not in str(visible)
    store.finish(auto['id'], result={'plain_summary':'Changement vérifié','integrated':True})
    visible = store.snapshot('bob')
    agent = next(a for a in visible['agents'] if a['id']=='job_hunter')
    assert agent['health']['last_success_at']
    assert agent['latest']['id'] == auto['id']
    assert agent['status'] == 'idle'
    latest_shared = max(event['id'] for event in visible['shared_coding_events'])
    assert store.notification_state('bob', latest_shared)['last_read_event_id'] == latest_shared
    assert store.notification_state('alice')['last_read_event_id'] == 0
    latest_shared = max(event['id'] for event in visible['shared_coding_events'])
    assert store.notification_state('bob', latest_shared)['last_read_event_id'] == latest_shared
    assert store.notification_state('alice')['last_read_event_id'] == 0
