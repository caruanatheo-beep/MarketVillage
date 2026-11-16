"""Explicit, bounded checks for MarketDesk City service connections."""
from __future__ import annotations

from datetime import datetime, timezone
import os


def _row(name: str, status: str, source: str, detail: str, last_sync: str = "",
         access: str = "Read", separate_process: bool = False) -> dict:
    return {"name": name, "status": status, "source": source, "detail": detail[:280],
            "last_sync": last_sync, "access": access, "separate_process": separate_process}


def check_integrations(username: str) -> dict:
    """Run once on user request; never starts collection or sends mail."""
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    checks: list[dict] = []
    try:
        from .city_offers import load_catalogue
        catalogue = load_catalogue()
        metadata = catalogue.metadata()
        checks.append(_row("Internship Tracker", "Connected" if catalogue.source == 'public' and not metadata['catalog_stale'] and not catalogue.warning else "Unavailable",
                           "Internships en ligne" if catalogue.source == 'public' else "Cache local de secours",
                           f"{len(catalogue.jobs)} offres ; {len(catalogue.errors)} alertes de sources. " + metadata['catalog_warning'],
                           catalogue.updated.isoformat(), "Read", False))
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
    from .city_chat import codex_chat_available
    available = codex_chat_available()
    checks.append(_row("Desk Manager · Codex", "Connected" if available else "Unavailable", "Abonnement ChatGPT",
                       "Connexion locale reconnue ; utilise le chat pour vérifier une réponse réelle." if available else
                       "Connexion Codex locale indisponible. Relance City avec les droits de ton compte Windows.",
                       access="External request on chat"))
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        checks.append(_row("Iris · rédaction API", "Unavailable", "OpenAI API existante",
                           "Rédaction API non configurée ; cela ne bloque pas le chat Codex.", access="Draft only", separate_process=False))
    else:
        checks.append(_row("Iris · rédaction API", "Unavailable", "OpenAI API existante",
                           "Configuration présente ; aucun appel API effectué. Une rédaction réelle reste à vérifier.",
                           access="Draft only"))
    return {"checked_at": checked_at, "integrations": checks}
