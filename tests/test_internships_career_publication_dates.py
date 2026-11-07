"""Career-page publication checks using synthetic HTML without network or data reads."""

import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from internships_project import internships
from internships_project.internships import _career_detail


@pytest.mark.parametrize("url,company,label", [
    ("https://jobs.amundi.com/offre-de-emploi/emploi-stage-trading_123.aspx",
     "Amundi", "Date de publication"),
    ("https://coveafinance-recrute.talent-soft.com/offre-de-emploi/emploi-stage-trading_123.aspx",
     "Covéa Finance", "Date de début de diffusion"),
])
@pytest.mark.parametrize("displayed,expected", [
    ("31/02/2026", ""),
    ("29/02/2026", ""),
    ("00/11/2026", ""),
    ("04/13/2026", ""),
    ("04/11/0000", ""),
    ("29/02/2024", "2024-02-29"),
    ("04/11/2026", "2026-11-04"),
])
def test_career_offer_survives_invalid_publication(url, company, label, displayed, expected):
    page = ("<h1>Stage Assistant Trading</h1>"
            "<p>Localisation Paris Niveau Bac+5 Type de contrat Stage "
            f"{label} : {displayed}</p>")

    job = _career_detail(url, company, html_override=page)

    assert job is not None
    assert job.url == url
    assert job.kind == "Stage"
    assert job.location == "Paris"
    assert job.published == expected
    assert not job.published_inferred
    assert displayed in job.description


@pytest.mark.parametrize("displayed,expected", [
    ("31.02.2026", ""),
    ("29.02.2024", "2024-02-29"),
])
def test_career_dotted_publication_dates(displayed, expected):
    job = _career_detail(
        "https://jobs.amundi.com/offre-de-emploi/emploi-stage-trading_123.aspx",
        "Amundi", html_override=("<h1>Stage Assistant Trading</h1>"
                                 "<p>Localisation Paris Niveau Bac+5 "
                                 f"Date de parution : {displayed}</p>"))

    assert job is not None
    assert job.published == expected


@pytest.mark.parametrize("displayed", ["31/02/2026", "31/12/9999"])
def test_structured_publication_keeps_priority_over_invalid_displayed_date(displayed):
    posting = json.dumps({"@type": "JobPosting", "datePosted": "2024-02-29"})
    job = _career_detail(
        "https://jobs.amundi.com/offre-de-emploi/emploi-stage-trading_123.aspx",
        "Amundi", html_override=("<h1>Stage Assistant Trading</h1>"
                                 "<p>Localisation Paris Niveau Bac+5 "
                                 f"Date de publication : {displayed}</p>"
                                 f'<script type="application/ld+json">{posting}</script>'))

    assert job is not None
    assert job.published == "2024-02-29"


def test_invalid_publication_reaches_board_as_detected_offer(monkeypatch):
    job = _career_detail(
        "https://jobs.amundi.com/offre-de-emploi/emploi-stage-trading_123.aspx",
        "Amundi", html_override=("<h1>Stage Assistant Trading</h1>"
                                 "<p>Localisation Paris Niveau Bac+5 "
                                 "Date de publication : 31/02/2026</p>"))
    assert job is not None
    now = datetime(2026, 11, 6, tzinfo=timezone.utc)
    writer = Mock()
    monkeypatch.setattr(internships, "_cache", None)
    monkeypatch.setattr(internships, "_last_attempt", now)
    monkeypatch.setattr(internships, "_refresh_previous_jobs", {})
    monkeypatch.setattr(internships, "_refresh_first_seen", {})
    monkeypatch.setattr(internships, "_write_cache", writer)

    internships._publish_refresh_progress([job], [])

    jobs = internships._cache[1]
    assert len(jobs) == 1
    assert jobs[0].url == job.url
    assert jobs[0].published == "2026-11-06"
    assert jobs[0].published_inferred
    assert internships.matching_opportunities(jobs, daily=True, today=now.date()) == jobs
    writer.assert_called_once_with(now, jobs, [])


@pytest.mark.parametrize("url,company,label", [
    ("https://jobs.amundi.com/offre-de-emploi/emploi-stage-trading_123.aspx",
     "Amundi", "Date de publication"),
    ("https://jobs.amundi.com/offre-de-emploi/emploi-stage-trading_123.aspx",
     "Amundi", "Date de parution"),
    ("https://coveafinance-recrute.talent-soft.com/offre-de-emploi/emploi-stage-trading_123.aspx",
     "Covéa Finance", "Date de début de diffusion"),
])
@pytest.mark.parametrize("displayed", ["07/11/2026", "07.11.2026", "06/11/2027"])
def test_future_publication_becomes_detection_without_losing_offer(monkeypatch, url, company, label, displayed):
    now = datetime(2026, 11, 6, 23, 30, tzinfo=timezone.utc)
    clock = Mock(wraps=datetime)
    clock.now.return_value = now
    monkeypatch.setattr(internships, "datetime", clock)
    job = _career_detail(
        url, company, html_override=("<h1>Stage Assistant Trading</h1>"
                                 "<p>Localisation Paris Niveau Bac+5 "
                                 f"{label} : {displayed}</p>"))
    assert job is not None
    assert job.published == ""
    writer = Mock()
    monkeypatch.setattr(internships, "_cache", None)
    monkeypatch.setattr(internships, "_last_attempt", now)
    monkeypatch.setattr(internships, "_refresh_previous_jobs", {})
    monkeypatch.setattr(internships, "_refresh_first_seen", {})
    monkeypatch.setattr(internships, "_write_cache", writer)

    internships._publish_refresh_progress([job], [])

    jobs = internships._cache[1]
    assert len(jobs) == 1
    assert jobs[0].url == job.url
    assert jobs[0].published == "2026-11-06"
    assert jobs[0].published_inferred
    assert internships.matching_opportunities(jobs, daily=True, today=now.date()) == jobs
    writer.assert_called_once_with(now, jobs, [])


@pytest.mark.parametrize("displayed,expected", [
    ("05/11/2026", "2026-11-05"),
    ("06/11/2026", "2026-11-06"),
])
def test_displayed_publication_accepts_today_and_past_in_utc(monkeypatch, displayed, expected):
    clock = Mock(wraps=datetime)
    clock.now.return_value = datetime(2026, 11, 6, 0, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(internships, "datetime", clock)

    assert internships._career_publication_date(displayed) == expected
