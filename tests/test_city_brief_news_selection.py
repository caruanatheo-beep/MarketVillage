"""The City brief cites the newest distinct corroborating articles."""

from datetime import datetime, timedelta, timezone

import pytest

from internships_project import city_services
from src import calendar, data, news
from src.models import MarketPoint, NewsItem


@pytest.mark.parametrize("direction", [-1, 1])
def test_mira_selects_recent_distinct_articles_through_agent(monkeypatch, direction):
    now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    today = now.date().isoformat()
    points = [
        MarketPoint(series, series, "Risk", value, previous, value - previous,
                    today, "index", "daily", "latest available", "Fixture",
                    f"https://example.org/{series}")
        for series, previous, value in [
            ("SP500", 100, 100 + direction * 2),
            ("VIXCLS", 20, 20 - direction * 3),
        ]
    ]
    title = "Stocks rise" if direction > 0 else "Stocks fall"
    # The feed is unordered; fragments and trailing slashes refer to one story.
    articles = [
        NewsItem(title + " older", "Reuters", (now - timedelta(days=2)).isoformat(), "https://example.org/older"),
        NewsItem(title + " newest", "Reuters", now.isoformat(), "https://example.org/latest#top"),
        NewsItem(title + " duplicate", "Reuters", (now - timedelta(minutes=1)).isoformat(), "https://example.org/latest/"),
        NewsItem(title + " other", "Bloomberg", (now - timedelta(hours=1)).astimezone(timezone(timedelta(hours=3))).isoformat(), "https://example.org/other"),
        NewsItem(title + " unknown", "Reuters", "not a date", "https://example.org/unknown"),
    ]
    monkeypatch.setattr(data, "load_snapshot", lambda: (points, {}))
    monkeypatch.setattr(news, "load_news", lambda: ([], []))
    monkeypatch.setattr(news, "fetch_global_news", lambda: (articles, []))
    monkeypatch.setattr(calendar, "load_calendar", lambda **kwargs: ([], None))

    result = city_services.run_agent("market_analyst", "synthetic-user", {"operation": "collect_markets"})

    cited = result["sentiment"]["supporting_news"]
    assert [item["title"] for item in cited] == [title + " newest", title + " other"]
    assert result["sentiment"]["confidence"] == "modérée"
    assert title + " newest" in result["text"]
    assert title + " other" in result["text"]
    assert title + " duplicate" not in result["text"]
    assert title + " older" not in result["text"]


def test_repeated_story_is_cited_only_once():
    today = datetime.now(timezone.utc).date().isoformat()
    points = [
        MarketPoint(series, series, "Risk", value, previous, value - previous,
                    today, "index", "daily", "latest available", "Fixture", "https://example.org")
        for series, previous, value in [("SP500", 100, 98), ("VIXCLS", 20, 23)]
    ]
    result = city_services._market_sentiment(points, [
        NewsItem("Stocks fall", "Reuters", today, url)
        for url in ["https://example.org/story", "https://example.org/story/#section"]
    ])
    assert len(result["supporting_news"]) == 1
