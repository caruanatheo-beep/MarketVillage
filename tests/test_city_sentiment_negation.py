"""Negated headlines must not corroborate a directional market brief."""

from datetime import datetime, timezone

import pytest

from internships_project import city_services
from src import calendar, data, news
from src.models import MarketPoint, NewsItem


@pytest.mark.parametrize("direction,movement", [(1, "rise"), (-1, "fall")])
@pytest.mark.parametrize("phrase", [
    "do not {movement}", "never {movement}", "no longer {movement}",
    "fail to {movement}", "failed to {movement}", "unable to {movement}",
    "don't {movement}", "didn’t {movement}", "DO NOT {movement}",
])
def test_negated_headline_cannot_strengthen_agent_brief(monkeypatch, direction, movement, phrase):
    today = datetime.now(timezone.utc).date().isoformat()
    points = [
        MarketPoint(series, series, "Risk", value, previous, value - previous,
                    today, "index", "daily", "latest available", "Fixture",
                    f"https://example.org/{series}")
        for series, previous, value in [
            ("SP500", 100, 100 + direction * 2),
            ("VIXCLS", 20, 20 - direction * 3),
        ]
    ]
    headline = "Stocks " + phrase.format(movement=movement)
    articles = [NewsItem(headline, "Reuters", today, "https://example.org/story")]
    monkeypatch.setattr(data, "load_snapshot", lambda: (points, {}))
    monkeypatch.setattr(news, "load_news", lambda: ([], []))
    monkeypatch.setattr(news, "fetch_global_news", lambda: (articles, []))
    monkeypatch.setattr(calendar, "load_calendar", lambda **kwargs: ([], None))

    result = city_services.run_agent("market_analyst", "synthetic-user", {"operation": "collect_markets"})

    assert len(result["sentiment"]["signals"]) == 2
    assert result["sentiment"]["confidence"] == "faible"
    assert result["sentiment"]["supporting_news"] == []
    assert headline not in result["text"]


def test_negation_after_lead_does_not_discard_explicit_market_move():
    today = datetime.now(timezone.utc).date().isoformat()
    points = [
        MarketPoint(series, series, "Risk", value, previous, value - previous,
                    today, "index", "daily", "latest available", "Fixture",
                    f"https://example.org/{series}")
        for series, previous, value in [("SP500", 100, 102), ("VIXCLS", 20, 17)]
    ]
    article = NewsItem("Stocks notch gains as bonds fail to rise", "Reuters", today,
                       "https://example.org/story")

    result = city_services._market_sentiment(points, [article])

    assert result["confidence"] == "modérée"
    assert result["supporting_news"][0]["title"] == article.title
