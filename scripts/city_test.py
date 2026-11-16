"""Run focused City agent tests with the project's existing Python packages."""

import os
from pathlib import Path
import sys
import tempfile


def main() -> int:
    packages = os.environ.get("MARKETDESK_TEST_SITE_PACKAGES", "")
    if packages and Path(packages).is_dir():
        sys.path.insert(0, packages)
    sys.path.insert(0, str(Path.cwd()))
    try:
        import pytest
    except ModuleNotFoundError:
        print("Tests indisponibles : dépendances Python du projet introuvables.", file=sys.stderr)
        return 2
    args = sys.argv[1:]
    if any(arg == '--basetemp' or arg.startswith('--basetemp=') for arg in args):
        return pytest.main(["-p", "no:cacheprovider", *args])
    # Keep nested Git fixtures off the workspace and avoid stale pytest ACLs.
    with tempfile.TemporaryDirectory(prefix='marketdesk-tests-', ignore_cleanup_errors=True) as temporary:
        return pytest.main(["-p", "no:cacheprovider", '--basetemp='+temporary, *args])


if __name__ == "__main__":
    raise SystemExit(main())
