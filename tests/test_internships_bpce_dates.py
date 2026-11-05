"""BPCE date checks using synthetic responses without network or data reads."""

from unittest.mock import Mock, patch

import pytest

from internships_project.internships import _bpce_open_data_jobs


@pytest.mark.parametrize("invalid_date", ["31/02/2026", "29/02/2026", "00/11/2026", "04/13/2026"])
def test_invalid_publication_date_keeps_offer_and_remaining_feed(invalid_date):
    dates = ["04/11/2026", invalid_date, "29/02/2024", "2026-11-03", ""]
    rows = [
        {
            "title": "Stage Assistant Trading",
            "company": "Synthetic Bank",
            "location": "Paris",
            "contract": "Stage",
            "published": published,
            "url": f"https://recrutement.bpce.fr/job/synthetic-{index}",
        }
        for index, published in enumerate(dates)
    ]
    response = Mock()
    response.json.return_value = rows
    with patch("internships_project.internships.requests.get", return_value=response):
        jobs = _bpce_open_data_jobs()

    assert [job.url for job in jobs] == [row["url"] for row in rows]
    assert [job.published for job in jobs] == ["2026-11-04", "", "2024-02-29", "2026-11-03", ""]
    assert all(not job.published_inferred for job in jobs)
