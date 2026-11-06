"""News must be dated and recent before corroborating City's market sentiment."""

from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest
from starlette.responses import JSONResponse

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


@pytest.mark.parametrize("series", ["SP500", "VIXCLS", "BAMLH0A0HYM2"])
@pytest.mark.parametrize("field,value", [
    ("value", None),
    ("value", float("nan")),
    ("value", float("inf")),
    ("previous", float("inf")),
    ("change", float("inf")),
    ("change", float("-inf")),
    ("change", float("nan")),
    ("value", "unavailable"),
    ("previous", "100"),
    ("change", []),
    ("value", True),
    pytest.param("change", 10 ** 400, id="integer-overflow"),
])
def test_invalid_observations_cannot_strengthen_market_sentiment(series, field, value):
    today = datetime.now(timezone.utc).date().isoformat()
    points = [
        MarketPoint(key, key, "Risk", current, previous, current - previous,
                    today, "index", "daily", "latest available", "Fixture",
                    f"https://example.org/{key}")
        for key, previous, current in [
            ("SP500", 100, 98), ("VIXCLS", 20, 23), ("BAMLH0A0HYM2", 3, 3.1),
        ]
    ]
    damaged = [replace(point, **{field: value}) if point.series_id == series else point
               for point in points]

    expected = city_services._market_sentiment(
        [point for point in points if point.series_id != series], [])
    result = city_services._market_sentiment(damaged, [])

    assert len(expected["signals"]) == 2
    assert result == expected


@pytest.mark.parametrize("series", ["SP500", "VIXCLS", "BAMLH0A0HYM2"])
def test_overflowing_moves_do_not_produce_market_signals(series):
    today = datetime.now(timezone.utc).date().isoformat()
    point = MarketPoint(series, series, "Risk", 1e308, 0.1, 1e308,
                        today, "index", "daily", "latest available", "Fixture",
                        f"https://example.org/{series}")

    result = city_services._market_sentiment([point], [])

    assert result == city_services._market_sentiment([], [])


@pytest.mark.parametrize("field", ["value", "previous", "change"])
@pytest.mark.parametrize("invalid", [
    float("nan"), float("inf"), float("-inf"),
    "unavailable", "102.5", [], {}, True, False,
    pytest.param(10 ** 400, id="integer-overflow"),
])
def test_invalid_reading_does_not_hide_valid_market_quotes(monkeypatch, field, invalid):
    from src import data

    today = datetime.now(timezone.utc).date().isoformat()
    valid = MarketPoint("SP500", "S&P 500", "Risk", 102, 100, 2,
                        today, "index", "daily", "latest available", "Fixture",
                        "https://example.org/SP500")
    damaged = replace(valid, series_id="VIXCLS", **{field: invalid})

    monkeypatch.setattr(data, "load_snapshot", lambda: ([damaged, valid], {}))
    city_services._market_snapshot_cached.cache_clear()
    try:
        readings = city_services.market_snapshot()["points"]
    finally:
        city_services._market_snapshot_cached.cache_clear()
    # City uses a strict JSON response: one non-finite value used to make
    # serialization fail and the route return an empty market panel.
    response = JSONResponse({"points": readings})

    assert json.loads(response.body)["points"] == city_services._market_readings([valid])
    assert [point["series_id"] for point in readings] == ["SP500"]


def test_missing_previous_reading_preserves_current_market_quote():
    point = MarketPoint("SP500", "S&P 500", "Risk", 102, None, None,
                        "2026-11-05", "index", "daily", "latest available", "Fixture",
                        "https://example.org/SP500")

    response = JSONResponse({"points": city_services._market_readings([point])})

    reading, = json.loads(response.body)["points"]
    assert reading["value"] == 102
    assert reading["previous"] is None
    assert reading["change"] is None
    assert reading["change_display"] == "N/A"
