"""Source preparation and failed reviews must not create a City budget."""

import json
from pathlib import Path

import pytest

from internships_project import city_coding as coding, state_store
from internships_project.marketdesk_city import CityError, CityStore


@pytest.fixture
def review(tmp_path, monkeypatch):
    monkeypatch.setattr(state_store, 'USER_DB_PATH', tmp_path / 'test.sqlite3')
    store = CityStore(state_store.USER_DB_PATH)
    source = tmp_path / 'internships_project' / 'city_example.py'
    source.parent.mkdir()
    source.write_text('def example():\n    return []\n', encoding='utf-8')
    monkeypatch.setattr(coding, 'repo_root', lambda: tmp_path)
    monkeypatch.setattr(coding, 'codex_binary', lambda: 'fixture-codex')
    monkeypatch.setattr(coding, 'codex_environment', lambda: {})
    monkeypatch.setattr(coding, 'require_chatgpt', lambda *_: None)

    def unavailable(*_):
        raise CityError('Quota indisponible')

    def git(_root, *args):
        return source.relative_to(tmp_path).as_posix() if args[0] == 'ls-files' else 'revision'

    calls = []

    def execute(command, directory, prompt, env):
        calls.append(command)
        Path(command[command.index('--output-last-message') + 1]).write_text(json.dumps({
            'summary': 'Expliquer le résultat vide',
            'request': 'Ajoute une explication quand le résultat est vide.',
            'evidence': 'La fonction example retourne une liste vide.',
            'limitations': 'Analyse des extraits uniquement.',
        }), encoding='utf-8')
        return [{'type': 'turn.completed'}]

    monkeypatch.setattr(coding, 'codex_usage_percent', unavailable)
    monkeypatch.setattr(coding, 'git', git)
    monkeypatch.setattr(coding, '_execute', execute)
    return store, source, calls


@pytest.mark.parametrize('failure', ['git', 'no_sources', 'read_source', 'schema'])
def test_preparation_failures_preserve_all_review_slots(review, monkeypatch, failure):
    store, source, calls = review
    with monkeypatch.context() as preparation:
        if failure in ('git', 'no_sources'):
            def git(*_):
                if failure == 'git':
                    raise CityError('Git indisponible')
                return ''
            preparation.setattr(coding, 'git', git)
        elif failure == 'read_source':
            original = Path.read_text

            def read(path, *args, **kwargs):
                if path == source:
                    raise OSError('Source indisponible')
                return original(path, *args, **kwargs)
            preparation.setattr(Path, 'read_text', read)
        else:
            original = Path.write_text

            def write(path, *args, **kwargs):
                if path.name == 'schema.json':
                    raise OSError('Ecriture indisponible')
                return original(path, *args, **kwargs)
            preparation.setattr(Path, 'write_text', write)

        for _ in range(7):
            with pytest.raises((CityError, OSError)):
                coding.review_repository()
        assert calls == []

    # More than the former six-call cap can run when the meter is unavailable.
    for _ in range(8):
        result = coding.review_repository()
        assert result['approval_required'] is True
    assert len(calls) == 8
    with store.db() as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='city_codex_agent_usage'").fetchone() is None


def test_failed_codex_execution_does_not_create_a_local_limit(review, monkeypatch):
    store, _, calls = review

    def execute(*_):
        calls.append(True)
        raise CityError('Codex interrompu')

    monkeypatch.setattr(coding, '_execute', execute)
    for _ in range(8):
        with pytest.raises(CityError, match='Codex interrompu'):
            coding.review_repository()
    assert len(calls) == 8
    with store.db() as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='city_codex_agent_usage'").fetchone() is None
