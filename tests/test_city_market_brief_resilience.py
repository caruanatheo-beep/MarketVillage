"""Mira preserves observed prices when independent enrichment sources fail."""

from dataclasses import replace
from datetime import datetime, timezone
from itertools import combinations

import pytest

from internships_project import city_services
from internships_project.marketdesk_city import CityError
from src import calendar, data, news
from src.models import CalendarEvent, MarketPoint, NewsItem


@pytest.fixture
def sources(monkeypatch):
    today = datetime.now(timezone.utc).date().isoformat()
    points = [
        MarketPoint(series, series, "Risk", value, previous, value - previous,
                    today, "index", "daily", "latest available", "Fixture",
                    f"https://example.org/{series}")
        for series, previous, value in [("SP500", 100, 98), ("VIXCLS", 20, 23)]
    ]
    monkeypatch.setattr(data, "load_snapshot", lambda: (points, {"state": "cached"}))
    monkeypatch.setattr(news, "load_news", lambda: ([NewsItem(
        "Monetary policy decision", "ECB", today, "https://example.org/policy")], []))
    monkeypatch.setattr(news, "fetch_global_news", lambda: ([NewsItem(
        "Stocks fall", "Reuters", today, "https://example.org/stocks")], []))
    monkeypatch.setattr(calendar, "load_calendar", lambda **kwargs: ([CalendarEvent(
        today, "12:00", "Policy meeting", "ECB", "https://example.org/meeting")], None))
    return {
        "official": (news, "load_news", "Publications officielles"),
        "global": (news, "fetch_global_news", "Actualités de marché"),
        "calendar": (calendar, "load_calendar", "Calendrier"),
    }


FAILURES = [subset for size in range(4)
            for subset in combinations(("official", "global", "calendar"), size)]


@pytest.mark.parametrize("failed", FAILURES)
def test_mira_delivers_available_sources_and_explains_each_failure(monkeypatch, sources, failed):
    def unavailable(*args, **kwargs):
        raise RuntimeError("synthetic provider detail must not reach the report")

    for name in failed:
        module, method, _ = sources[name]
        monkeypatch.setattr(module, method, unavailable)

    result = city_services.run_agent("market_analyst", "fixture", {"operation": "collect_markets"})

    assert result["market_points"] == 2
    assert len(result["market_data"]) == 2
    assert len(result["sentiment"]["signals"]) == 2
    assert result["sentiment"]["confidence"] == ("faible" if "global" in failed else "modérée")
    assert result["data_status"] == {"state": "cached"}
    assert result["headlines"] == (0 if "official" in failed else 1)
    assert result["calendar_events"] == (0 if "calendar" in failed else 1)
    assert ("Monetary policy decision" in result["text"]) == ("official" not in failed)
    assert ("Policy meeting" in result["text"]) == ("calendar" not in failed)
    assert ("Stocks fall" in result["text"]) == ("global" not in failed)
    assert len(result["warnings"]) == len(failed)
    for name in failed:
        assert any(sources[name][2] in warning for warning in result["warnings"])
    for warning in result["warnings"]:
        # The existing task/memory callers publish text, so warnings belong there too.
        assert warning in result["text"][:3500]
    assert "synthetic provider detail" not in str(result)
    assert result["text"].startswith("## Sources incomplètes" if failed else "## Analyse")


@pytest.mark.parametrize("raises", [False, True])
def test_missing_prices_still_fail_without_calling_enrichment(monkeypatch, sources, raises):
    def snapshot():
        if raises:
            raise RuntimeError("synthetic source detail")
        return [], {}

    def forbidden(*args, **kwargs):
        pytest.fail("No enrichment should run without observed prices")

    monkeypatch.setattr(data, "load_snapshot", snapshot)
    for module, method, _ in sources.values():
        monkeypatch.setattr(module, method, forbidden)

    with pytest.raises(CityError) as error:
        city_services.run_agent("market_analyst", "fixture", {"operation": "collect_markets"})
    assert "synthetic source detail" not in str(error.value)


def test_provider_warnings_are_also_visible_in_the_report(monkeypatch, sources):
    monkeypatch.setattr(news, "load_news", lambda: ([], ["Official feed unavailable"]))
    monkeypatch.setattr(calendar, "load_calendar", lambda **kwargs: ([], "Calendar incomplete"))

    result = city_services.market_brief()

    assert result["warnings"] == ["Official feed unavailable", "Calendar incomplete"]
    assert all(warning in result["text"] for warning in result["warnings"])


@pytest.mark.parametrize("field", ["value", "previous", "change"])
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_brief_excludes_invalid_prices_from_facts_counts_and_shared_report(monkeypatch, sources, field, invalid):
    points, status = data.load_snapshot()
    valid = replace(points[1], previous=None, change=None)
    damaged = [replace(points[0], series_id=series, **{field: invalid})
               for series in ("SP500", "DGS10", "DEXUSEU", "BAMLH0A0HYM2")]
    # A valid short rate makes an invalid long rate reach the curve calculation.
    short_rate = replace(points[0], series_id="DGS2", value=4, previous=4, change=0)
    monkeypatch.setattr(data, "load_snapshot", lambda: ([valid, short_rate], status))
    expected = city_services.market_brief()
    monkeypatch.setattr(data, "load_snapshot", lambda: (damaged + [valid, short_rate], status))

    result = city_services.run_agent("market_analyst", "fixture", {"operation": "collect_markets"})

    for key in ("market_points", "market_data", "summary", "sentiment", "data_status"):
        assert result[key] == expected[key]
    assert result["market_points"] == 2
    assert len(result["warnings"]) == 1
    assert "4" in result["warnings"][0]
    assert result["warnings"][0] in result["text"][:3500]
    assert result["text"].endswith(expected["text"])


@pytest.mark.parametrize("invalid", [None, float("nan"), float("inf"), float("-inf")])
def test_only_invalid_prices_fail_before_enrichment(monkeypatch, sources, invalid):
    points, status = data.load_snapshot()
    monkeypatch.setattr(data, "load_snapshot", lambda: ([replace(points[0], value=invalid)], status))

    def forbidden(*args, **kwargs):
        pytest.fail("No enrichment should run without usable prices")

    for module, method, _ in sources.values():
        monkeypatch.setattr(module, method, forbidden)

    with pytest.raises(CityError, match="aucune observation exploitable"):
        city_services.run_agent("market_analyst", "fixture", {"operation": "collect_markets"})
