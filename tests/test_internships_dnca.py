"""DNCA collection: public offer scope, publication dates and duplicate links."""

import os
import time
from dataclasses import replace
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
    jobs = internships._dnca_jobs()
    assert [job.url for job in jobs] == [BASE + "/DEF2"]


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
def test_dnca_public_collection_live():
    started = time.perf_counter()
    jobs = internships._dnca_jobs()
    elapsed = time.perf_counter() - started
    print(f"DNCA public collection: {elapsed:.3f}s; {len(jobs)} offers")
    assert jobs, "No verified offers: do not report this source as functional"
    assert all(job.url.startswith(BASE + "/") and job.description and job.location for job in jobs)
    assert all(job.kind in {"Stage", "VIE"} for job in jobs)
    assert all(job.published and not job.published_inferred for job in jobs)
    assert len({job.url for job in jobs}) == len(jobs)
    assert len(internships._deduplicate_opportunities(jobs + jobs)) == len(jobs)
