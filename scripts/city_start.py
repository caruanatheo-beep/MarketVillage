"""Launch City with the project's installed packages from the portable Python."""
import runpy
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / '.venv' / 'Lib' / 'site-packages')]
runpy.run_module('internships_project.city_app', run_name='__main__')
