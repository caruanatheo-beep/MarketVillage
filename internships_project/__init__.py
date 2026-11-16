"""Compatibility namespace for the separate City and Internships applications."""
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
__path__ = [str(_root / 'City' / 'internships_project'),
            str(_root / 'Internships' / 'internships_project'),
            str(Path(__file__).resolve().parent)]
