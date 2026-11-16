"""Verify automatic fixture cleanup without deleting caller-owned directories."""
from pathlib import Path
import sys
from types import SimpleNamespace

from scripts import city_test


def test_default_test_fixtures_live_outside_workspace_and_are_removed(monkeypatch):
    captured = []
    def run(args):
        path = Path(next(arg.split('=',1)[1] for arg in args if arg.startswith('--basetemp=')))
        assert path.is_dir()
        assert not path.resolve().is_relative_to(Path.cwd().resolve())
        (path/'fixture.txt').write_text('temporary')
        captured.append(path)
        return 0
    monkeypatch.setitem(sys.modules,'pytest',SimpleNamespace(main=run))
    monkeypatch.setattr(sys,'argv',['city_test.py','tests/test_example.py','-q'])
    assert city_test.main() == 0
    assert not captured[0].exists()


def test_explicit_temporary_location_remains_caller_owned(tmp_path,monkeypatch):
    marker = tmp_path/'keep.txt'
    marker.write_text('caller owned')
    def run(args):
        assert '--basetemp='+str(tmp_path) in args
        return 7
    monkeypatch.setitem(sys.modules,'pytest',SimpleNamespace(main=run))
    monkeypatch.setattr(sys,'argv',['city_test.py','--basetemp='+str(tmp_path)])
    assert city_test.main() == 7
    assert marker.read_text() == 'caller owned'
