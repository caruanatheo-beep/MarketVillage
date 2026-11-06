"""Unusual provider dates must not hide City's other market news."""

import pytest

from internships_project import city_services
from src import news
from src.models import NewsItem


@pytest.mark.parametrize("unusable_date", [
    "0001-01-01T00:00:00+01:00",
    "9999-12-31T23:30:00-01:00",
    "not a date",
])
def test_unusable_date_preserves_articles_and_latest_duplicate(monkeypatch, unusable_date):
    monkeypatch.setattr(news, "load_news", lambda: ([
        NewsItem("unusable", "Fixture", unusable_date, "https://example.org/a"),
        NewsItem("old copy", "Fixture", unusable_date, "https://example.org/b#old"),
        NewsItem("latest", "Fixture", "2026-11-05 18:18 UTC", "https://example.org/b"),
    ], []))

    result = city_services.market_news()

    assert result["total_unique"] == 2
    assert [(item["title"], item["date_known"]) for item in result["articles"]] == [
        ("latest", True), ("unusable", False),
    ]
    assert result["articles"][1]["published"] == unusable_date


def test_full_calendar_range_sorts_without_platform_timestamps(monkeypatch):
    monkeypatch.setattr(news, "load_news", lambda: ([
        NewsItem("unknown", "Fixture", "", "https://example.org/0"),
        NewsItem("earliest", "Fixture", "0001-01-01T00:00:00Z", "https://example.org/a"),
        NewsItem("latest", "Fixture", "9999-12-31T23:59:59Z", "https://example.org/z"),
        NewsItem("tie b", "Fixture", "2026-11-05T20:18:00+02:00", "https://example.org/c"),
        NewsItem("tie a", "Fixture", "2026-11-05 18:18 UTC", "https://example.org/b"),
    ], []))

    result = city_services.market_news()

    assert [item["title"] for item in result["articles"]] == [
        "latest", "tie a", "tie b", "earliest", "unknown",
    ]
    assert [item["date_known"] for item in result["articles"]] == [True] * 4 + [False]
