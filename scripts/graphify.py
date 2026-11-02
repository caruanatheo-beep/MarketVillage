"""Run the isolated Graphify install without changing the application venv."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".codex-tools" / "graphify"))

from graphify.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
