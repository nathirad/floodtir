"""Compatibility wrapper for the Bangkok water scraper.

TLS certificate verification intentionally uses Python's secure default.
Install the correct CA bundle on the host instead of bypassing verification.
"""

import runpy
import sys
from pathlib import Path


_scraper = str(Path(__file__).parent / 'scrape_bangkok_water.py')
sys.argv = [_scraper] + sys.argv[1:]
runpy.run_path(_scraper, run_name='__main__')
