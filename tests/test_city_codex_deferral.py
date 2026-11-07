"""Temporary Codex unavailability must preserve every kind of City mission."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from internships_project import city_coding, state_store
from internships_project.city_specialists import VERSION
from internships_project.marketdesk_city import CityError, CityStore, CityWorker


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = tmp_path / 'codex-deferral.sqlite3'
    monkeypatch.setattr(state_store, 'USER_DB_PATH', path)
    return CityStore(path)


def create_mission(store, operation):
    request = 'Corrige la reprise des missions City.'
    if operation == 'prepare_branch':
        source = store.create_task('alice', 'job_hunter', 'Revue Codex',
                                   {'operation': 'codex_review'})
        assert store.claim_next()['id'] == source['id']
        store.finish(source['id'], result={
            'revision': 'a' * 40, 'coding_request': request,
            'approval_required': True, 'role_version': VERSION,
            'text': 'Une amélioration à approuver.',
        })
        task_id = store.review_specialist_proposal('alice', source['id'], True)['task_id']
        return store.task_detail('alice', task_id)
    parameters = {'operation': operation}
    if operation == 'code_change':
        parameters['request'] = request
    return store.create_task('alice', 'job_hunter', 'Mission Codex', parameters)


@pytest.mark.parametrize('operation,entrypoint', [
    ('develop', 'implement_change'),
    ('codex_review', 'review_repository'),
    ('code_change', 'change_proposal'),
    ('prepare_branch', 'implement_change'),
])
@pytest.mark.parametrize('reason', [
    'Quota Codex indisponible : missions de développement suspendues.',
    'Connecte Codex avec ton abonnement ChatGPT : codex login. Aucun repli sur une clé API.',
    'Développement reporté : budget Codex quotidien atteint.',
])
def test_codex_mission_resumes_after_temporary_unavailability(
        store, monkeypatch, operation, entrypoint, reason):
    task = create_mission(store, operation)
    worker = CityWorker(store)
    calls = []

    def execute(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == 1:
            raise CityError(reason)
        return {'text': 'Mission terminée après reprise.'}

    monkeypatch.setattr(city_coding, entrypoint, execute)
    with store.db() as db:
        before = db.execute('SELECT parameters_json FROM city_tasks WHERE id=?', (task['id'],)).fetchone()[0]
        approvals = [tuple(row) for row in db.execute('SELECT * FROM city_proposal_reviews')] if operation == 'prepare_branch' else []

    assert worker.run_once()
    with store.db() as db:
        deferred = db.execute('SELECT * FROM city_tasks WHERE id=?', (task['id'],)).fetchone()
    assert deferred['status'] == 'queued'
    assert deferred['parameters_json'] == before
    assert deferred['finished_at'] is None
    assert deferred['error'] is None
    scheduled = datetime.fromisoformat(deferred['scheduled_at'])
    if 'budget Codex quotidien' in reason:
        paris = ZoneInfo('Europe/Paris')
        assert scheduled.astimezone(paris).date() == datetime.now(paris).date() + timedelta(days=1)
        assert scheduled.astimezone(paris).hour == 0
    else:
        remaining = (scheduled - datetime.now(scheduled.tzinfo)).total_seconds()
        assert 3500 < remaining <= 3600
    assert not worker.run_once()
    assert len(calls) == 1
    assert reason in store.snapshot('alice')['events'][0]['message']

    # Make the scheduled retry due without changing its identity or approval.
    with store.db() as db:
        db.execute('UPDATE city_tasks SET scheduled_at=NULL WHERE id=?', (task['id'],))
    assert worker.run_once()
    assert len(calls) == 2
    assert store.task_detail('alice', task['id'])['status'] == 'completed'
    with store.db() as db:
        assert db.execute('SELECT COUNT(*) FROM city_tasks').fetchone()[0] == (2 if approvals else 1)
        if approvals:
            assert [tuple(row) for row in db.execute('SELECT * FROM city_proposal_reviews')] == approvals
            assert calls[0][0] == calls[1][0]


def test_codex_review_permanent_error_still_fails(store, monkeypatch):
    task = create_mission(store, 'codex_review')

    def invalid_report():
        raise CityError('La revue Codex n’a pas produit de proposition exploitable.')

    monkeypatch.setattr(city_coding, 'review_repository', invalid_report)
    assert CityWorker(store).run_once()
    assert store.task_detail('alice', task['id'])['status'] == 'failed'


def test_branch_without_approval_is_not_deferred_or_executed(store, monkeypatch):
    task = store.create_task('alice', 'job_hunter', 'Préparer une branche',
                             {'operation': 'prepare_branch', 'source_task_id': 'missing'})
    monkeypatch.setattr(city_coding, 'implement_change',
                        lambda *args, **kwargs: pytest.fail('Approval is required'))
    assert CityWorker(store).run_once()
    assert store.task_detail('alice', task['id'])['status'] == 'failed'


@pytest.mark.parametrize('cancel_timing', ['during_execution', 'after_deferral', None])
def test_project_deferral_respects_cancellation_and_resumes_dependencies(
        store, monkeypatch, cancel_timing):
    project = store.create_custom_workflow('alice', 'Correction City', 'Fiabilise City', [
        {'id': 'code', 'agent_id': 'job_hunter', 'operation': 'develop',
         'description': 'Corrige la reprise', 'depends_on': []},
        {'id': 'review', 'agent_id': 'developer', 'operation': 'daily_questions',
         'description': 'Prépare les questions', 'depends_on': ['code']},
    ])
    task_id, dependent_id = project['task_ids']
    calls = []

    def execute(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            assert store.workflow_details('alice', project['id'])['status'] == 'running'
            if cancel_timing == 'during_execution':
                assert store.cancel_workflow('alice', project['id'])
            raise CityError('Développement reporté : budget Codex quotidien atteint.')
        return {'text': 'Correction terminée.'}

    monkeypatch.setattr(city_coding, 'implement_change', execute)
    worker = CityWorker(store)
    assert worker.run_once()
    if cancel_timing == 'after_deferral':
        assert store.cancel_workflow('alice', project['id'])

    expected = 'cancelled' if cancel_timing else 'queued'
    assert store.workflow_details('alice', project['id'])['status'] == expected
    assert store.task_detail('alice', task_id)['status'] == expected
    assert store.task_detail('alice', dependent_id)['status'] == expected
    assert not worker.run_once()
    assert len(calls) == 1

    # Even once the delayed attempt is due, cancellation must remain final.
    with store.db() as db:
        db.execute('UPDATE city_tasks SET scheduled_at=NULL WHERE id=?', (task_id,))
    if cancel_timing:
        assert not worker.run_once()
        assert len(calls) == 1
        assert store.task_detail('alice', task_id)['finished_at']
        event = next(item for item in store.snapshot('alice')['events'] if item['task_id'] == task_id)
        assert event['status'] == 'cancelled'
        assert 'annul' in event['message'].lower()
    else:
        assert worker.run_once()
        assert len(calls) == 2
        dependent = store.claim_next()
        assert dependent['id'] == dependent_id
        store.finish(dependent_id, result={'text': 'Questions prêtes.'})
        assert store.workflow_details('alice', project['id'])['status'] == 'completed'
