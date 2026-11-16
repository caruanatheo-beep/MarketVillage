"""Local City launcher waits for ongoing work before activating a new commit."""
from internships_project import state_store
from internships_project.marketdesk_city import CityStore
from scripts import city_start


def test_launcher_waits_for_running_missions(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'city.db')
    store = CityStore(state_store.USER_DB_PATH)
    task = store.create_task('alice', 'job_hunter', 'Examine le code', {'operation': 'repository_audit'})
    assert city_start.missions_running() is False
    store.claim_next()
    assert city_start.missions_running() is True
    store.finish(task['id'], result={'title': 'Examen terminé'})
    assert city_start.missions_running() is False


def test_launcher_detects_integrated_patch_without_root_commit(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    monkeypatch.setattr(city_start, 'root', tmp_path)
    monkeypatch.setattr(city_start.subprocess, 'run', lambda *a, **kw: SimpleNamespace(stdout='a'*40))
    before = city_start.revision()
    (tmp_path/'.city-worktrees').mkdir()
    (tmp_path/'.city-worktrees/.integrations.json').write_text(json.dumps(['b'*40]))
    assert city_start.revision() != before
    assert 'b'*40 in city_start.revision()


def test_launcher_retries_failed_startup_with_bounded_backoff(monkeypatch):
    import pytest
    from types import SimpleNamespace
    launched, waits = [], []
    def start(*args, **kwargs):
        launched.append(True)
        return SimpleNamespace(poll=lambda: 1)
    monkeypatch.setattr(city_start.subprocess, 'Popen', start)
    monkeypatch.setattr(city_start, 'revision', lambda: 'current')
    monkeypatch.setattr(city_start.time, 'sleep', waits.append)
    monkeypatch.setattr(city_start.time, 'monotonic', lambda: 0)
    with pytest.raises(RuntimeError, match='trois tentatives'):
        city_start.supervise()
    assert len(launched) == 4
    assert waits == [5, 5, 5, 10, 5, 15, 5]


def test_city_app_imports_without_optional_dotenv_dependency():
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = """
import importlib.abc
import os
import sys
sys.path.insert(0, sys.argv[1])
if os.environ.get('MARKETDESK_TEST_SITE_PACKAGES'):
    sys.path.insert(0, os.environ['MARKETDESK_TEST_SITE_PACKAGES'])
class NoDotenv(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'dotenv' or fullname.startswith('dotenv.'):
            raise ModuleNotFoundError('optional dotenv dependency unavailable')
sys.meta_path.insert(0, NoDotenv())
import internships_project.city_app
"""
    import_paths = [*(path for path in sys.path if "site-packages" in path)]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(import_paths)
    result = subprocess.run([sys.executable, "-c", script, str(root)], cwd=root, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr[:500]
