"""Public RSS collection with synthetic responses and controlled latency only."""

import time
import threading
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from internships_project import internships


HOST = "jobs.amundi.com"


def feed(contract):
    return Mock(content=(f'<rss><channel><item><title>Stage Trading {contract}</title>'
                         f'<link>https://{HOST}/offer/{contract}</link>'
                         '</item></channel></rss>').encode())


def test_rss_latency_and_complete_results(monkeypatch):
    calls = []
    simultaneous = threading.Barrier(2, timeout=3)

    def get(url, params, **kwargs):
        simultaneous.wait()
        time.sleep(0.15)
        calls.append(params["Rss_Contract"])
        return feed(params["Rss_Contract"])

    def detail(url, company, title):
        return internships._opportunity(title, company, "Paris", "Stage", url, "")

    monkeypatch.setattr(internships.requests, "get", get)
    monkeypatch.setattr(internships, "_career_detail", detail)
    started = time.perf_counter()
    jobs = internships._amundi_jobs()
    elapsed = time.perf_counter() - started
    print(f"RSS: {elapsed:.3f}s, 150ms/feed, {len(jobs)} offers")
    assert sorted(calls) == [579, 1478]
    assert [job.url for job in jobs] == [f"https://{HOST}/offer/{i}" for i in (579, 1478)]


def test_all_detail_failures_are_reported(monkeypatch):
    monkeypatch.setattr(internships.requests, "get", lambda *a, **kw: feed(579))
    def fail(*args):
        raise internships.requests.ReadTimeout("synthetic detail unavailable")
    monkeypatch.setattr(internships, "_career_detail", fail)
    with pytest.raises(internships.requests.ReadTimeout):
        internships._amundi_jobs()


@pytest.mark.parametrize("malformed", [False, True])
def test_one_feed_failure_preserves_other_contract(monkeypatch, malformed):
    def get(url, params, **kwargs):
        if params["Rss_Contract"] == 579:
            if malformed:
                return Mock(content=b"<rss>broken")
            raise internships.requests.ReadTimeout("synthetic feed unavailable")
        return feed(1478)
    monkeypatch.setattr(internships.requests, "get", get)
    monkeypatch.setattr(internships, "_career_detail", lambda url, company, title:
                        internships._opportunity(title, company, "Paris", "Stage", url, ""))
    assert [job.url for job in internships._amundi_jobs()] == [f"https://{HOST}/offer/1478"]


def test_all_feed_failures_are_reported(monkeypatch):
    monkeypatch.setattr(internships.requests, "get", lambda *a, **kw: Mock(content=b"not XML"))
    with pytest.raises(internships.ElementTree.ParseError):
        internships._amundi_jobs()


def test_irrelevant_details_mean_empty_not_error(monkeypatch):
    monkeypatch.setattr(internships.requests, "get", lambda *a, **kw: feed(579))
    monkeypatch.setattr(internships, "_career_detail", lambda *a: None)
    assert internships._amundi_jobs() == []


def test_detail_outage_keeps_previous_offers_and_reports_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(internships, "CACHE_PATH", tmp_path / "synthetic.json")
    monkeypatch.setattr(internships, "_source_job_cache_path", None)
    monkeypatch.setattr(internships, "_source_job_cache", {})
    job = internships._opportunity("Stage Trading", "Amundi", "Paris", "Stage",
                                     f"https://{HOST}/offer/579", "")
    internships._load_source_job_cache()
    internships._source_job_cache["Amundi"] = {
        "updated": datetime.now(timezone.utc).isoformat(), "jobs": [job], "check": {},
    }
    monkeypatch.setattr(internships.requests, "get", lambda *a, **kw: feed(579))
    def fail(*args):
        raise internships.requests.ReadTimeout("synthetic detail unavailable")
    monkeypatch.setattr(internships, "_career_detail", fail)
    jobs, check, error = internships._collect_source("Amundi", internships._amundi_jobs, (), True)
    assert jobs == [job]
    assert check["status"] == "stale"
    assert error.startswith("Amundi:")


def test_duplicate_links_are_loaded_once_and_external_links_ignored(monkeypatch):
    content = (f'<rss><channel><item><title>Stage Trading</title><link>https://{HOST}/offer/1</link>'
               '</item><item><title>Stage Trading</title><link>https://example.invalid/offer</link>'
               '</item></channel></rss>').encode()
    monkeypatch.setattr(internships.requests, "get", lambda *a, **kw: Mock(content=content))
    detail = Mock(return_value=None)
    monkeypatch.setattr(internships, "_career_detail", detail)
    assert internships._amundi_jobs() == []
    detail.assert_called_once_with(f"https://{HOST}/offer/1", "Amundi", "Stage Trading")
