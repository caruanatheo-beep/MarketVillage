"""Recover missed GitHub schedules using the existing Windows Git credential."""
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / '.venv/Lib/site-packages')]
from scripts.internships_refresh_window import collection_window_open

REPOSITORY = 'caruanatheo-beep/Internships-Offres'
SNAPSHOT = 'https://caruanatheo-beep.github.io/Internships-Offres/offers.json'
WORKFLOW = f'/repos/{REPOSITORY}/actions/workflows/pages.yml'


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z','+00:00'))
        return parsed if parsed.tzinfo is not None else None
    except (ValueError,TypeError,AttributeError):
        return None


def recovery_status(now, updated, runs):
    if not collection_window_open(now):
        return 'outside_collection_window'
    published = timestamp(updated)
    if published and 0 <= (now-published).total_seconds() < 60*60:
        return 'fresh'
    active = {'queued','in_progress','waiting','pending','requested'}
    if any(run.get('status') in active for run in runs):
        return 'workflow_active'
    for run in runs:
        created = timestamp(run.get('created_at'))
        if created and (now-created).total_seconds() < 15*60:
            return 'retry_cooldown'
    return 'recovery_needed'


def github_credential():
    result = subprocess.run(['git','-c','credential.interactive=never','credential','fill'],
        input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,
        timeout=20,cwd=ROOT,
        env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'Never'},
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    values = dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    if result.returncode or not values.get('password'):
        raise RuntimeError('Existing Windows GitHub credential unavailable')
    return values['password']


def github_request(path, token, *, payload=None):
    # Fixed host and no redirects: the credential never reaches the public site.
    connection = http.client.HTTPSConnection('api.github.com',timeout=20)
    headers = {'Accept':'application/vnd.github+json','User-Agent':'MarketDesk-refresh-watchdog',
               'Authorization':'Bearer '+token,'X-GitHub-Api-Version':'2022-11-28'}
    data = None if payload is None else json.dumps(payload).encode()
    if data is not None:
        headers['Content-Type'] = 'application/json'
    try:
        connection.request('GET' if payload is None else 'POST',path,body=data,headers=headers)
        response = connection.getresponse()
        body = response.read()
        if not 200 <= response.status < 300:
            raise RuntimeError(f'GitHub API failed (HTTP {response.status})')
        return json.loads(body) if body else {}
    finally:
        connection.close()


def check(now, *, recover=False):
    if not collection_window_open(now):
        return {'status':'outside_collection_window'}
    updated = ''
    try:
        request = Request(SNAPSHOT+'?watchdog='+str(int(now.timestamp())),
                          headers={'Cache-Control':'no-cache','User-Agent':'MarketDesk-refresh-watchdog'})
        with urlopen(request,timeout=15) as response:
            updated = json.load(response).get('updated','')
    except (OSError,ValueError,AttributeError):
        pass  # Still inspect GitHub before deciding whether recovery is needed.
    status = recovery_status(now,updated,[])
    if status == 'fresh':
        return {'status':status,'published_updated':updated}
    token = github_credential()
    data = github_request(WORKFLOW+'/runs?per_page=10',token)
    runs = data.get('workflow_runs')
    if not isinstance(runs,list):
        raise RuntimeError('GitHub workflow state unavailable')
    status = recovery_status(now,updated,runs)
    if status == 'recovery_needed' and recover:
        github_request(WORKFLOW+'/dispatches',token,
                       payload={'ref':'main','inputs':{'recovery':True}})
        status = 'recovery_dispatched'
    return {'status':status,'published_updated':updated}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recover',action='store_true',help='Dispatch only if stale, open and idle')
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    try:
        result = check(now,recover=args.recover)
        exit_code = 0
    except Exception as error:
        # HTTP/provider/credential output can contain private details.
        result = {'status':'check_failed','error_type':type(error).__name__}
        exit_code = 1
    result['checked_at'] = now.isoformat()
    report = ROOT/'artifacts/internships-refresh-watchdog.json'
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
