"""The scheduled worker can run without starting the City web server."""
import os
from pathlib import Path
import subprocess
import sys


def test_standalone_worker_starts_with_its_own_database(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env['INTERNSHIPS_USER_DB'] = str(tmp_path / 'accounts.sqlite3')
    result = subprocess.run([sys.executable, str(root / 'scripts' / 'run_city_worker.py')],
                            cwd=root, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr[:500]
    assert (tmp_path / 'accounts.sqlite3').exists()
