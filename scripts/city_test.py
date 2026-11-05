"""Run focused City agent tests with the project's existing Python packages."""

import os
from pathlib import Path
import sys


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
    return pytest.main(["-p", "no:cacheprovider", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
