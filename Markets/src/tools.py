from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .models import CalendarEvent, Evidence, MarketPoint, NewsItem, ToolResult
from .security import safe_text
from .intelligence import material_moves, movement_analysis, surprise_text
from .analytics import format_change, format_value
from .web_search import search_official_web


@dataclass
class ToolContext:
    query: str
    points: list[MarketPoint]
    news: list[NewsItem]
    events: list[CalendarEvent]
    profile: str = "Cross-Asset"


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    handler: Callable[[ToolContext], ToolResult]


def _snapshot(context: ToolContext) -> ToolResult:
    terms = set(context.query.casefold().replace("/", " ").split())
    selected = [point for point in context.points if point.value is not None and (
        not terms or any(term in f"{point.label} {point.category}".casefold() for term in terms)
    )]
    if len(selected) < 4:
        selected = [point for point in context.points if point.value is not None]
    selected = selected[:24]
    evidence = [Evidence(
        claim=(f"{point.label}: {point.value} {point.unit} at {point.date}; previous "
               f"{point.previous} at {point.previous_date or 'unavailable'}; change {point.change}; status {point.status}"),
        value=str(point.value), source=point.source_name, url=point.source_url,
        observation_date=point.date, evidence_type="observed market or macro value",
        confidence="medium" if point.source_name.startswith("Yahoo") else "high",
    ) for point in selected]
    summary = "\n".join(item.claim for item in evidence)
    return ToolResult("market_snapshot", summary, evidence)


def _news(context: ToolContext) -> ToolResult:
    evidence = [Evidence(
        claim=safe_text(item.title, 280), source=item.source, url=item.url,
        observation_date=item.published, evidence_type="official headline", confidence="medium",
    ) for item in context.news[:10]]
    return ToolResult("official_news", "\n".join(item.claim for item in evidence), evidence)


def _central_banks(context: ToolContext) -> ToolResult:
    markers = ("reserve", "central bank", "england", "japan")
    items = [item for item in context.news if any(marker in item.source.casefold() for marker in markers)]
    evidence = [Evidence(
        claim=safe_text(item.title, 280), source=item.source, url=item.url,
        observation_date=item.published, evidence_type="central-bank communication", confidence="high",
    ) for item in items[:10]]
    return ToolResult("central_banks", "\n".join(item.claim for item in evidence), evidence,
                      [] if evidence else ["No central-bank item was available in the current feed snapshot."])


def _calendar(context: ToolContext) -> ToolResult:
    evidence = [Evidence(
        claim=(f"{event.title}; region {event.region}; importance {event.importance}; "
               f"previous {event.previous}; consensus {event.consensus}; actual {event.actual}; "
               f"surprise {surprise_text(event)}; observed reaction {event.market_reaction}"),
        source=event.institution, url=event.url, observation_date=f"{event.date} {event.time}",
        evidence_type="official scheduled event", confidence="high",
    ) for event in context.events[:12]]
    return ToolResult("macro_calendar", "\n".join(item.claim for item in evidence), evidence)


def _web(context: ToolContext) -> ToolResult:
    return search_official_web(context.query)


def _move_explainer(context: ToolContext) -> ToolResult:
    summary = movement_analysis(context.points, context.news, context.events, context.profile)
    evidence = _snapshot(context).evidence[:8] + _news(context).evidence[:6] + _calendar(context).evidence[:4]
    return ToolResult("move_explainer", summary, evidence, ["Candidate drivers are correlations, not proven causes."])


def _sales_workflow(context: ToolContext) -> ToolResult:
    moves = material_moves(context.points, context.profile, 4)
    priority = "\n".join(
        f"- {point.label}: {format_value(point)} ({format_change(point)}), observed {point.date}."
        for point in moves
    ) or "- No verified priority move is available."
    next_event = context.events[0] if context.events else None
    catalyst = (
        f"{next_event.date} {next_event.time}: {next_event.title}; previous {next_event.previous}; "
        f"consensus {next_event.consensus}; actual {next_event.actual}."
        if next_event else "No verified upcoming event is available."
    )
    segments = {
        "Rates Sales": "real-money duration accounts, bank treasuries, hedge funds and liability-driven investors",
        "FX Sales": "corporate hedgers, macro funds, real-money allocators and options users",
        "Market Risk": "desk risk managers, portfolio managers and books with convexity or liquidity exposure",
        "Cross-Asset": "macro funds, multi-asset investors, asset allocators and corporate treasury clients",
    }.get(context.profile, "institutional clients")
    question = {
        "Rates Sales": "Is the client expressing a view on terminal policy, curve shape, duration or volatility?",
        "FX Sales": "Is the client solving for spot direction, hedge timing, carry or optionality?",
        "Market Risk": "Which shock, basis move or volatility regime would create the largest loss or liquidity need?",
        "Cross-Asset": "Which cross-market confirmation would change the client's allocation or hedge decision?",
    }.get(context.profile, "Which market outcome matters most to the client's decision?")
    summary = (
        f"DESK: {context.profile}\nPRIORITY MOVES:\n{priority}\n"
        f"NEXT VERIFIED CATALYST: {catalyst}\n"
        f"RELEVANT CLIENT SEGMENTS: {segments}.\n"
        f"DISCOVERY QUESTION: {question}\n"
        "SCENARIO DISCIPLINE: distinguish above-consensus/hawkish, in-line/base and below-consensus/dovish outcomes; "
        "state the observable trigger, assets to watch and invalidation signal without inventing a forecast."
    )
    evidence = _snapshot(context).evidence[:8] + _calendar(context).evidence[:3]
    return ToolResult("sales_workflow", summary, evidence)


TOOL_REGISTRY: dict[str, AgentTool] = {
    "market_snapshot": AgentTool("market_snapshot", "Current rates, macro, FX, equities, credit and commodities snapshot.", _snapshot),
    "official_news": AgentTool("official_news", "Dated official economic and policy headlines.", _news),
    "central_banks": AgentTool("central_banks", "Federal Reserve, ECB, Bank of England and Bank of Japan communications.", _central_banks),
    "macro_calendar": AgentTool("macro_calendar", "Upcoming official macroeconomic releases and policy events.", _calendar),
    "web_search": AgentTool("web_search", "Bounded search restricted to allowlisted official domains.", _web),
    "move_explainer": AgentTool("move_explainer", "Material moves, matching official news, confidence and next catalysts.", _move_explainer),
    "sales_workflow": AgentTool("sales_workflow", "Desk priorities, relevant client segments, discovery questions and scenario discipline.", _sales_workflow),
}


def classify_and_plan(query: str, max_steps: int) -> tuple[str, list[str], list[str]]:
    lower = query.casefold()
    tools = ["market_snapshot"]
    classification = "cross-asset market question"
    if any(word in lower for word in ("calendar", "release", "event", "today", "week", "payroll", "cpi", "pce")):
        tools.append("macro_calendar")
        classification = "macro calendar and market question"
    if any(word in lower for word in ("fed", "ecb", "boe", "boj", "central bank", "policy", "speech")):
        tools.append("central_banks")
        classification = "central-bank research question"
    if any(word in lower for word in ("news", "headline", "latest", "development", "morning", "brief")):
        tools.append("official_news")
    # Web search is the only tool that may add a live network call. Keep it for
    # explicit causal or announcement requests; current headlines already come
    # from the dashboard snapshot.
    if any(word in lower for word in ("why", "drove", "cause", "speech", "announcement")):
        tools.append("web_search")
    if any(word in lower for word in ("why", "drove", "cause", "move", "explain")):
        tools.append("move_explainer")
    if any(word in lower for word in (
        "client", "call", "sales", "talking", "scenario", "prepare", "morning", "brief", "changed", "desk"
    )):
        tools.append("sales_workflow")
        classification = f"{classification} with Sales workflow"
    tools = list(dict.fromkeys(tools))[:max_steps]
    plan = [f"Collect {TOOL_REGISTRY[name].description}" for name in tools]
    plan.append("Build and audit the evidence register before synthesis.")
    return classification, plan, tools


def execute_tools(context: ToolContext, names: list[str], session: dict[str, object], max_per_tool: int) -> list[ToolResult]:
    counts = dict(session.get("tool_counts", {}))
    results: list[ToolResult] = []
    for name in names:
        if counts.get(name, 0) >= max_per_tool:
            results.append(ToolResult(name, "Tool call limit reached.", warnings=[f"{name}: per-session limit reached."]))
            continue
        tool = TOOL_REGISTRY[name]
        results.append(tool.handler(context))
        counts[name] = counts.get(name, 0) + 1
    session["tool_counts"] = counts
    return results


def registry_markdown() -> str:
    lines = ["### Available research tools"]
    lines.extend(f"- **{tool.name}**: {tool.description}" for tool in TOOL_REGISTRY.values())
    return "\n".join(lines)
