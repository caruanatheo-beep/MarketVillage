import os

import pytest
import requests

from src.calendar import fetch_bls_events
from src.data import SERIES, FredCollector
from internships_project.internships import _bnp_cib_jobs

pytestmark = pytest.mark.live


@pytest.mark.skipif(os.getenv("LIVE_SOURCE_TESTS") != "1", reason="Set LIVE_SOURCE_TESTS=1 to call official sources")
def test_principal_public_sources_live():
    collector = FredCollector(timeout=12, cache_ttl=60)
    point = collector.fetch(SERIES[2])  # US 10Y single-series CSV path
    assert point.value is not None
    assert point.source_url.startswith("https://fred.stlouisfed.org/")
    snapshot = collector.fetch_all()  # parallel single-series CSV paths
    assert sum(item.value is not None for item in snapshot) >= 20


@pytest.mark.skipif(os.getenv("LIVE_SOURCE_TESTS") != "1", reason="Set LIVE_SOURCE_TESTS=1 to call official sources")
def test_bls_calendar_fails_safely_when_live_provider_is_reachable_or_blocked():
    events, error = fetch_bls_events(days_ahead=120)
    assert isinstance(events, list)
    assert error is None or error.startswith("BLS calendar unavailable:")


@pytest.mark.skipif(os.getenv("LIVE_SOURCE_TESTS") != "1", reason="Set LIVE_SOURCE_TESTS=1 to call official sources")
def test_bnp_cib_current_market_internships_live():
    try:
        jobs = _bnp_cib_jobs()
    except requests.RequestException as exc:
        pytest.skip(f"BNP CIB inaccessible depuis cette connexion : {exc}")
    assert jobs, "BNP CIB is reachable but no open market internships were parsed"
    assert all(job.company == "BNP Paribas" and job.url.startswith("https://careers.cib.bnpparibas/jobs/")
               for job in jobs)
