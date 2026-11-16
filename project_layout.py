"""Application locations in the monorepo; legacy imports and data stay stable."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CITY = ROOT / 'City' / 'internships_project'
INTERNSHIPS = ROOT / 'Internships' / 'internships_project'
DATA = ROOT / 'internships_project' / 'data'


def legacy_path(name: str) -> str:
    """Translate a project source path to its existing publication/import path."""
    for prefix in ('Markets/', 'City/', 'Internships/'):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def source_path(name: str, root: Path = ROOT) -> Path:
    """Find a logical source path in new checkouts and pre-migration worktrees."""
    path = Path(name)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Expected a repository-relative source path')
    if name.startswith(('Markets/', 'City/', 'Internships/')):
        return root / name
    if name.startswith('src/'):
        candidate = root / 'Markets' / name
    elif name.startswith('deploy/'):
        candidate = root / 'Internships' / name
    elif name.startswith('internships_project/') and name != 'internships_project/data' and not name.startswith('internships_project/data/'):
        relative = name.split('/', 1)[1]
        owner = 'City' if relative.startswith(('city_', 'marketdesk_city.', 'CITY_AGENT_ROLES')) else 'Internships'
        candidate = root / owner / name
    else:
        return root / name
    # Existing fixture/worktree layouts and the independent public repository
    # continue to use their original paths.
    return candidate if candidate.exists() or candidate.parent.exists() else root / name
