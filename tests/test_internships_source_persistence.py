"""Synthetic source refreshes: no network, repository cache or private data."""

from datetime import datetime, timezone
from threading import Lock
from time import perf_counter
from types import SimpleNamespace

import pytest

from internships_project import internships


def test_progressive_collection_runs_more_than_eight_sources_without_exceeding_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(internships, "CACHE_PATH", tmp_path / "offers.json")
    monkeypatch.setattr(internships, "_source_job_cache_path", None)
    monkeypatch.setattr(internships, "_source_job_cache", {})
    monkeypatch.setattr(internships, "_source_checks", {})
    monkeypatch.setattr(internships, "_source_counts", {})
    monkeypatch.setattr(internships, "_opportunity_source_tasks",
                        lambda: [(f"Synthetic {i}", None, ()) for i in range(24)])
    lock = Lock()
    active = [0]
    peak = [0]

    def collect(name, loader, args, force):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        try:
            # Model a slow, independent public feed without network access.
            from time import sleep
            sleep(0.04)
            return [], {"status": "empty", "count": 0}, ""
        finally:
            with lock:
                active[0] -= 1

    monkeypatch.setattr(internships, "_collect_source", collect)
    monkeypatch.setattr(internships, "_publish_refresh_progress", lambda *args: None)
    internships._fetch_opportunities_progressive()
    assert 8 < peak[0] <= internships.SOURCE_COLLECTION_WORKERS


@pytest.mark.parametrize("source_fails", [False, True])
@pytest.mark.parametrize("clock_step", [0, 0.6])
def test_refresh_persists_sources_once_and_still_publishes_progress(tmp_path, monkeypatch, source_fails, clock_step):
    monkeypatch.setattr(internships, "CACHE_PATH", tmp_path / "offers.json")
    monkeypatch.setattr(internships, "_source_job_cache_path", None)
    monkeypatch.setattr(internships, "_source_job_cache", {})
    internships._load_source_job_cache()
    now = datetime.now(timezone.utc).isoformat()
    sources = {}
    for index in range(24):
        name = f"Synthetic bank {index}"
        sources[name] = {
            "updated": now,
            "jobs": [internships.Opportunity(
                f"Trading intern {row}", name, "Paris", "Stage",
                f"https://example.invalid/{index}/{row}", "2026-11-07", 90,
                description="Synthetic public offer description. " * 60,
            ) for row in range(80)],
            "check": {"status": "ok", "count": 80},
            "connector_version": 1,
        }
    monkeypatch.setattr(internships, "_source_job_cache", sources)
    monkeypatch.setattr(internships, "SMARTRECRUITERS", {name: name for name in sources})
    for registry in ("GREENHOUSE", "LEVER", "ASHBY", "WORKDAY",
                     "ORACLE_CAREER_BOARDS", "CAREER_LISTINGS"):
        monkeypatch.setattr(internships, registry, {})
    monkeypatch.setattr(internships, "_source_checks", {})
    monkeypatch.setattr(internships, "_source_counts", {})

    def collect(name, loader, args, force):
        if source_fails and name == "Business France VIE":
            raise internships.requests.Timeout("Synthetic source unavailable")
        jobs = sources.get(name, {}).get("jobs", [])
        return jobs, {"status": "ok" if jobs else "empty"}, ""

    monkeypatch.setattr(internships, "_collect_source", collect)
    # Isolate persistence cost from the independently tested offer deduplication.
    monkeypatch.setattr(internships, "_deduplicate_opportunities", lambda jobs: jobs)
    progress = []
    clock = [0.0]

    def tick():
        clock[0] += clock_step
        return clock[0]

    monkeypatch.setattr(internships, "time", SimpleNamespace(perf_counter=tick))
    monkeypatch.setattr(internships, "_publish_refresh_progress",
                        lambda jobs, errors: progress.append(len(jobs)))
    writes = []
    write = internships._write_source_job_cache

    def persist():
        writes.append(True)
        write()

    monkeypatch.setattr(internships, "_write_source_job_cache", persist)
    started = perf_counter()
    jobs, errors = internships._fetch_opportunities_progressive()
    elapsed = perf_counter() - started
    print(f"source persistence: {elapsed:.3f}s, {len(writes)} writes, "
          f"{len(progress)} progress updates, {len(jobs)} offers")
    assert len(jobs) == 1920
    assert errors == (["Business France VIE: Timeout"] if source_fails else [])
    if source_fails:
        assert internships.source_checks()["Business France VIE"]["status"] == "error"
    # First and final snapshots survive batching, including source failures.
    assert len(progress) == 2 if clock_step == 0 else len(progress) > 2
    assert progress[-1] == len(jobs)
    assert len(writes) == 1
    # A fresh process must recover every source and its full descriptions.
    monkeypatch.setattr(internships, "_source_job_cache_path", None)
    monkeypatch.setattr(internships, "_source_job_cache", {})
    internships._load_source_job_cache()
    assert internships._source_job_cache == sources
