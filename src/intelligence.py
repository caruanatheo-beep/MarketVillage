from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from .analytics import format_change, format_value
from .models import CalendarEvent, MarketPoint, NewsItem

PROFILES = ("Rates Sales", "FX Sales", "Cross-Asset", "Market Risk")
PROFILE_CATEGORIES = {
    "Rates Sales": ("Rates", "Policy", "Credit", "Macro"),
    "FX Sales": ("FX", "Rates", "Policy", "Macro"),
    "Cross-Asset": ("Risk", "Rates", "FX", "Commodities", "Credit", "Macro"),
    "Market Risk": ("Risk", "Credit", "Rates", "FX", "Commodities"),
}


def material_moves(points: list[MarketPoint], profile: str, limit: int = 5) -> list[MarketPoint]:
    categories = PROFILE_CATEGORIES.get(profile, PROFILE_CATEGORIES["Cross-Asset"])
    available = [point for point in points if point.value is not None and point.change is not None and point.category in categories]
    def score(point: MarketPoint) -> float:
        multiplier = 0.12 if point.unit == "bp" else 1.0
        return abs(float(point.change)) * multiplier
    return sorted(available, key=score, reverse=True)[:limit]


def movement_analysis(points: list[MarketPoint], news: list[NewsItem], events: list[CalendarEvent], profile: str) -> str:
    moves = material_moves(points, profile, 4)
    facts = [f"- **{point.label}: {format_value(point)} ({format_change(point)})**, observed {point.date}." for point in moves]
    keywords = set()
    for point in moves:
        keywords.update(re.findall(r"[a-z]{3,}", f"{point.label} {point.category}".casefold()))
    matched = [item for item in news if keywords & set(re.findall(r"[a-z]{3,}", item.title.casefold()))][:3]
    drivers = [f"- Possible driver: [{item.title}]({item.url}) ({item.source}, {item.published})." for item in matched]
    upcoming = [f"- **{event.date} {event.time}:** [{event.title}]({event.url})" for event in events[:3]]
    confidence = "Medium" if len(matched) >= 2 else "Low"
    return (
        "### Observed facts\n\n" + ("\n".join(facts) or "- No material move is available.") +
        "\n\n### Possible drivers\n\n" + ("\n".join(drivers) or "- No timely official headline matches the move; causality is unverified.") +
        f"\n\n### Confidence\n\n**{confidence}**. This is an evidence match, not proof of causality." +
        "\n\n### Next catalysts\n\n" + ("\n".join(upcoming) or "- No verified upcoming catalyst is available.")
    )


def surprise_text(event: CalendarEvent) -> str:
    def number(value: str) -> float | None:
        match = re.search(r"[-+]?\d+(?:\.\d+)?", value or "")
        return float(match.group()) if match else None
    actual, consensus = number(event.actual), number(event.consensus)
    if actual is None or consensus is None:
        return event.surprise
    suffix = "pp" if "%" in event.actual or "%" in event.consensus else ""
    return f"{actual - consensus:+.2f}{suffix} vs consensus"


def profiled_brief(points: list[MarketPoint], events: list[CalendarEvent], news: list[NewsItem], profile: str) -> str:
    moves = material_moves(points, profile, 6)
    market = "\n".join(f"- **{item.label}: {format_value(item)}** ({format_change(item)}), {item.date}." for item in moves)
    catalysts = "\n".join(
        f"- **{event.date} {event.time}:** [{event.title}]({event.url}); previous {event.previous}, consensus {event.consensus}, actual {event.actual}, surprise {surprise_text(event)}."
        for event in events[:4]
    )
    headlines = "\n".join(f"- [{item.title}]({item.url}) ({item.source}, {item.published})" for item in news[:3])
    return f"""## {profile} Brief

### Priority market moves

{market or '- Insufficient verified market data.'}

### Expectations and catalysts

{catalysts or '- No verified event is currently available.'}

### Official intelligence

{headlines or '- No current official publication was retrieved.'}

### Desk interpretation

{movement_analysis(points, news, events, profile)}
"""
