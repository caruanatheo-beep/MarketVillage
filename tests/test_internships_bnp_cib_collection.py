"""Public CIB collection checks with synthetic pages and controlled latency."""

import time
import threading
from dataclasses import replace

import pytest

from internships_project import internships


ROOT = "https://careers.cib.bnpparibas"
ARCHIVES = (
    ("/who-we-are/global-markets/", 1),
    ("/job-contract-type/internship/", 4),
    ("/job-contract-type/stage/", 4),
    ("/job-domain/temporary-status/", 1),
)


class Response:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def offer(url, company, title):
    return internships._opportunity(title, company, "Paris", "Stage", url, "")


def test_collection_latency_and_complete_pagination(monkeypatch):
    calls = []

    def get(url, **kwargs):
        time.sleep(0.05)
        calls.append(url)
        return Response('<a href="/jobs/trading-intern/">Trading intern</a>')

    monkeypatch.setattr(internships.requests, "get", get)
    monkeypatch.setattr(internships, "_career_detail", offer)
    started = time.perf_counter()
    jobs = internships._bnp_cib_jobs()
    elapsed = time.perf_counter() - started
    print(f"CIB: {len(calls)} pages, {elapsed:.3f}s (50ms/page simulated)")

    expected = {ROOT + path + (f"page/{number}/" if number > 1 else "")
                for path, pages in ARCHIVES for number in range(1, pages + 1)}
    assert set(calls) == expected
    assert len(calls) == len(expected)
    assert [job.url for job in jobs] == [ROOT + "/jobs/trading-intern/"]


def test_all_archives_unavailable_is_reported(monkeypatch):
    def get(url, **kwargs):
        raise internships.requests.ReadTimeout("archive unavailable")

    monkeypatch.setattr(internships.requests, "get", get)
    with pytest.raises(internships.requests.ReadTimeout):
        internships._bnp_cib_jobs()


def test_archive_failure_stops_its_pagination_only(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if "/internship/" in url:
            raise internships.requests.ReadTimeout("archive unavailable")
        return Response('<a href="/jobs/trading-intern/">Trading intern</a>')

    monkeypatch.setattr(internships.requests, "get", get)
    monkeypatch.setattr(internships, "_career_detail", offer)
    assert len(internships._bnp_cib_jobs()) == 1
    assert ROOT + "/job-contract-type/internship/page/2/" not in calls
    assert ROOT + "/job-contract-type/stage/page/4/" in calls


def test_archives_start_concurrently(monkeypatch):
    # Verify overlapping requests without depending on machine speed.
    first_requests = threading.Barrier(4, timeout=5)

    def get(url, **kwargs):
        if "/page/" not in url:
            first_requests.wait()
        return Response("")

    monkeypatch.setattr(internships.requests, "get", get)
    assert internships._bnp_cib_jobs() == []


@pytest.mark.parametrize("detail_date,expected", [
    ("2026-10-20", "2026-10-20"),
    ("", "2026-10-19"),
    ("2026-02-31", "2026-10-19"),
])
def test_detail_date_has_priority_and_empty_duplicates_keep_listing_date(monkeypatch, detail_date, expected):
    def get(url, **kwargs):
        date = '<span>19 October 2026</span>' if "/global-markets/" in url else ""
        return Response('<a href="/jobs/trading-intern/">Trading intern</a>' + date)

    monkeypatch.setattr(internships.requests, "get", get)
    monkeypatch.setattr(internships, "_career_detail", lambda *args: replace(offer(*args), published=detail_date))
    jobs = internships._bnp_cib_jobs()
    assert len(jobs) == 1
    assert jobs[0].published == expected
    assert not jobs[0].published_inferred
