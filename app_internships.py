"""Backward-compatible Internships entry point."""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
if os.environ.get('MARKETDESK_TEST_SITE_PACKAGES'):
    sys.path.insert(0, os.environ['MARKETDESK_TEST_SITE_PACKAGES'])

if __name__ == '__main__':
    import runpy
    runpy.run_module('Internships.app', run_name='__main__')
else:
    from Internships import app as implementation
    sys.modules[__name__] = implementation
