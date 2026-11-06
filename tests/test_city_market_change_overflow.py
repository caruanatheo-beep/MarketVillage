"""City keeps finite quotes without publishing overflowing derived movements."""

from dataclasses import replace
from datetime import datetime, timezone
import json

import pytest

from internships_project import city_services
from src import calendar, data, news
from src.models import MarketPoint


def quote(series="SP500", category="Risk", unit="index", previous=1, change=1e308):
    return MarketPoint(
        series, series, category, 1e308, previous, change,
        datetime.now(timezone.utc).date().isoformat(), unit, "daily",
        "latest available", "Fixture", f"https://example.org/{series}",
    )


@pytest.mark.parametrize("series,category,unit", [
    ("SP500", "Risk", "index"),
    ("DEXUSEU", "FX", "USD"),
    ("DCOILWTICO", "Commodities", "USD"),
    ("DGS2", "Rates", "%"),
    ("BAMLH0A0HYM2", "Credit", "%"),
])
@pytest.mark.parametrize("sign", [-1, 1])
def test_panel_preserves_quotes_when_converted_change_overflows(monkeypatch, series, category, unit, sign):
    point = quote(series, category, unit, change=sign * 1e308)
    healthy = quote("VIXCLS", previous=20, change=1)
    monkeypatch.setattr(data, "load_snapshot", lambda: ([point, healthy], {}))

    city_services._market_snapshot_cached.cache_clear()
    try:
        readings = city_services.market_snapshot()["points"]
    finally:
        city_services._market_snapshot_cached.cache_clear()

    assert len(readings) == 2
    assert readings[0]["value"] == point.value
    assert readings[0]["change"] == point.change
    assert readings[0]["change_display"] == "Variation indisponible (calcul hors limites)"
    assert readings[1]["change_display"] == "+5.00%"
    json.dumps(readings, allow_nan=False)


@pytest.mark.parametrize("previous,change", [(1e-308, 10), (1, 1e308), (1, -1e308)])
def test_mira_report_and_summary_do_not_publish_infinite_changes(monkeypatch, previous, change):
    points = [quote(previous=previous, change=change),
              quote("VIXCLS", previous=20, change=1),
              quote("DEXUSEU", "FX", "USD", previous, change),
              quote("BAMLH0A0HYM2", "Credit", "%", previous, 1e308)]
    monkeypatch.setattr(data, "load_snapshot", lambda: (points, {"state": "cached"}))
    monkeypatch.setattr(news, "load_news", lambda: ([], []))
    monkeypatch.setattr(news, "fetch_global_news", lambda: ([], []))
    monkeypatch.setattr(calendar, "load_calendar", lambda **kwargs: ([], None))

    result = city_services.run_agent("market_analyst", "fixture", {"operation": "collect_markets"})

    assert result["market_points"] == 4
    assert len(result["market_data"]) == 4
    assert "Variation indisponible (calcul hors limites)" in result["summary"]
    assert result["text"].count("Variation indisponible (calcul hors limites)") == 3
    assert "VIX +5.00%" in result["summary"]
    assert result["sentiment"]["signals"] == ["VIX +5.00%"]
    assert "inf%" not in result["text"]
    assert "inf bp" not in result["text"]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("category,unit,previous,change,display", [
    ("Risk", "index", 100, 2, "+2.00%"),
    ("Rates", "%", 4, -0.05, "-5.0 bp"),
    ("Policy", "%", 4, 0.25, "+25.0 bp"),
    ("Risk", "index", 0, 2, "+2.00"),
    ("Risk", "index", None, None, "N/A"),
    ("Risk", "index", 1, 1e300, f"{1e302:+.2f}%"),
])
def test_valid_changes_keep_existing_units_and_format(category, unit, previous, change, display):
    point = replace(quote(), category=category, unit=unit, previous=previous, change=change)

    assert city_services._market_change_display(point) == display
