"""Isolated code snapshots and tested patches; never stage the user's workspace."""
from __future__ import annotations

from project_layout import legacy_path, source_path

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .city_specialists import git
from .marketdesk_city import CityError
from .public_safety import company_logo_path


def code_path(name: str) -> bool:
    name = legacy_path(name)
    path = Path(name)
    excluded = {'node_modules', 'vendor', '__pycache__', 'data', 'user_data', 'exports', 'cache', 'cvs'}
    if any(part.lower() in excluded or part.startswith('.') for part in path.parts):
        return False
    if name in {'project_layout.py', 'AGENTS.md', 'app.py', 'app_internships.py', 'requirements.txt', 'pyproject.toml', 'pytest.ini',
                'internships_project/SOURCES.md'}:
        return True
    if not name.startswith(('internships_project/', 'src/', 'tests/', 'scripts/')):
        return False
    if path.suffix in {'.py', '.ts', '.tsx', '.js', '.mjs', '.css', '.html'}:
        return True
    if path.name in {'package.json', 'package-lock.json', 'tsconfig.json'}:
        return True
    return company_logo_path(name) or (name.startswith('internships_project/city_assets/') and path.suffix in {'.png', '.webp', '.svg', '.json'})


def code_files(root: Path) -> dict[str, bytes | None]:
    names = set(git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split('\0'))
    files = {}
    for name in sorted(names):
        if not code_path(name):
            continue
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise CityError('Copie de code suspendue : lien de fichier hors du dépôt.')
        if not path.exists():
            files[name] = None
        elif path.is_file() and path.stat().st_size <= 2_000_000:
            files[name] = path.read_bytes()
    return files


def signature(files: dict[str, bytes | None]) -> str:
    digest = hashlib.sha256()
    for name, data in sorted(files.items()):
        digest.update(name.encode() + b'\0' + (hashlib.sha256(data).digest() if data is not None else b'deleted'))
    return digest.hexdigest()


def snapshot(root: Path, directory: Path) -> tuple[str, str]:
    """Commit an allowlisted code-only baseline inside a disposable worktree."""
    files = code_files(root)
    stamp = signature(files)
    if signature(code_files(root)) != stamp:
        raise CityError('Le dépôt a changé pendant les vérifications : intégration suspendue. La branche reste disponible.')
    existing = code_files(directory)
    for name in existing.keys() - files.keys():
        (directory/name).unlink(missing_ok=True)
    for name, data in files.items():
        if name in existing and existing[name] == data:
            continue
        target = directory / name
        if target.is_symlink() or not target.resolve().is_relative_to(directory.resolve()):
            raise CityError('Copie de code suspendue : destination hors de la branche isolée.')
        if data is None:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    git(directory, 'add', '-A')
    if git(directory, 'diff', '--cached', '--name-only'):
        git(directory, '-c', 'commit.gpgsign=false', 'commit', '-m', 'Snapshot local code for isolated City mission')
    return git(directory, 'rev-parse', 'HEAD'), stamp


def activation_commits(root: Path) -> list[str]:
    try:
        data = json.loads((root/'.city-worktrees'/'.integrations.json').read_text(encoding='utf-8'))
        return [value for value in data if isinstance(value, str) and len(value) == 40
                and all(c in '0123456789abcdef' for c in value)][-200:]
    except (OSError, ValueError, TypeError):
        return []


def _patch(directory: Path, *args: str) -> bytes:
    result = subprocess.run(['git', '-c', 'core.longpaths=true', 'diff', '--binary', '--no-ext-diff',
                             '--no-textconv', *args], cwd=directory, capture_output=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode:
        raise CityError('Impossible de préparer les changements isolés.')
    return result.stdout


def integrate_patch(root: Path, directory: Path, revision: str, files: list[str], agent_id: str,
                    checks, on_progress=None) -> dict:
    """Test against current local code, then apply only the mission delta, without touching the index."""
    if any(not code_path(name) for name in files):
        raise CityError('Intégration suspendue : fichier hors du code autorisé. La branche reste disponible.')
    area = root/'.city-worktrees'
    area.mkdir(exist_ok=True)
    current = git(root, 'rev-parse', 'HEAD')
    with tempfile.TemporaryDirectory(prefix='integration-', dir=area) as temporary:
        parent = Path(temporary).resolve()
        target = parent/'worktree'
        if not target.resolve().is_relative_to(area.resolve()):
            raise CityError('Chemin de vérification invalide.')
        git(root, 'worktree', 'add', '--detach', str(target), current)
        try:
            base, stamp = snapshot(root, target)
            patch = parent/'mission.patch'
            frontend_changed = any(legacy_path(name).startswith('internships_project/city_frontend/src/') for name in files)
            # Rebuild the shared bundle from the combined sources; an older generated bundle
            # must neither overwrite another agent's UI change nor create a false conflict.
            patch_files = [name for name in files if not (
                frontend_changed and legacy_path(name) == 'internships_project/city_assets/city.js')]
            patch.write_bytes(_patch(directory, revision, 'HEAD', '--', *patch_files))
            already_applied = False
            try:
                git(target, 'apply', '--check', str(patch))
                git(target, 'apply', str(patch))
            except CityError as exc:
                try:
                    git(target, 'apply', '--reverse', '--check', str(patch))
                    already_applied = True
                except CityError:
                    if agent_id!='internships_engineer':
                        raise CityError('Intégration suspendue : conflit avec les modifications locales. La branche reste disponible.') from exc
                    from .city_source_merge import apply_source_delta
                    apply_source_delta(directory,revision,'HEAD',target,patch_files)
            if on_progress:
                on_progress('Vérification du résultat avec les modifications locales actuelles, dans une copie isolée.')
            test_file = checks(root, target, files, agent_id)
            if frontend_changed:
                bundle = source_path('internships_project/city_assets/city.js', target).relative_to(target).as_posix()
                if bundle not in files:
                    files.append(bundle)
            git(target, 'add', '-A', '--', *files)
            patch.write_bytes(_patch(target, '--cached', 'HEAD', '--', *files))
            if patch.read_bytes():
                git(target, '-c', 'commit.gpgsign=false', 'commit', '-m', 'Improve MarketDesk with '+agent_id)
                commit = git(target, 'rev-parse', 'HEAD')
            else:
                commit = git(directory, 'rev-parse', 'HEAD')
            if git(root, 'rev-parse', 'HEAD') != current or signature(code_files(root)) != stamp:
                raise CityError('Le dépôt a changé pendant les vérifications : intégration suspendue. La branche reste disponible.')
            if patch.read_bytes():
                git(root, 'apply', '--check', str(patch))
                git(root, 'apply', str(patch))
            git(root, 'update-ref', 'refs/marketdesk/integrations/'+directory.name, commit)
            commits = list(dict.fromkeys(activation_commits(root) + [commit]))[-200:]
            staged = area/'.integrations.tmp'
            staged.write_text(json.dumps(commits), encoding='utf-8')
            os.replace(staged, area/'.integrations.json')
            return {'integrated': True, 'commit': commit, 'rebased': base != revision,
                    'already_present': already_applied,
                    'integration_mode': 'working_tree', 'server_checks': [test_file,
                    'frontend build' if any(name.endswith('.tsx') for name in files) else 'Python syntax']}
        finally:
            # Only the disposable worktree created above is removed; its source branch remains.
            dependencies = source_path('internships_project/city_frontend', target)/'node_modules'
            if dependencies.is_junction():
                os.rmdir(dependencies)
            elif dependencies.is_symlink():
                dependencies.unlink()
            git(root, 'worktree', 'remove', '--force', str(target))
