"""ODDO collection checks with synthetic PDFs and no network or data reads."""

from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import Mock

import pytest
from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject, DictionaryObject, NameObject,
)

from internships_project import internships


def _offer_pdf(text):
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
    })
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 20 700 Td ({text}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = stream
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _collect(monkeypatch, displayed, label="First publication date"):
    root = "https://recrutement.altays-progiciels.com/oddo/"
    urls = [root + "first.pdf", root + "second.pdf"]
    listing = "".join(f'<a href="{url}">Stage Assistant Trading</a>' for url in urls)
    responses = {internships.ODDO_ALTAYS_LISTING: Mock(text=listing)}
    for url, value in zip(urls, [displayed, "04/11/2026"]):
        publication = f" {label} : {value}" if value else ""
        responses[url] = Mock(content=_offer_pdf(
            "Localisation : Paris Type de contrat : Stage" + publication))
    get = Mock(side_effect=lambda url, **kwargs: responses[url])
    monkeypatch.setattr(internships.requests, "get", get)
    jobs = internships._oddo_jobs()
    assert get.call_count == 3
    assert [job.url for job in jobs] == urls
    assert all(job.kind == "Stage" and job.location == "Paris" for job in jobs)
    assert jobs[1].published == "2026-11-04"
    return jobs


@pytest.mark.parametrize("label", ["First publication date", "Date de publication"])
@pytest.mark.parametrize("displayed,expected", [
    ("31/02/2026", ""),
    ("29/02/2026", ""),
    ("04/13/2026", ""),
    ("04/11/0000", ""),
    ("29/02/2024", "2024-02-29"),
    ("", ""),
])
def test_oddo_keeps_offers_when_pdf_publication_is_invalid(
        monkeypatch, label, displayed, expected):
    jobs = _collect(monkeypatch, displayed, label)
    assert jobs[0].published == expected
    assert not jobs[0].published_inferred


def test_invalid_oddo_date_becomes_detection_date_in_daily_results(monkeypatch):
    job = _collect(monkeypatch, "31/02/2026")[0]
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
