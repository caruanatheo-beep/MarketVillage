"""Launch City locally and activate integrated commits when all missions are idle."""
import os
from pathlib import Path
import runpy
import sqlite3
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / '.venv' / 'Lib' / 'site-packages')]


def revision() -> str:
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True,
                            text=True, timeout=5, check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    from internships_project.city_worktree import activation_commits
    return result.stdout.strip() + ':' + ','.join(activation_commits(root))


def missions_running() -> bool:
    from dotenv import load_dotenv
    load_dotenv(root / '.env')
    from internships_project.state_store import USER_DB_PATH
    database = USER_DB_PATH.resolve()
    if not database.exists():
        return False
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=3) as db:
        return bool(db.execute("SELECT 1 FROM city_tasks WHERE status='running' LIMIT 1").fetchone())


def supervise() -> None:
    current = revision()
    child_env = {**os.environ, 'MARKETDESK_CITY_SUPERVISED': '1'}
    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--serve'], cwd=root,
                             env=child_env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    failures, started = 0, time.monotonic()
    try:
        while True:
            time.sleep(5)
            if child.poll() is not None:
                failures += 1
                if failures > 3:
                    raise RuntimeError('City ne redémarre pas après trois tentatives ; vérifie le journal du serveur.')
                # A brief database lock during startup must not permanently stop City.
                time.sleep(5 * failures)
                current = revision()
                child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--serve'], cwd=root,
                                         env=child_env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                started = time.monotonic()
                continue
            if time.monotonic() - started > 60:
                failures = 0
            try:
                latest = revision()
                if latest != current and not missions_running():
                    child.terminate()
                    child.wait(timeout=15)
                    current = latest
                    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--serve'], cwd=root,
                                             env=child_env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    started = time.monotonic()
            except (OSError, sqlite3.Error, subprocess.SubprocessError):
                continue  # Keep serving; retry activation when Git and the task store are readable.
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=15)


if __name__ == '__main__':
    if sys.argv[1:] == ['--serve']:
        runpy.run_module('internships_project.city_app', run_name='__main__')
    else:
        supervise()
