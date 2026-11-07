import json
import threading
import time
from unittest.mock import Mock

import pytest
import requests

from internships_project import internships


def _card(title, slug, *, contract="Stage", location="PARIS - 75", entity="GIE AXA"):
    return (f'<a class="search-results-list__job-link" href="/emploi/paris/{slug}/3441/123">{title}</a>'
            f'<li class="job-location">{location}</li><li class="job-contract">{contract}</li>'
            f'<li class="job-entity">{entity}</li>')


def _detail(title, description):
    posting = {"@type": "JobPosting", "title": title, "datePosted": "2026-11-01",
               "description": description}
    return f'<script type="application/ld+json">{json.dumps(posting)}</script>'


def test_axa_collects_verified_stage_offers_across_pages(monkeypatch):
    pages = {
        1: ('<input class="pagination-current" max="2">'
            + _card("Stage - Investment Strategy and Financial Data Analyst", "investment-strategy")
            + _card("Stage - Health equity analyst", "health-equity")
            + _card("Portfolio Analyst", "portfolio-cdi", contract="CDI")),
        2: (_card("Stage - Portfolio Liquidity Analyst", "portfolio-liquidity")
            + _card("Conseiller Valorisation Automobiles - Stage", "automobiles")),
    }
    details = {
        "investment-strategy": _detail("Stage - Investment Strategy and Financial Data Analyst",
                                       "Suivi des classes d'actifs liquides et données Bloomberg."),
        "portfolio-liquidity": _detail("Stage - Portfolio Liquidity Analyst",
                                      "Portfolio liquidity and market risk analysis."),
    }
    calls = []

    class Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            pass

    def get(url, *, params=None, timeout=None):
        calls.append((url, params))
        if params is not None:
            return Response(pages[params.get("p", 1)])
        return Response(details[url.split("/")[-3]])

    monkeypatch.setattr(internships.requests, "get", get)
    jobs = internships._axa_jobs()
    assert {job.title for job in jobs} == {
        "Stage - Investment Strategy and Financial Data Analyst",
        "Stage - Portfolio Liquidity Analyst",
    }
    assert all(job.published == "2026-11-01" and job.kind == "Stage" for job in jobs)
    assert all(job.source == "Site carrière · AXA" and job.url.startswith("https://recrutement.axa.fr/emploi/") for job in jobs)
    assert len(calls) == 4  # Two listing pages and only two relevant details.


@pytest.mark.parametrize("sequential", [True, False], ids=["serial-baseline", "parallel"])
def test_axa_detail_loading_latency(monkeypatch, sequential):
    """Measure eight slow public details without making external requests."""
    listing = "".join(_card(f"Stage Trading {i}", f"trading-{i}") for i in range(8))
    active = peak = 0
    lock = threading.Lock()
    if sequential:
        executor = internships.ThreadPoolExecutor
        monkeypatch.setattr(internships, "ThreadPoolExecutor",
                            lambda **kwargs: executor(max_workers=1))

    def get(url, *, params=None, timeout=None):
        nonlocal active, peak
        if params is not None:
            return Mock(text=listing)
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(0.1)
            return Mock(text=_detail("Stage Trading", "Trading desk internship"))
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(internships.requests, "get", get)
    started = time.perf_counter()
    jobs = internships._axa_jobs()
    elapsed = time.perf_counter() - started
    print(f"AXA synthetic: {elapsed:.3f}s; peak={peak}; offers={len(jobs)}")
    assert len(jobs) == 8
    assert [job.url.split("/")[-3] for job in jobs] == [f"trading-{i}" for i in range(8)]
    if sequential:
        assert peak == 1
    else:
        assert 1 < peak <= 4


@pytest.mark.parametrize("all_failed", [False, True])
def test_axa_detail_failures_preserve_successes_or_report_outage(monkeypatch, all_failed):
    listing = _card("Stage Trading", "failed") + _card("Stage Trading", "healthy")

    def get(url, *, params=None, timeout=None):
        if params is not None:
            return Mock(text=listing)
        if all_failed or "/failed/" in url:
            raise requests.Timeout("synthetic timeout")
        return Mock(text=_detail("Stage Trading", "Trading desk internship"))

    monkeypatch.setattr(internships.requests, "get", get)
    if all_failed:
        with pytest.raises(requests.Timeout):
            internships._axa_jobs()
    else:
        jobs = internships._axa_jobs()
        assert len(jobs) == 1
        assert "/healthy/" in jobs[0].url
