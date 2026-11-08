"""DNCA collection: public offer scope, publication dates and duplicate links."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from internships_project import internships
from internships_project.source_coverage import SOURCE_COVERAGE


BASE = "https://www.dnca-investments.com/carrieres"
TITLES = ("Stagiaire Risques de Marché et Développement", "Stagiaire Risques de Marché")


def article(title=TITLES[0], published="20/10/2026", contract="Stage", location="Paris"):
    return (
        # The listing elsewhere on the same page must not supply offer metadata.
        '<h1>Stagiaire Trading</h1><p>Publiée le 01/01/2025</p>'
        '<article data-ds="careers-detail" data-careers="detail">'
        f'<h1>{title}</h1><span data-role="meta-item"><svg></svg>{contract}</span>'
        f'<span data-role="meta-item"><svg></svg>{location}</span>'
        f'<span data-role="meta-item">Publiée le<!-- --> {published}</span>'
        '<p>Suivi des risques de marché des fonds obligataires. À partir de janvier 2027.</p>'
        '</article>'
    )


def setup_responses(monkeypatch, details):
    listing = ''.join(f'<a href="/carrieres/{key}">{TITLES[0]}</a>' for key in details)
    listing += ('<a href="/carrieres/ABC1?tracking=yes#detail">Duplicate</a>'
                '<a href="https://example.invalid/carrieres/EVIL">External</a>'
                '<a href="/carrieres?contract=stage">Filter</a>')
    responses = {BASE: Mock(text=listing)}
    responses.update({f"{BASE}/{key}": Mock(text=value) for key, value in details.items()})
    get = Mock(side_effect=lambda url, **kwargs: responses[url])
    monkeypatch.setattr(internships.requests, "get", get)
    return get


def test_dates_links_contracts_and_duplicates(monkeypatch):
    get = setup_responses(monkeypatch, {"ABC1": article(), "DEF2": article(TITLES[1], "21/10/2026")})
    jobs = internships._dnca_jobs()
    assert get.call_count == 3
    assert [job.url for job in jobs] == [BASE + "/ABC1", BASE + "/DEF2"]
    assert [job.title for job in jobs] == list(TITLES)
    assert [job.published for job in jobs] == ["2026-10-20", "2026-10-21"]
    assert all(job.location == "Paris" and job.kind == "Stage" for job in jobs)
    assert all(job.start_period == "janvier 2027" and not job.published_inferred for job in jobs)
    duplicate = replace(jobs[0], source="Site carrière · BPCE", url="https://recrutement.bpce.fr/job/1")
    assert len(internships._deduplicate_opportunities(jobs + [duplicate])) == 2
    assert SOURCE_COVERAGE["DNCA"].status == "connected"


@pytest.mark.parametrize("published", ["31/02/2026", "20/10/2999", ""])
def test_invalid_or_missing_publication_stays_unknown(monkeypatch, published):
    setup_responses(monkeypatch, {"ABC1": article(published=published)})
    jobs = internships._dnca_jobs()
    assert len(jobs) == 1
    assert jobs[0].published == ""
    assert not jobs[0].published_inferred


def test_unreadable_details_report_failure(monkeypatch):
    setup_responses(monkeypatch, {"ABC1": '<h1>Page introuvable</h1>'})
    with pytest.raises(ValueError, match="fiche DNCA absente"):
        internships._dnca_jobs()


def test_one_failed_detail_preserves_other_offer(monkeypatch):
    setup_responses(monkeypatch, {"ABC1": "Page introuvable", "DEF2": article(TITLES[1])})
    with pytest.raises(internships._PartialSourceError) as caught:
        internships._dnca_jobs()
    assert [job.url for job in caught.value.jobs] == [BASE + "/DEF2"]
    assert caught.value.failed_urls == {BASE + "/ABC1"}


@pytest.mark.parametrize("with_cache", [False, True])
@pytest.mark.parametrize("failure", ["markup", "timeout"])
def test_partial_collection_keeps_only_still_listed_failed_offers(tmp_path, monkeypatch, with_cache, failure):
    monkeypatch.setattr(internships, "CACHE_PATH", tmp_path / "synthetic.json")
    monkeypatch.setattr(internships, "_source_job_cache_path", None)
    monkeypatch.setattr(internships, "_source_job_cache", {})
    internships._load_source_job_cache()
    previous = internships._opportunity(TITLES[0], "DNCA", "Paris", "Stage", BASE + "/ABC1", "2026-10-20")
    removed = replace(previous, url=BASE + "/REMOVED")
    irrelevant = replace(previous, url=BASE + "/CDI3")
    old_snapshot = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "jobs": [previous, removed, irrelevant], "check": {"status": "ok"},
        "connector_version": 1,
    }
    if with_cache:
        internships._source_job_cache["DNCA"] = old_snapshot
    get = setup_responses(monkeypatch, {"ABC1": "Page introuvable", "DEF2": article(TITLES[1]),
                                       "CDI3": article(title="Analyste Risques de Marché", contract="CDI")})
    if failure == "timeout":
        original = get.side_effect
        def response(url, **kwargs):
            if url == BASE + "/ABC1":
                raise internships.requests.ReadTimeout("synthetic unavailable detail")
            return original(url, **kwargs)
        get.side_effect = response

    jobs, check, error = internships._collect_source("DNCA", internships._dnca_jobs, (), False)

    assert [job.url for job in jobs] == [BASE + "/DEF2"] + ([previous.url] if with_cache else [])
    assert check["status"] == "stale" and check["cache_status"] == "partial"
    assert check["count"] == len(jobs)
    assert "collecte incomplète" in error and check["error"] in error
    assert check["last_success"] == (old_snapshot["updated"] if with_cache else "")
    if with_cache:
        assert internships._source_job_cache["DNCA"] is old_snapshot
    else:
        assert "DNCA" not in internships._source_job_cache
    monkeypatch.setattr(internships, "source_checks", lambda: {"DNCA": check})
    board = internships.render_opportunities(jobs, [error], datetime.now(timezone.utc))
    assert "Collecte incomplète, certaines fiches indisponibles" in board
    assert "Offres en cache, dernière collecte en erreur" not in board
    assert "DNCA: collecte incomplète" in board


def test_detail_parallelism_reduces_loading_time_without_losing_offers(monkeypatch):
    get = setup_responses(monkeypatch, {key: article() for key in ("ABC1", "D2", "D3", "D4", "D5", "D6")})
    original = get.side_effect

    def delayed(url, **kwargs):
        if url != BASE:
            time.sleep(0.1)
        return original(url, **kwargs)

    get.side_effect = delayed
    with monkeypatch.context() as serial:
        serial.setattr(internships, "ThreadPoolExecutor", lambda **kwargs: ThreadPoolExecutor(max_workers=1))
        started = time.perf_counter()
        sequential = internships._dnca_jobs()
        sequential_seconds = time.perf_counter() - started
    started = time.perf_counter()
    concurrent = internships._dnca_jobs()
    concurrent_seconds = time.perf_counter() - started
    print(f"DNCA controlled latency: serial={sequential_seconds:.3f}s; parallel={concurrent_seconds:.3f}s")
    assert [job.url for job in concurrent] == [job.url for job in sequential]
    assert len(concurrent) == 6
    assert concurrent_seconds < sequential_seconds * 0.8


def test_vie_contract_and_local_publication(monkeypatch):
    setup_responses(monkeypatch, {"ABC1": article(title="Analyste Risques de Marché", contract="VIE")})
    jobs = internships._dnca_jobs()
    assert len(jobs) == 1
    assert jobs[0].kind == "VIE"
    assert jobs[0].published == "2026-10-20"


@pytest.mark.parametrize("changes", [{"contract": "CDI", "title": "Analyste Risques de Marché"},
                                    {"title": "Stage Ressources Humaines"}, {"location": ""}])
def test_unusable_offers_are_excluded(monkeypatch, changes):
    setup_responses(monkeypatch, {"ABC1": article(**changes)})
    assert internships._dnca_jobs() == []


@pytest.mark.skipif(os.environ.get("LIVE_SOURCE_TESTS") != "1", reason="Explicit public-source check only")
def test_dnca_public_collection_live(monkeypatch):
    get = internships.requests.get
    timings = []

    def timed_get(url, **kwargs):
        started = time.perf_counter()
        try:
            response = get(url, **kwargs)
        finally:
            timings.append((url, time.perf_counter() - started))
        return response

    monkeypatch.setattr(internships.requests, "get", timed_get)
    started = time.perf_counter()
    try:
        jobs = internships._dnca_jobs()
    finally:
        print("DNCA public request timings:", timings)
    elapsed = time.perf_counter() - started
    print(f"DNCA public collection: {elapsed:.3f}s; {len(jobs)} offers")
    assert jobs, "No verified offers: do not report this source as functional"
    assert all(job.url.startswith(BASE + "/") and job.description and job.location for job in jobs)
    assert all(job.kind in {"Stage", "VIE"} for job in jobs)
    assert all(job.published and not job.published_inferred for job in jobs)
    assert len({job.url for job in jobs}) == len(jobs)
    assert len(internships._deduplicate_opportunities(jobs + jobs)) == len(jobs)
