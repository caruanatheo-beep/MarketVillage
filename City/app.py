"""Launch the independent City server from its project directory."""
from pathlib import Path
import os
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if os.environ.get('MARKETDESK_TEST_SITE_PACKAGES'):
    sys.path.insert(0, os.environ['MARKETDESK_TEST_SITE_PACKAGES'])

if __name__ == '__main__':
    runpy.run_module('internships_project.city_app', run_name='__main__')
