"""News must be dated and recent before corroborating City's market sentiment."""

from datetime import datetime, timezone

import pytest

from internships_project import city_services
from src.models import MarketPoint, NewsItem


@pytest.mark.parametrize("published,eligible", [
    ("2026-11-05", True),
    ("2026-11-01", True),
    ("2026-10-31", False),
    ("2025-11-05", False),
    ("2026-11-06", False),
    ("", False),
    ("time unavailable", False),
    ("not a date", False),
    ("2026-11-05 09:00 UTC", True),
    ("2026-11-01T00:30:00+02:00", False),
    ("2026-10-31T23:30:00-02:00", True),
])
@pytest.mark.parametrize("constructive", [False, True])
def test_only_recent_dated_news_can_strengthen_sentiment(monkeypatch, published, eligible, constructive):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 5, 12, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(city_services, "datetime", FixedDatetime)
    prices = []
    for series, previous, value in [
        ("SP500", 100, 102 if constructive else 98),
        ("VIXCLS", 20, 18 if constructive else 23),
    ]:
        prices.append(MarketPoint(
            series, series, "Risk", value, previous, value - previous,
            "2026-11-05", "index", "daily", "latest available", "FRED",
            f"https://example.org/{series}",
        ))
    headline = NewsItem(
        "Stocks rise" if constructive else "Stocks fall", "Reuters", published,
        "https://example.org/news",
    )

    result = city_services._market_sentiment(prices, [headline])

    assert len(result["signals"]) == 2
    assert result["confidence"] == ("modérée" if eligible else "faible")
    assert result["supporting_news"] == ([{
        "title": headline.title, "url": headline.url, "source": headline.source,
        "published": published,
    }] if eligible else [])
