"""Synthetic source refreshes: no network, repository cache or private data."""

from datetime import datetime, timezone
from time import perf_counter

import pytest

from internships_project import internships


@pytest.mark.parametrize("source_fails", [False, True])
def test_refresh_persists_sources_once_and_still_publishes_progress(tmp_path, monkeypatch, source_fails):
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
    assert len(progress) > len(sources)
    assert progress[-1] == len(jobs)
    assert len(writes) == 1
    # A fresh process must recover every source and its full descriptions.
    monkeypatch.setattr(internships, "_source_job_cache_path", None)
    monkeypatch.setattr(internships, "_source_job_cache", {})
    internships._load_source_job_cache()
    assert internships._source_job_cache == sources
