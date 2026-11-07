"""Quota lookup must release missions even when the local CLI misbehaves."""
import io
import json
from queue import Queue
from types import SimpleNamespace

import pytest

from internships_project import city_coding as coding, state_store
from internships_project.marketdesk_city import CityError


@pytest.fixture
def cli(monkeypatch):
    process = SimpleNamespace(
        stdin=io.StringIO(), stdout=io.StringIO(), stopped=False, waited=False)
    process.poll = lambda: None

    def terminate():
        process.stopped = True

    def wait(timeout):
        process.waited = True

    process.terminate = terminate
    process.wait = wait
    monkeypatch.setattr(coding.subprocess, 'Popen', lambda *a, **kw: process)
    monkeypatch.setattr(coding.threading, 'Thread', lambda target, **kw:
                        SimpleNamespace(start=target))

    def replies(*messages):
        process.stdout = io.StringIO('\n'.join(json.dumps(m) for m in messages))

    process.replies = replies
    return process


@pytest.mark.parametrize('initialized', [False, True])
def test_notifications_do_not_extend_quota_deadline(cli, monkeypatch, initialized):
    now = [0.0]
    reads = []

    class NotificationQueue(Queue):
        def get(self, timeout):
            if initialized and not reads:
                reads.append('initialize')
                return json.dumps({'id': 1, 'result': {}})
            reads.append(timeout)
            # Fail quickly on the old implementation rather than hanging the test.
            assert len(reads) <= 5, 'notifications keep restarting the quota timeout'
            now[0] += 5
            return json.dumps({'method': 'account/rateLimits/updated'})

    monkeypatch.setattr(coding, 'Queue', NotificationQueue)
    monkeypatch.setattr(coding.time, 'monotonic', lambda: now[0])
    with pytest.raises(CityError, match='Quota Codex indisponible'):
        coding.codex_usage_percent('fixture-codex', {})
    assert reads == (['initialize'] if initialized else []) + [15, 10, 5]
    assert cli.stopped and cli.waited


@pytest.mark.parametrize('reply', [
    [], None, {'id': 2, 'result': None},
    {'id': 2, 'result': {'rateLimitsByLimitId': [], 'rateLimits': []}},
    {'id': 2, 'result': {'rateLimitsByLimitId': ['invalid']}},
])
def test_invalid_quota_uses_bounded_fallback_budget(cli, monkeypatch, tmp_path, reply):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'usage.sqlite3')
    cli.replies({'id': 1, 'result': {}}, reply)
    assert coding.require_daily_codex_budget('fixture-codex', {}) is None
    assert cli.stopped and cli.waited
    # Unavailable quotas must preserve the existing daily cap.
    for _ in range(coding.CODEX_DAILY_FALLBACK_CALLS - 1):
        cli.replies({'id': 1, 'result': {}}, reply)
        assert coding.require_daily_codex_budget('fixture-codex', {}) is None
    cli.replies({'id': 1, 'result': {}}, reply)
    with pytest.raises(CityError, match='budget Codex quotidien'):
        coding.require_daily_codex_budget('fixture-codex', {})


@pytest.mark.parametrize('limits', [
    {'rateLimits': {'secondary': {'windowDurationMins': 10080, 'usedPercent': 23}}},
    {'rateLimitsByLimitId': {'codex': {
        'primary': {'windowDurationMins': 300, 'usedPercent': 90},
        'secondary': {'windowDurationMins': 10080, 'usedPercent': 23}}}},
])
def test_quota_response_after_notifications(cli, limits):
    cli.replies({'method': 'ready'}, {'id': 1, 'result': {}},
                {'method': 'account/updated'}, {'id': 2, 'result': limits})
    assert coding.codex_usage_percent('fixture-codex', {}) == 23
    assert cli.stopped and cli.waited
    sent = [json.loads(line) for line in cli.stdin.getvalue().splitlines()]
    assert [message['method'] for message in sent] == [
        'initialize', 'initialized', 'account/rateLimits/read']
