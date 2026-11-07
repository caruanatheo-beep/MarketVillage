"""Refresh dating checks using synthetic offers, without network or stored data."""

import json
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest

from internships_project import internships
from internships_project.internships import Opportunity


TODAY = date(2026, 11, 6)
OFFER = Opportunity("Assistant Trading", "Synthetic Bank", "Paris", "Stage",
                    "https://example.invalid/trading", "", 10)
INVALID_DATES = ["2026-02-30", "0000-01-01", "2026-13-01", "20261106", "unknown"]


@pytest.mark.parametrize("published", INVALID_DATES)
@pytest.mark.parametrize("inferred", [False, True])
def test_invalid_current_date_becomes_detection(monkeypatch, published, inferred):
    monkeypatch.setattr(internships, "_refresh_first_seen", {})
    job = replace(OFFER, published=published, published_inferred=inferred)

    result = internships._date_detected_offer(job, None, TODAY)

    assert result == replace(OFFER, published=TODAY.isoformat(), published_inferred=True)
    assert internships._refresh_first_seen == {OFFER.url: TODAY.isoformat()}


@pytest.mark.parametrize("published", INVALID_DATES)
@pytest.mark.parametrize("origin", ["previous_confirmed", "previous_detected", "history"])
def test_invalid_prior_dates_do_not_poison_detection(monkeypatch, published, origin):
    history = {OFFER.url: published} if origin == "history" else {}
    previous = (None if origin == "history" else
                replace(OFFER, published=published,
                        published_inferred=origin == "previous_detected"))
    monkeypatch.setattr(internships, "_refresh_first_seen", history)

    result = internships._date_detected_offer(OFFER, previous, TODAY)

    assert result.published == TODAY.isoformat()
    assert result.published_inferred


@pytest.mark.parametrize("inferred", [False, True])
def test_invalid_source_date_preserves_valid_previous_date(monkeypatch, inferred):
    monkeypatch.setattr(internships, "_refresh_first_seen", {})
    previous = replace(OFFER, published="2024-02-29", published_inferred=inferred)
    job = replace(OFFER, published="2026-02-30")

    result = internships._date_detected_offer(job, previous, TODAY)

    assert result.published == previous.published
    assert result.published_inferred == inferred


def test_valid_source_date_replaces_detection(monkeypatch):
    monkeypatch.setattr(internships, "_refresh_first_seen", {OFFER.url: "2026-10-01"})
    previous = replace(OFFER, published="2026-10-01", published_inferred=True)
    job = replace(OFFER, published="2024-02-29")

    assert internships._date_detected_offer(job, previous, TODAY) == job


def test_invalid_source_date_keeps_older_detection_from_history(monkeypatch):
    monkeypatch.setattr(internships, "_refresh_first_seen", {OFFER.url: "2026-10-20"})
    previous = replace(OFFER, published="2026-10-27")
    job = replace(OFFER, published="0000-01-01")

    result = internships._date_detected_offer(job, previous, TODAY)

    assert result.published == "2026-10-20"
    assert result.published_inferred


def test_valid_history_keeps_earliest_detection_despite_invalid_source(monkeypatch):
    monkeypatch.setattr(internships, "_refresh_first_seen", {OFFER.url: "2024-02-29"})
    previous = replace(OFFER, published="2026-10-20", published_inferred=True)
    job = replace(OFFER, published="0000-01-01")

    result = internships._date_detected_offer(job, previous, TODAY)

    assert result.published == "2024-02-29"
    assert result.published_inferred
    assert not internships.matching_opportunities([result], weekly=True, today=TODAY)


def test_refresh_keeps_corrected_detection_through_progress_and_completion(monkeypatch):
    now = datetime(2026, 11, 6, tzinfo=timezone.utc)
    clock = Mock(wraps=datetime)
    clock.now.return_value = now
    writer = Mock()
    snapshot_writer = Mock()
    monkeypatch.setattr(internships, "datetime", clock)
    monkeypatch.setattr(internships, "_cache", (now, [], []))
    monkeypatch.setattr(internships, "_last_attempt", None)
    monkeypatch.setattr(internships, "_force_source_refresh", False)
    monkeypatch.setattr(internships, "_refresh_previous_jobs", {})
    monkeypatch.setattr(internships, "_refresh_first_seen", {})
    monkeypatch.setattr(internships, "_read_history_document", lambda: {})
    monkeypatch.setattr(internships, "_write_cache", writer)
    monkeypatch.setattr(internships, "_remember_opportunity_snapshot", snapshot_writer)
    job = replace(OFFER, published="2026-02-30")

    def fetch():
        internships._publish_refresh_progress([job], [])
        assert internships._cache[1] == [
            replace(OFFER, published=TODAY.isoformat(), published_inferred=True)]
        return [job], []

    monkeypatch.setattr(internships, "_fetch_opportunities", fetch)

    jobs, errors, updated = internships.refresh_opportunities(notify_email=False)

    assert updated == now
    assert errors == []
    assert jobs == [replace(OFFER, published=TODAY.isoformat(), published_inferred=True)]
    assert internships.matching_opportunities(jobs, daily=True, today=TODAY) == jobs
    assert internships.matching_opportunities(jobs, weekly=True, today=TODAY) == jobs
    assert writer.call_count == 2
    writer.assert_called_with(now, jobs, [])
    snapshot_writer.assert_called_with(now, jobs, [])


def test_cacib_reposted_offer_keeps_first_observed_date(tmp_path, monkeypatch):
    url = "https://jobs.ca-cib.com/Pages/Offre/detailoffre.aspx?idOffre=116549"
    old = replace(OFFER, url=url, published="2026-10-27")
    reposted = replace(old, published="2026-11-07")
    cache = tmp_path / "internships_cache.json"
    cache.write_text(json.dumps({"version": 3, "updated": "2026-11-07T00:20:00+00:00",
                                 "jobs": [asdict(reposted)], "errors": []}), encoding="utf-8")
    cache.with_name("internships_history.json").write_text(json.dumps({
        "version": 1, "baseline": {"updated": "2026-10-27T15:13:00+00:00",
                                   "jobs": [asdict(old)], "errors": []}, "snapshots": []}), encoding="utf-8")
    monkeypatch.setattr(internships, "CACHE_PATH", cache)
    monkeypatch.setattr(internships, "_cache", None)
    cached = internships._read_cache()[1][0]
    assert cached.published == "2026-10-27"
    assert cached.published_inferred
    monkeypatch.setattr(internships, "_fetch_opportunities", lambda: ([reposted], []))
    jobs, _, _ = internships.refresh_opportunities(notify_email=False)
    assert jobs[0].published == "2026-10-27"
    assert jobs[0].published_inferred
    assert not internships.matching_opportunities(jobs, daily=True, today=date(2026, 11, 7))
    assert not internships.matching_opportunities(jobs, weekly=True, today=date(2026, 11, 7))
    assert internships._read_history_document()["first_seen"][url] == "2026-10-27"
