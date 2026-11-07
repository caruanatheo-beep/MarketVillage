"""Check City modules for syntax regressions without importing the application."""
import ast
from pathlib import Path


def test_city_modules_compile():
    root = Path(__file__).resolve().parents[1] / "internships_project"
    paths = [*root.glob("city_*.py"), root / "marketdesk_city.py"]
    for path in sorted(paths):
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=path.name)
