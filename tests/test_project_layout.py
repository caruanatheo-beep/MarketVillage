"""Check project boundaries and compatibility with the independent public export."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from project_layout import ROOT, DATA, legacy_path, source_path


@pytest.mark.parametrize('module,owner', [
    ('src.config','Markets'), ('internships_project.internships','Internships'),
    ('internships_project.city_app','City'), ('internships_project.city_routes','City'),
])
def test_legacy_imports_resolve_to_separate_sources(module, owner):
    origin = Path(importlib.util.find_spec(module).origin).resolve()
    assert origin.is_relative_to(ROOT / owner)


@pytest.mark.parametrize('entrypoint',['Markets/app.py','Internships/app.py','app.py','app_internships.py'])
def test_entrypoints_keep_startup_smoke_mode(entrypoint):
    result = subprocess.run([sys.executable,str(ROOT/entrypoint)],cwd=ROOT,
                            env={**os.environ,'APP_TEST_MODE':'1'},
                            capture_output=True,text=True,timeout=40)
    assert result.returncode == 0, result.stderr
    assert 'entry point: OK' in result.stdout


def test_shared_storage_and_root_are_not_relocated():
    from internships_project import state_store, local_apps, city_specialists
    # Inspect defaults without changing the already isolated store used by tests.
    spec = importlib.util.spec_from_file_location('internships_project._layout_store',state_store.__file__)
    defaults = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(defaults)
    assert defaults.STATE_PATH == DATA / 'user_state.json'
    assert local_apps.ROOT == city_specialists.repo_root() == ROOT
    assert source_path('internships_project/data') == ROOT / 'internships_project/data'


def test_source_resolution_supports_legacy_worktrees(tmp_path):
    old = tmp_path / 'internships_project/city_sample.py'
    old.parent.mkdir()
    old.write_text('legacy = True\n')
    assert source_path('internships_project/city_sample.py', tmp_path) == old
    new = tmp_path / 'City/internships_project/city_sample.py'
    new.parent.mkdir(parents=True)
    new.write_text('current = True\n')
    assert source_path('internships_project/city_sample.py', tmp_path) == new
    assert legacy_path(new.relative_to(tmp_path).as_posix()) == 'internships_project/city_sample.py'
    with pytest.raises(ValueError):
        source_path('../private')


def test_project_paths_preserve_agent_and_publication_boundaries():
    from internships_project.city_worktree import code_path
    from internships_project.city_source_campaign import allowed
    for path in ('City/internships_project/city_routes.py', 'Markets/src/data.py',
                 'Internships/internships_project/internships.py', 'project_layout.py'):
        assert code_path(path)
    assert allowed('Internships/internships_project/internships.py')
    assert allowed('Internships/internships_project/assets/company_logos/example.com.png')
    assert not allowed('City/internships_project/city_routes.py')
    assert not code_path('Internships/internships_project/data/private.py')


def test_source_delta_maps_new_source_paths_to_existing_public_layout(tmp_path):
    from internships_project.city_source_merge import apply_source_delta
    repository = tmp_path / 'repository'
    repository.mkdir()
    def git(*args):
        return subprocess.check_output(['git','-c','core.hooksPath=NUL',
                                       '-c','user.name=Test','-c','user.email=test@example.com',
                                       *args],cwd=repository).decode().strip()
    git('init')
    name = 'Internships/internships_project/source_catalog.py'
    source = repository / name
    source.parent.mkdir(parents=True)
    source.write_text('SOURCES = {}\n')
    git('add','.')
    git('commit','-m','base')
    base = git('rev-parse','HEAD')
    source.write_text('SOURCES = {"bank": "careers"}\n')
    git('commit','-am','source')
    head = git('rev-parse','HEAD')
    release = tmp_path / 'release'
    target = release / 'internships_project/source_catalog.py'
    target.parent.mkdir(parents=True)
    target.write_text('SOURCES = {}\n')
    apply_source_delta(repository,base,head,release,[name],target_names={name:legacy_path(name)})
    assert target.read_text() == source.read_text()
    assert not (release / 'Internships').exists()


def test_public_package_is_independent_of_monorepo_namespaces(tmp_path):
    from scripts.package_internships_pages import package_repository
    seed = tmp_path / 'seed.json'
    seed.write_text(json.dumps({'updated':'','generated':'','sources':{
        'checked':0,'unavailable':0,'retained':0},'offers':[]}))
    output = tmp_path / 'public'
    package_repository(output,seed)
    assert (output / '.github/workflows/pages.yml').is_file()
    assert (output / 'deploy/github-pages/site/index.html').is_file()
    assert (output / 'internships_project/internships.py').is_file()
    assert 'City' not in (output / 'internships_project/__init__.py').read_text()
    assert not (output / 'City').exists()
    assert not (output / 'project_layout.py').exists()
