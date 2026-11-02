"""Explicit, bounded checks for MarketDesk City service connections."""
from __future__ import annotations

from datetime import datetime, timezone
import os
import time


def _row(name: str, status: str, source: str, detail: str, last_sync: str = "",
         access: str = "Read", separate_process: bool = False) -> dict:
    return {"name": name, "status": status, "source": source, "detail": detail[:280],
            "last_sync": last_sync, "access": access, "separate_process": separate_process}


def check_integrations(username: str) -> dict:
    """Run once on user request; never starts collection or sends mail."""
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    checks: list[dict] = []
    try:
        from .internships import load_opportunities
        jobs, errors, updated = load_opportunities(refresh=False)
        checks.append(_row("Internship Tracker", "Connected", "Shared offers cache / connector state",
                           f"{len(jobs)} cached offers; {len(errors)} current source errors. Check performed without a refresh.",
                           updated.isoformat(), "Read", False))
    except Exception as exc:
        checks.append(_row("Internship Tracker", "Error", "Shared offers cache",
                           f"Cache unavailable ({type(exc).__name__})."))
    try:
        from src.data import load_snapshot
        points, status = load_snapshot()
        usable = [point for point in points if getattr(point, "value", None) is not None]
        detail = f"{len(usable)} observations loaded from the current snapshot."
        checks.append(_row("Market Data", "Connected" if usable else "Unavailable", "Market Brief data snapshot",
                           detail if usable else "The data service responded but returned no usable observations.",
                           str(status.get("updated_at", "")) if isinstance(status, dict) else "", "Read", False))
    except Exception as exc:
        checks.append(_row("Market Data", "Error", "Market Brief data service",
                           f"Data snapshot failed ({type(exc).__name__})."))
    try:
        from src.news import load_news
        news, errors = load_news()
        checks.append(_row("News Service", "Connected" if news else "Unavailable", "Configured news feeds/cache",
                           f"{len(news)} news items returned; {len(errors)} feed errors.", access="Read", separate_process=False))
    except Exception as exc:
        checks.append(_row("News Service", "Error", "Configured news feeds/cache",
                           f"News check failed ({type(exc).__name__})."))
    try:
        from .state_store import load_user_data
        contacts = load_user_data(username, "mail_contacts")
        checks.append(_row("Networking Database", "Connected", "Account-scoped Mail contacts in SQLite",
                           f"Database accessible; {len(contacts)} contacts saved for this account.", access="Read", separate_process=False))
    except Exception as exc:
        checks.append(_row("Networking Database", "Error", "Account-scoped SQLite contacts",
                           f"Contact database failed ({type(exc).__name__})."))
    try:
        from .llm_usage import _connect
        with _connect() as db:
            usage_count = db.execute("SELECT COUNT(*) FROM llm_usage WHERE username=?", (username,)).fetchone()[0]
        checks.append(_row("AI Costs Ledger", "Connected", "Account-scoped LLM usage database",
                           f"Usage ledger accessible; {usage_count} recorded call(s) for this account.",
                           access="Read", separate_process=False))
    except Exception as exc:
        checks.append(_row("AI Costs Ledger", "Error", "Account-scoped LLM usage database",
                           f"Usage ledger failed ({type(exc).__name__})."))
    outreach_row = None
    try:
        from . import mail_outreach  # noqa: F401
        outreach_row = _row("Outreach Service", "Unavailable",
                           "Existing Mail draft generator and account profiles",
                           "Draft generator module is present. This diagnostic does not generate or send a draft; use AI Assistant > Mail to validate that workflow.",
                           access="Read/write draft", separate_process=False)
        checks.append(outreach_row)
    except Exception as exc:
        checks.append(_row("Outreach Service", "Error", "Existing Mail draft generator",
                           f"Draft service failed to load ({type(exc).__name__})."))
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        checks.append(_row("LLM Provider", "Unavailable", "OpenAI API",
                           "OPENAI_API_KEY is not configured on the server.", access="External request on chat", separate_process=False))
    else:
        try:
            import requests
            started = time.monotonic()
            response = requests.get("https://api.openai.com/v1/models",
                                    headers={"Authorization": f"Bearer {key}"}, timeout=(4, 8))
            latency = round((time.monotonic() - started) * 1000)
            status = "Connected" if response.ok else "Error"
            detail = f"OpenAI models endpoint returned HTTP {response.status_code} in {latency} ms; no completion was requested."
            checks.append(_row("LLM Provider", status, "OpenAI Models API", detail,
                               checked_at if response.ok else "", "External request on chat", False))
            if outreach_row and response.ok:
                outreach_row["status"] = "Connected"
                outreach_row["detail"] = "Mail draft workflow is available and the provider endpoint responded. No draft or email was created."
            response.close()
        except Exception as exc:
            checks.append(_row("LLM Provider", "Error", "OpenAI Models API",
                               f"Provider check failed ({type(exc).__name__}); no key or response body is shown.",
                               access="External request on chat", separate_process=False))
    return {"checked_at": checked_at, "integrations": checks}
