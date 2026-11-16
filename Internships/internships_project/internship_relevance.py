"""Deterministic, account-local ranking of internships against explicit profile fields."""
from __future__ import annotations

import re
import unicodedata
from datetime import date


def _words(value: object) -> set[str]:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return set(re.findall(r"[a-z0-9]+", text)) - {"stage", "internship", "intern", "de", "des", "du", "en", "the", "and"}


def rank_offers(jobs: list, profile: dict | None, today: date) -> list[tuple[object, dict]]:
    """Use stated preferences only; a source deadline is shown only if parseable and current."""
    profile = profile or {}
    roles = profile.get("target_roles", [])
    locations = profile.get("locations", [])
    roles = [item for item in roles if isinstance(item, str)][:20] if isinstance(roles, list) else []
    locations = [item for item in locations if isinstance(item, str)][:20] if isinstance(locations, list) else []
    start = str(profile.get("start_month") or "")
    end = str(profile.get("end_month") or "")
    ranked = []
    for job in jobs:
        reasons = []
        title_words = _words(job.title) | _words(job.family)
        if any(_words(role) and _words(role) <= title_words for role in roles):
            reasons.append("Métier ciblé")
        if any(_words(place) and _words(place) <= _words(job.location) for place in locations):
            reasons.append("Lieu souhaité")
        from .internships import start_month
        month = start_month(job.start_period)
        if month and (start or end) and (not start or month >= start) and (not end or month <= end):
            reasons.append("Période de début souhaitée")
        try:
            deadline = date.fromisoformat(str(job.deadline)).isoformat()
            if deadline < today.isoformat():
                deadline = ""
        except ValueError:
            deadline = ""
        detail = {"relevance": "forte" if len(reasons) >= 2 else "à examiner",
                  "match_reasons": reasons, "deadline": deadline}
        ranked.append((job, detail))
    return sorted(ranked, key=lambda pair: (-len(pair[1]["match_reasons"]), -pair[0].score,
                                            pair[0].title.casefold()))
