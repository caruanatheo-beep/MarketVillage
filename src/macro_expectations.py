from __future__ import annotations

import csv
import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import requests

from .config import ROOT, settings
from .models import CalendarEvent, MarketPoint

EXPECTATIONS_FILE = ROOT / "data" / "macro_expectations.csv"
TE_ENDPOINT = "https://api.tradingeconomics.com/calendar/country/{countries}/{start}/{end}"


def _key(date: str, title: str) -> tuple[str, str]:
    words = re.sub(r"[^a-z0-9 ]", " ", title.casefold())
    return date, " ".join(words.split())


def _reaction(points: list[MarketPoint], region: str) -> str:
    ids = {
        "United States": ("DGS2", "DGS10", "SP500", "DEXUSEU"),
        "Euro Area": ("DEXUSEU", "DGS10", "SP500"),
        "United Kingdom": ("DEXUSUK", "DGS10", "SP500"),
    }.get(region, ("SP500", "VIXCLS", "DEXUSEU"))
    values = {point.series_id: point for point in points}
    parts = []
    for series_id in ids:
        point = values.get(series_id)
        if point and point.change is not None:
            suffix = " bp" if point.unit == "%" and point.category in {"Rates", "Policy", "Credit"} else "%"
            parts.append(f"{point.label} {point.change:+.2f}{suffix}")
    return ", ".join(parts[:3]) + " (latest observed moves; event attribution unverified)" if parts else "unavailable"


def fetch_market_expectations(days_back: int = 3, days_ahead: int = 30) -> tuple[list[CalendarEvent], str]:
    """Retrieve market previous/consensus/actual values from Trading Economics."""
    key = settings.trading_economics_api_key
    if not key:
        return [], "Consensus provider not configured"
    today = datetime.now(timezone.utc).date()
    url = TE_ENDPOINT.format(
        countries="united states,united kingdom,euro area",
        start=(today - timedelta(days=days_back)).isoformat(),
        end=(today + timedelta(days=days_ahead)).isoformat(),
    )
    try:
        response = requests.get(
            url,
            params={"c": key, "f": "json"},
            headers={"User-Agent": "AI-Sales-Desk-Assistant/3.1"},
            timeout=(4, min(settings.request_timeout + 4, 15)),
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return [], "Consensus provider returned an unexpected response"
        regions = {"United States": "United States", "United Kingdom": "United Kingdom", "Euro Area": "Euro Area"}
        events: list[CalendarEvent] = []
        for row in payload:
            country = regions.get(str(row.get("Country", "")))
            if not country:
                continue
            if int(row.get("Importance") or 1) < 2:
                continue
            raw_date = str(row.get("Date", ""))
            try:
                dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dt = dt.astimezone(timezone.utc)
            except ValueError:
                continue
            importance = {1: "Low", 2: "Medium", 3: "High"}.get(int(row.get("Importance") or 2), "Medium")
            source_url = str(row.get("SourceURL") or "").strip()
            if not source_url.startswith("http"):
                detail = str(row.get("URL") or "")
                source_url = "https://tradingeconomics.com" + detail if detail.startswith("/") else "https://tradingeconomics.com/calendar"
            category = str(row.get("Category") or "Macro release")
            actual = str(row.get("Actual") or "unavailable")
            events.append(CalendarEvent(
                date=dt.strftime("%Y-%m-%d"), time=dt.strftime("%H:%M UTC"),
                title=str(row.get("Event") or category)[:180], institution=str(row.get("Source") or "Official source")[:100],
                url=source_url, status="market calendar", region=country,
                importance=importance, event_type=category,
                previous=str(row.get("Previous") or "unavailable"),
                consensus=str(row.get("Forecast") or "unavailable"), actual=actual,
            ))
        return events, f"Market expectations: {len(events)} events"
    except (requests.RequestException, ValueError, TypeError) as exc:
        return [], f"Consensus provider unavailable ({type(exc).__name__})"


def _similar(left: str, right: str) -> bool:
    a = set(_key("", left)[1].split())
    b = set(_key("", right)[1].split())
    return len(a & b) >= 2 or (a and b and len(a & b) / min(len(a), len(b)) >= 0.55)


def enrich_events(events: list[CalendarEvent], points: list[MarketPoint], market_events: list[CalendarEvent] | None = None) -> list[CalendarEvent]:
    records: dict[tuple[str, str], dict[str, str]] = {}
    try:
        with EXPECTATIONS_FILE.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                records[_key(row.get("date", ""), row.get("title", ""))] = row
    except OSError:
        pass
    market_events = list(market_events or [])
    output = []
    for event in events:
        record = records.get(_key(event.date, event.title), {})
        provider = next((item for item in market_events if item.date == event.date and item.region == event.region and _similar(item.title, event.title)), None)
        previous = record.get("previous") or (provider.previous if provider else "") or event.previous
        consensus = record.get("consensus") or (provider.consensus if provider else "") or event.consensus
        actual = record.get("actual") or (provider.actual if provider else "") or event.actual
        output.append(replace(
            event,
            previous=previous, consensus=consensus, actual=actual,
            market_reaction=_reaction(points, event.region) if actual != "unavailable" else event.market_reaction,
        ))
    # Keep recent releases and forecast-bearing events that are absent from the smaller official schedule.
    for provider in market_events:
        if not any(item.date == provider.date and item.region == provider.region and _similar(item.title, provider.title) for item in output):
            reaction = _reaction(points, provider.region) if provider.actual != "unavailable" else provider.market_reaction
            output.append(replace(provider, market_reaction=reaction))
    return sorted(output, key=lambda event: (event.date, event.time, event.title))[:100]
