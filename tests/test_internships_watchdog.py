"""Missed schedules recover once; fresh snapshots, active work and night stay quiet."""
from datetime import datetime,timedelta,timezone
import io
import json

import pytest

from scripts import internships_refresh_watchdog as watchdog
from scripts import internships_refresh_window as window

NOW=datetime(2026,11,16,18,30,tzinfo=timezone.utc)


@pytest.mark.parametrize('minutes,expected',[(0,'fresh'),(59,'fresh'),(60,'recovery_needed'),(120,'recovery_needed')])
def test_freshness_threshold(minutes,expected):
    assert watchdog.recovery_status(NOW,(NOW-timedelta(minutes=minutes)).isoformat(),[]) == expected


def test_closed_window_never_recovers():
    assert watchdog.recovery_status(NOW.replace(hour=5),'',[]) == 'outside_collection_window'


@pytest.mark.parametrize('status',['queued','in_progress','waiting','pending','requested'])
def test_existing_work_prevents_duplicate_dispatch(status):
    assert watchdog.recovery_status(NOW,'',[{'status':status}]) == 'workflow_active'


def test_recent_failed_run_gets_a_cooldown():
    run={'status':'completed','conclusion':'failure','created_at':(NOW-timedelta(minutes=5)).isoformat()}
    assert watchdog.recovery_status(NOW,'',[run]) == 'retry_cooldown'
    run['created_at']=(NOW-timedelta(minutes=20)).isoformat()
    assert watchdog.recovery_status(NOW,'',[run]) == 'recovery_needed'


@pytest.mark.parametrize('recover,active,expected',[(False,False,'recovery_needed'),(True,False,'recovery_dispatched'),(True,True,'workflow_active')])
def test_dispatch_uses_recovery_mode_only_when_requested_and_idle(monkeypatch,recover,active,expected):
    monkeypatch.setattr(watchdog,'urlopen',lambda *a,**k:io.BytesIO(b'{"updated":"2026-11-16T12:00:00+00:00"}'))
    monkeypatch.setattr(watchdog,'github_credential',lambda:'test credential')
    dispatched=[]
    def request(path,token,*,payload=None):
        if payload is not None:
            dispatched.append((path,payload))
            return {}
        return {'workflow_runs':[{'status':'in_progress'}] if active else []}
    monkeypatch.setattr(watchdog,'github_request',request)
    assert watchdog.check(NOW,recover=recover)['status'] == expected
    assert bool(dispatched) is (recover and not active)
    if dispatched:
        assert dispatched[0] == (watchdog.WORKFLOW+'/dispatches',{'ref':'main','inputs':{'recovery':True}})


def test_fresh_publication_needs_no_credential_or_api_request(monkeypatch):
    payload=json.dumps({'updated':NOW.isoformat()}).encode()
    monkeypatch.setattr(watchdog,'urlopen',lambda *a,**k:io.BytesIO(payload))
    monkeypatch.setattr(watchdog,'github_credential',lambda:pytest.fail('No credential needed'))
    assert watchdog.check(NOW,recover=True)['status'] == 'fresh'


@pytest.mark.parametrize('now,updated,active',[(NOW,NOW.isoformat(),False),(NOW,'2026-11-16T12:00:00+00:00',True),(NOW.replace(hour=5),'',False)])
def test_recovery_dispatch_rechecks_window_and_freshness_on_github(tmp_path,monkeypatch,now,updated,active):
    monkeypatch.setenv('GITHUB_EVENT_NAME','workflow_dispatch')
    monkeypatch.setenv('INTERNSHIPS_RECOVERY','true')
    monkeypatch.setenv('PUBLIC_OFFERS_URL','https://example.invalid/offers.json')
    output=tmp_path/'output'
    monkeypatch.setenv('GITHUB_OUTPUT',str(output))
    monkeypatch.setattr(window,'urlopen',lambda *a,**k:io.BytesIO(json.dumps({'updated':updated}).encode()))
    window.main(now)
    assert output.read_text().strip() == f'active={str(active).lower()}'
