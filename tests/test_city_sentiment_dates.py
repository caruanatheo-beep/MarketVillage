"""Mira must not turn asynchronous daily variations into a common market move."""

from datetime import datetime, timezone

import pytest

from internships_project import city_services
from src import calendar, data, news
from src.models import MarketPoint, NewsItem


@pytest.fixture
def brief_sources(monkeypatch):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 6, 12, tzinfo=timezone.utc)

    monkeypatch.setattr(city_services, "datetime", FixedDatetime)
    monkeypatch.setattr(news, "load_news", lambda: ([], []))
    monkeypatch.setattr(calendar, "load_calendar", lambda **kwargs: ([], None))


def point(series, day, previous, change):
    credit = series == "BAMLH0A0HYM2"
    return MarketPoint(series, series, "Credit" if credit else "Risk",
                       previous + change, previous, change, day,
                       "%" if credit else "index", "daily", "latest available",
                       "Fixture", f"https://example.org/{series}")


@pytest.mark.parametrize("direction", [-1, 1])
@pytest.mark.parametrize("second_series", ["VIXCLS", "BAMLH0A0HYM2"])
@pytest.mark.parametrize("second_day,comparable", [
    ("2026-11-06", True),
    ("2026-11-05", False),
    # Compare UTC observation days rather than raw timestamp prefixes.
    ("2026-11-07T00:30:00+02:00", True),
    ("2026-11-06T00:30:00+02:00", False),
])
def test_mira_requires_contemporaneous_directional_signals(
    monkeypatch, brief_sources, direction, second_series, second_day, comparable,
):
    points = [point("SP500", "2026-11-06", 100, direction * 2),
              point(second_series, second_day,
                    20 if second_series == "VIXCLS" else 3,
                    -direction * (2 if second_series == "VIXCLS" else 0.05))]
    monkeypatch.setattr(data, "load_snapshot", lambda: (points, {"state": "cached"}))
    headline = "Stocks rise" if direction > 0 else "Stocks fall"
    monkeypatch.setattr(news, "fetch_global_news", lambda: ([NewsItem(
        headline, "Reuters", "2026-11-06", "https://example.org/stocks")], []))

    result = city_services.run_agent("market_analyst", "synthetic", {"operation": "collect_markets"})

    sentiment = result["sentiment"]
    assert result["market_points"] == 2
    assert len(result["market_data"]) == 2
    assert len(sentiment["signals"]) == 2
    assert sentiment["label"] == (
        ("Constructif" if direction > 0 else "Défensif") if comparable else "Mitigé")
    assert sentiment["confidence"] == ("modérée" if comparable else "faible")
    assert bool(sentiment["supporting_news"]) == comparable
    assert len(set(sentiment["signal_dates"].values())) == (1 if comparable else 2)
    assert sentiment["signal_dates"]["Actions"] == "2026-11-06"
    if not comparable:
        assert "dates d'observation différentes" in result["text"]
        assert "2026-11-05" in result["text"]
        assert result["summary"].startswith("Mitigé")
    else:
        assert "dates d'observation différentes" not in result["text"]


def test_quiet_older_indicator_does_not_invalidate_same_day_signals(monkeypatch, brief_sources):
    points = [point("SP500", "2026-11-06", 100, -2),
              point("VIXCLS", "2026-11-06", 20, 2),
              point("BAMLH0A0HYM2", "2026-11-05", 3, 0.01)]
    monkeypatch.setattr(data, "load_snapshot", lambda: (points, {}))
    monkeypatch.setattr(news, "fetch_global_news", lambda: ([], []))

    result = city_services.market_brief()

    assert result["sentiment"]["label"] == "Défensif"
    assert result["sentiment"]["signal_dates"] == {
        "Actions": "2026-11-06", "Volatilité": "2026-11-06"}


@pytest.mark.parametrize("direction", [-1, 1])
@pytest.mark.parametrize("observed,published,corroborates", [
    ("2026-11-06", "2026-11-05", False),
    ("2026-11-05", "2026-11-06", False),
    ("2026-11-05", "2026-11-05", True),
    ("2026-11-06", "2026-11-07T00:30:00+02:00", True),
    ("2026-11-06", "2026-11-06T00:30:00+02:00", False),
])
def test_brief_corroboration_requires_the_observed_session(
    monkeypatch, brief_sources, direction, observed, published, corroborates,
):
    points = [point("SP500", observed, 100, direction * 2),
              point("VIXCLS", observed, 20, -direction * 2)]
    monkeypatch.setattr(data, "load_snapshot", lambda: (points, {}))
    headline = "Stocks rise" if direction > 0 else "Stocks fall"
    monkeypatch.setattr(news, "fetch_global_news", lambda: ([NewsItem(
        headline, "Reuters", published, "https://example.org/session")], []))

    result = city_services.run_agent("market_analyst", "synthetic", {"operation": "collect_markets"})

    sentiment = result["sentiment"]
    assert sentiment["label"] == ("Constructif" if direction > 0 else "Défensif")
    assert len(sentiment["signals"]) == 2
    assert sentiment["confidence"] == ("modérée" if corroborates else "faible")
    assert bool(sentiment["supporting_news"]) == corroborates
    assert (headline in result["text"]) == corroborates
    assert ("même date UTC" in result["text"]) != corroborates
    assert len(result["market_data"]) == 2
