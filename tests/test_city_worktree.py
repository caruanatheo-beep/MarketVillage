import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from internships_project import city_worktree as worktree
from internships_project.city_specialists import git
from internships_project.marketdesk_city import CityError


@pytest.mark.parametrize('platform', ['nt', 'posix'])
def test_git_commands_run_without_windows_console(monkeypatch, tmp_path, platform):
    from internships_project import city_specialists, city_coding

    calls = []
    no_window = 0x08000000
    monkeypatch.setattr(subprocess, 'CREATE_NO_WINDOW', no_window, raising=False)
    for module in (city_specialists, worktree, city_coding):
        monkeypatch.setattr(module, 'os', SimpleNamespace(name=platform))

    def run(command, **options):
        calls.append(options)
        output = 'Logged in using ChatGPT\n' if options.get('text') else b'binary patch\x00'
        return SimpleNamespace(returncode=0, stdout=output, stderr='')

    monkeypatch.setattr(subprocess, 'run', run)
    assert git(tmp_path, 'status', '--porcelain') == 'Logged in using ChatGPT'
    assert worktree._patch(tmp_path, 'HEAD') == b'binary patch\x00'
    city_coding.require_chatgpt('codex', {})
    assert len(calls) == 3
    assert all(call['creationflags'] == (no_window if platform == 'nt' else 0) for call in calls)
    assert all(call['capture_output'] and call['timeout'] > 0 for call in calls)


@pytest.fixture
def repo(tmp_path):
    root=tmp_path/'repo'
    root.mkdir()
    git(root,'init')
    git(root,'config','user.name','Test')
    git(root,'config','user.email','test@example.invalid')
    (root/'internships_project').mkdir()
    (root/'internships_project/example.py').write_text('value = 1\n')
    (root/'note.txt').write_text('private local note')
    (root/'.gitignore').write_text('.city-worktrees/\n.env\n')
    git(root,'add','.')
    git(root,'-c','commit.gpgsign=false','commit','-m','Base')
    return root


def prepare(root):
    (root/'internships_project/example.py').write_text('value = 2\n')
    (root/'internships_project/new_module.py').write_text('helper = True\n')
    (root/'.env').write_text('SECRET=must-never-enter-the-worktree')
    (root/'internships_project/private.json').write_text('{"personal": "private"}')
    directory=root/'.city-worktrees'/('a'*32)
    directory.parent.mkdir()
    git(root,'worktree','add','-b','mission',directory.relative_to(root).as_posix(),'HEAD')
    revision,stamp=worktree.snapshot(root,directory)
    assert (directory/'internships_project/example.py').read_text()=='value = 2\n'
    assert (directory/'internships_project/new_module.py').is_file()
    assert not (directory/'.env').exists()
    assert not (directory/'internships_project/private.json').exists()
    (directory/'internships_project/example.py').write_text('value = 3\n')
    git(directory,'add','internships_project/example.py')
    git(directory,'-c','commit.gpgsign=false','commit','-m','Improve MarketDesk with job_hunter')
    return directory,revision


def test_snapshot_and_integration_preserve_uncommitted_and_staged_work(repo):
    directory,revision=prepare(repo)
    head=git(repo,'rev-parse','HEAD')
    (repo/'note.txt').write_text('user edited this while the agent worked')
    git(repo,'add','note.txt')
    staged=git(repo,'diff','--cached')
    calls=[]
    def checks(root,target,files,agent):
        assert (target/'internships_project/example.py').read_text()=='value = 3\n'
        assert (target/'internships_project/new_module.py').is_file()
        calls.append(True)
        return 'focused checks'
    result=worktree.integrate_patch(repo,directory,revision,['internships_project/example.py'],'job_hunter',checks)
    assert result['integrated'] and result['integration_mode']=='working_tree' and calls
    assert (repo/'internships_project/example.py').read_text()=='value = 3\n'
    assert (repo/'internships_project/new_module.py').read_text()=='helper = True\n'
    assert (repo/'note.txt').read_text()=='user edited this while the agent worked'
    assert git(repo,'rev-parse','HEAD')==head and git(repo,'diff','--cached')==staged
    assert result['commit'] in worktree.activation_commits(repo)
    repeat=worktree.integrate_patch(repo,directory,revision,['internships_project/example.py'],'job_hunter',checks)
    assert repeat['already_present']


def test_conflict_and_test_failure_leave_local_files_untouched(repo):
    directory,revision=prepare(repo)
    (repo/'internships_project/example.py').write_text('value = 99\n')
    with pytest.raises(CityError,match='conflit'):
        worktree.integrate_patch(repo,directory,revision,['internships_project/example.py'],'job_hunter',lambda *a:None)
    assert (repo/'internships_project/example.py').read_text()=='value = 99\n'
    (repo/'internships_project/example.py').write_text('value = 2\n')
    def fail(*args):raise CityError('Tests failed')
    with pytest.raises(CityError,match='Tests failed'):
        worktree.integrate_patch(repo,directory,revision,['internships_project/example.py'],'job_hunter',fail)
    assert (repo/'internships_project/example.py').read_text()=='value = 2\n'
    assert not worktree.activation_commits(repo)


def test_changes_during_validation_are_not_overwritten(repo):
    directory,revision=prepare(repo)
    def checks(*args):
        (repo/'internships_project/example.py').write_text('value = 42\n')
        return 'tests passed'
    with pytest.raises(CityError,match='changé pendant'):
        worktree.integrate_patch(repo,directory,revision,['internships_project/example.py'],'job_hunter',checks)
    assert (repo/'internships_project/example.py').read_text()=='value = 42\n'


def test_frontend_bundle_is_rebuilt_without_overwriting_other_changes(repo):
    source = 'internships_project/city_frontend/src/view.tsx'
    bundle = 'internships_project/city_assets/city.js'
    for name, value in ((source, 'export const value = 1;\n'), (bundle, 'old bundle\n')):
        (repo/name).parent.mkdir(parents=True, exist_ok=True)
        (repo/name).write_text(value)
    git(repo, 'add', source, bundle)
    git(repo, '-c', 'commit.gpgsign=false', 'commit', '-m', 'UI base')
    directory, revision = prepare(repo)
    # Add the UI delta to this mission's existing commit.
    (directory/source).write_text('export const value = 2;\n')
    (directory/bundle).write_text('mission bundle\n')
    git(directory, 'add', source, bundle)
    git(directory, '-c', 'commit.gpgsign=false', 'commit', '--amend', '--no-edit')
    (repo/bundle).write_text('bundle from another integrated mission\n')
    def checks(root, target, files, agent):
        assert (target/bundle).read_text() == 'bundle from another integrated mission\n'
        assert (target/source).read_text() == 'export const value = 2;\n'
        (target/bundle).write_text('rebuilt combined UI\n')
        return 'frontend build'
    result = worktree.integrate_patch(repo, directory, revision,
        ['internships_project/example.py', source, bundle], 'city_ui_engineer', checks)
    assert result['integrated']
    assert (repo/bundle).read_text() == 'rebuilt combined UI\n'
