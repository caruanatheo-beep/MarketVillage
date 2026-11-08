"""Public Talentsoft RSS regression checks, with an opt-in live measurement."""

import os
from datetime import datetime, timezone
from time import perf_counter
from unittest.mock import Mock
from xml.etree import ElementTree

import pytest
import requests

from internships_project import internships


URL = "https://jobs.amundi.com/Pages/Offre/detailoffre.aspx?idOffre=117097"


def rss(pubdate="", repeats=1):
    item = (f"<item><title>Stage Structuration ETF</title><link>{URL}</link>"
            f"<pubDate>{pubdate}</pubDate></item>")
    return ("<rss><channel><lastBuildDate>Wed, 04 Nov 2026 10:19:45 Z</lastBuildDate>"
            + item * repeats + "</channel></rss>").encode()


def install_public_pages(monkeypatch, feeds, detail_date=""):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        response = Mock()
        if url.endswith("/handlers/offerRss.ashx"):
            content = feeds[kwargs["params"]["Rss_Contract"]]
            if isinstance(content, Exception):
                raise content
            response.content = content
        else:
            assert url == URL
            response.text = ("<h1>Stage Structuration ETF</h1>"
                             "<p>Localisation Paris Niveau Bac+5 Type de contrat Stage "
                             f"Date de publication : {detail_date}</p>")
        return response

    monkeypatch.setattr(internships.requests, "get", get)
    return calls


@pytest.mark.parametrize("broken", [b"<rss><channel>", b"<html>Unavailable</html>",
                                  requests.Timeout("Public feed timed out")])
@pytest.mark.parametrize("broken_contract", [579, 1478])
def test_one_broken_feed_preserves_verified_offers(monkeypatch, broken, broken_contract):
    feeds = {579: rss(), 1478: rss()}
    feeds[broken_contract] = broken
    install_public_pages(monkeypatch, feeds, detail_date="04/11/2024")

    jobs = internships._amundi_jobs()

    assert len(jobs) == 1
    assert jobs[0].url == URL
    assert jobs[0].published == "2024-11-04"


@pytest.mark.parametrize("broken", [b"<rss>", b"<html>Unavailable</html>", b"<rss/>"])
def test_broken_feeds_report_failure_instead_of_empty_success(monkeypatch, broken):
    install_public_pages(monkeypatch, {579: broken, 1478: broken})

    with pytest.raises((ElementTree.ParseError, ValueError)):
        internships._amundi_jobs()


def test_valid_empty_feeds_remain_empty(monkeypatch):
    calls = install_public_pages(monkeypatch, {579: rss(repeats=0), 1478: rss(repeats=0)})

    assert internships._amundi_jobs() == []
    assert len(calls) == 2


def test_unreachable_feeds_report_failure(monkeypatch):
    install_public_pages(monkeypatch, {579: requests.Timeout("Public feed timed out"),
                                      1478: requests.Timeout("Public feed timed out")})

    with pytest.raises(requests.Timeout):
        internships._amundi_jobs()


@pytest.mark.parametrize("pubdate,expected", [
    ("Mon, 04 Nov 2024 10:19:45 Z", "2024-11-04"),
    ("Mon, 04 Nov 2024 10:19:45", "2024-11-04"),
    ("Mon, 04 Nov 2024 00:30:00 +0200", "2024-11-03"),
    ("", ""),
    ("not a date", ""),
    ("31 Feb 2024 10:00:00 GMT", ""),
    ("04 Nov 9999 10:00:00 GMT", ""),
])
def test_only_valid_offer_publication_dates_are_used(monkeypatch, pubdate, expected):
    install_public_pages(monkeypatch, {579: rss(pubdate), 1478: rss(pubdate)})

    jobs = internships._amundi_jobs()

    assert len(jobs) == 1
    assert jobs[0].published == expected
    assert not jobs[0].published_inferred


def test_future_offer_date_does_not_become_publication(monkeypatch):
    clock = Mock(wraps=datetime)
    clock.now.return_value = datetime(2024, 11, 4, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(internships, "datetime", clock)
    install_public_pages(monkeypatch, {579: rss("05 Nov 2024 10:00:00 GMT"),
                                      1478: rss()})

    jobs = internships._amundi_jobs()

    assert len(jobs) == 1
    assert jobs[0].published == ""
    assert not jobs[0].published_inferred


def test_detail_publication_takes_priority_over_rss(monkeypatch):
    install_public_pages(monkeypatch, {579: rss("04 Nov 2024 10:00:00 GMT"), 1478: rss()},
                         detail_date="03/11/2024")

    assert internships._amundi_jobs()[0].published == "2024-11-03"


@pytest.mark.parametrize("dated_contract", [579, 1478])
def test_duplicates_fetch_one_detail_and_keep_confirmed_date(monkeypatch, dated_contract):
    feeds = {579: rss(repeats=2), 1478: rss(repeats=2)}
    feeds[dated_contract] = rss("04 Nov 2024 10:00:00 GMT", repeats=2)
    calls = install_public_pages(monkeypatch, feeds)

    jobs = internships._amundi_jobs()

    assert len(jobs) == 1
    assert jobs[0].published == "2024-11-04"
    assert sum(url == URL for url, _ in calls) == 1
    assert internships._deduplicate_opportunities(jobs + jobs) == jobs


@pytest.mark.skipif(os.getenv("LIVE_AMUNDI_RSS") != "1", reason="Public live check is opt-in")
def test_amundi_public_collection_live(monkeypatch):
    statuses = []
    original_get = internships.requests.get

    def get(url, **kwargs):
        response = original_get(url, **kwargs)
        statuses.append(response.status_code)
        return response

    monkeypatch.setattr(internships.requests, "get", get)
    started = perf_counter()
    jobs = internships._amundi_jobs()
    elapsed = perf_counter() - started
    unique = internships._deduplicate_opportunities(jobs)
    print(f"Amundi: {elapsed:.3f}s; offers={len(jobs)}; unique={len(unique)}; "
          f"dated={sum(bool(job.published) for job in unique)}; HTTP={sorted(statuses)}")
    for job in unique:
        print(f"{job.title} | {job.kind} | {job.location} | {job.published} | {job.url}")
    assert unique, "No usable market internship could be verified"
    assert all(job.url.startswith("https://jobs.amundi.com/") for job in unique)
    assert all(job.kind in {"Stage", "VIE"} and job.location for job in unique)
    assert all(job.description for job in unique)
    assert any(job.published and not job.published_inferred for job in unique)
