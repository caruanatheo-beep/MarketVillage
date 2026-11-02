"""Adapters from City agents to existing MarketDesk services.

Each adapter is an explicit, bounded operation. None of these functions sends
mail, applies to jobs, writes code, or performs background LLM polling.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import math
import re
import unicodedata
import threading

from .marketdesk_city import CityError, refresh_jobs_workflow

_DRAFT_LOCKS = [threading.Lock() for _ in range(32)]


def _fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def search_text(value: object) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(value or "").casefold())
                   if not unicodedata.combining(c))


def redact_diagnostic(value: object) -> str:
    text = str(value)
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "[SECRET]", text)
    text = re.sub(r"(?i)\b(Bearer|Basic)\s+[^\s,;\"']+", r"\1 [SECRET]", text)
    text = re.sub(r'''(?ix)([\w-]*(?:password|passwd|api[_-]?key|token|secret|cookie)[\w-]*["']?\s*[:=]\s*)("[^"]*"|'[^']*'|[^\s,;&]+)''', r"\1[SECRET]", text)
    return re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[SECRET]@", text)


def _observation_age(value: object) -> dict:
    try:
        observed = datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        age = (datetime.now(timezone.utc).date() - observed).days
    except (ValueError, TypeError):
        return {"age_days": None, "date_status": "unknown"}
    return {"age_days": age, "date_status": "future" if age < 0 else "dated",
            "note": "Âge calendaire de l'observation, pas une cotation temps réel."}


def market_news() -> dict:
    from src.news import load_news
    items, errors = load_news()
    articles = []
    for item in items:
        raw_date = str(item.published or "")
        try:
            stamp = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            stamp = stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp
            timestamp = stamp.timestamp()
        except ValueError:
            timestamp = float("-inf")
        articles.append((timestamp, {"title": item.title, "publisher": str(getattr(item, "source", "")),
                                    "published": raw_date, "url": item.url,
                                    "date_known": timestamp != float("-inf")}))
    articles.sort(key=lambda row: (-row[0], row[1]["url"]))
    seen, unique = set(), []
    for _, article in articles:
        key = article["url"].split("#")[0].rstrip("/") or search_text(article["title"])
        if key not in seen:
            seen.add(key)
            unique.append(article)
    return {"articles": unique[:12], "total_unique": len(unique),
            "errors": [redact_diagnostic(e) for e in errors[:3]], "order": "publication décroissante, dates inconnues en dernier"}


def run_agent(agent_id: str, username: str, parameters: dict | None = None) -> dict:
    parameters = parameters if isinstance(parameters, dict) else {}
    if agent_id == "internship_scout":
        if parameters.get("operation", "refresh_internships") != "refresh_internships":
            raise CityError("Hugo peut uniquement actualiser les stages via Internships.")
        detected = parameters.get('report_mode') == 'detected_today'
        return {**refresh_jobs_workflow(published_today=not detected, detected_today=detected), "source": "Service Python Internships, sans interface Gradio"}
    if agent_id == "networker" and parameters.get("operation") == "refresh_internships":
        return {**refresh_jobs_workflow(), "title": "Lina · collecte Internships", "source": "Service Python Internships, sans interface Gradio"}
    if agent_id == 'networker' and parameters.get('operation') == 'enrich_schools':
        from .network_discovery import enrich_schools
        return enrich_schools(username)
    from .city_specialists import SPECIALISTS, run_specialist
    if agent_id in SPECIALISTS:
        return run_specialist(agent_id, username, parameters)
    if agent_id == "market_analyst":
        return market_brief()
    if agent_id == "networker":
        if parameters.get("discover_public"):
            from .network_discovery import discover_contacts
            return discover_contacts(username)
        return network_contacts(username, str(parameters.get("query") or ""))
    if agent_id == "outreach_agent":
        return prepare_outreach(username, str(parameters.get("contact_id") or ""),
                                str(parameters.get("profile_id") or ""),
                                str(parameters.get("language") or "Français"))
    raise CityError("Aucun workflow n'est connecté à cet agent.")


def market_brief() -> dict:
    """Read the existing Market Brief snapshot, news and official calendar."""
    try:
        from src.data import load_snapshot
        from src.news import load_news
        from src.calendar import load_calendar
        from src.analytics import briefing_markdown
        from src.models import NewsItem

        points, status = load_snapshot()
        news, news_errors = load_news()
        events, calendar_error = load_calendar(days_ahead=14, limit=20)
        verified_news = [item for item in news if isinstance(item, NewsItem)]
        brief = briefing_markdown(points, events, verified_news)
        if not brief.strip():
            raise CityError("Le Market Brief n'a pas renvoyé de données utilisables.")
        return {"title": "Brief de marché", "as_of": datetime.now(timezone.utc).isoformat(),
                "market_points": len([p for p in points if getattr(p, "value", None) is not None]),
                "market_data": _market_readings(points),
                "headlines": len(verified_news), "calendar_events": len(events),
                "data_status": status, "warnings": [*news_errors[:3], *([calendar_error] if calendar_error else [])],
                "text": brief[:18000], "source": "Market Brief · données et publications existantes"}
    except CityError:
        raise
    except Exception as exc:
        raise CityError(f"Market Brief indisponible ({type(exc).__name__}).") from exc


def _market_readings(points: list) -> list[dict]:
    selected = []
    wanted = {"DGS2", "DGS10", "DEXUSEU", "DEXUSUK", "SP500", "VIXCLS", "BAMLH0A0HYM2", "DCOILWTICO"}
    for point in points:
        if getattr(point, "series_id", "") in wanted and getattr(point, "value", None) is not None:
            selected.append({"series_id": point.series_id, "label": point.label,
                             "value": float(point.value), "unit": point.unit,
                             "previous": float(point.previous) if point.previous is not None else None,
                             "change": float(point.change) if point.change is not None else None,
                             "observed_at": str(point.date or ""), "source": point.source_name,
                             "source_url": point.source_url, **_observation_age(point.date)})
    return selected[:8]


@lru_cache(maxsize=1)
def _market_snapshot_cached(bucket: int) -> dict:
    from src.data import load_snapshot
    points, status = load_snapshot()
    selected = _market_readings(points)
    return {"points": selected, "status": status,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "note": "Observations datées du fournisseur ; elles peuvent être différées."}


def market_snapshot() -> dict:
    return _market_snapshot_cached(int(datetime.now(timezone.utc).timestamp()) // 60)


def internship_highlight() -> dict:
    """Read the current Internships cache without starting a new source collection."""
    from . import internships

    jobs, errors, updated = internships.load_opportunities(refresh=False)
    ranked = sorted(jobs, key=internships._opportunity_sort_key)
    job = ranked[0] if ranked else None
    offer = ({
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "kind": job.kind,
        "start_period": job.start_period,
        "published": job.published,
        "published_inferred": job.published_inferred,
        "source": job.source,
        "selection_source": "internships_cache",
        "selection_reason": "Offre en tête du classement actuel d’Internships.",
    } if job else None)
    return {
        "featured_offer": offer,
        "updated_at": updated.isoformat(),
        "total_count": len(jobs),
        "source_errors": len(errors),
    }


def market_exercise() -> dict:
    """Build a small, deterministic exercise only from currently observed yields."""
    try:
        from src.data import load_snapshot
        points, _ = load_snapshot()
        lookup = {str(getattr(p, "series_id", "")).upper(): p for p in points}
        short = lookup.get("DGS2")
        long = lookup.get("DGS10")
        if not short or not long or short.value is None or long.value is None:
            raise CityError("Les rendements nécessaires ne sont pas disponibles dans le snapshot actuel.")
        if not short.date or not long.date or str(short.date)[:10] != str(long.date)[:10]:
            raise CityError("Exercice suspendu : les rendements 2 ans et 10 ans doivent avoir la même date d'observation connue.")
        if not all(math.isfinite(float(p.value)) for p in (short, long)):
            raise CityError("Les rendements disponibles ne sont pas numériques et finis.")
        spread = float(long.value) - float(short.value)
        return {"title": "Exercice : pente de la courbe", "source": "Market Brief · observations disponibles",
                "observed_at": str(long.date or ""),
                "question": f"Le rendement 10 ans est {float(long.value):.3f}% et le 2 ans {float(short.value):.3f}%. "
                            "Calcule l'écart 10 ans – 2 ans en points de base et indique si la courbe est pentue ou inversée.",
                "answer": f"Écart observé : {spread * 100:.1f} points de base. "
                          + ("La courbe est pentue." if spread > 0 else "La courbe est inversée." if spread < 0 else "Les rendements sont égaux."),
                "note": "Calcul déterministe sur les dernières observations disponibles ; ce n'est pas un conseil d'investissement."}
    except CityError:
        raise
    except Exception as exc:
        raise CityError(f"Exercice indisponible ({type(exc).__name__}).") from exc


def network_contacts(username: str, query: str = "", page: int = 1) -> dict:
    """Review contacts already imported in the user's Networking workspace."""
    from .state_store import load_user_data
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        raise CityError("La page doit être un entier positif.")
    contacts = load_user_data(username, "mail_contacts")
    if not contacts:
        return {"title": "Réseau professionnel", "contacts": [], "count": 0,
                "total_matches": 0, "page": page, "page_size": 12, "has_more": False,
                "text": "Aucun contact enregistré. Consulte la collecte quotidienne de Lina dans City → Contacts, ou importe tes contacts dans Mail.",
                "source": "Network · dossier personnel", "warning": "Aucune recherche externe n'est lancée par cette consultation du dossier."}
    terms = search_text(query).split()
    scored = []
    for key, item in contacts.items():
        fields = {field: search_text(item.get(field)) for field in
                  ("name", "role", "company", "location", "desk", "experiences")}
        haystack = " ".join(fields.values())
        score = sum(1 for term in terms if term in haystack)
        if not terms or score:
            scored.append((score, key, item, [field for field, text in fields.items()
                                             if any(term in text for term in terms)]))
    scored.sort(key=lambda row: (-row[0], str(row[2].get("company") or "").casefold(),
                                 str(row[2].get("name") or "").casefold(), row[1]))
    records = [{"id": key, "name": item.get("name", "Identité à vérifier"), "role": item.get("role", ""),
                "company": item.get("company", ""), "location": item.get("location", ""),
                "linkedin_url": item.get("linkedin_url", ""), "verification": item.get("verification_status", "À vérifier"),
                "conversation": item.get("conversation", "Non contacté"), "relevance": item.get("relevance", "À examiner"),
                "matched_fields": matched, "match_basis": "Mots-clés dans les données importées, non vérifiées automatiquement."}
               for _, key, item, matched in scored[(page - 1) * 12:page * 12]]
    return {"title": "Contacts pertinents déjà enregistrés", "contacts": records, "count": len(records),
            "total_matches": len(scored), "page": page, "page_size": 12, "has_more": page * 12 < len(scored),
            "text": f"{len(scored)} contact(s) correspondent aux mots-clés fournis parmi {len(contacts)} contacts sauvegardés ; {len(records)} sur cette page.",
            "source": "Network · dossier personnel", "warning": "Aucune recherche externe n'est lancée par cette consultation. Les contacts publics collectés par Lina restent à vérifier."}


def prepare_outreach(username: str, contact_id: str, profile_id: str, language: str) -> dict:
    # Serialize duplicate requests per account without blocking edits in Mail during the LLM call.
    lock = _DRAFT_LOCKS[int(_fingerprint(username)[:8], 16) % len(_DRAFT_LOCKS)]
    if not lock.acquire(timeout=20):
        raise CityError("Un brouillon est déjà en préparation. Consulte son résultat avant de réessayer.")
    try:
        return _prepare_outreach(username, contact_id, profile_id, language)
    finally:
        lock.release()


def _prepare_outreach(username: str, contact_id: str, profile_id: str, language: str) -> dict:
    """Generate and save a draft using existing contact/profile/LLM code; never send."""
    from .state_store import load_user_data, save_user_data
    from .candidate_profiles import clean_catalog
    from . import mail_outreach
    from .career_agent import CareerAgentError

    contacts = load_user_data(username, "mail_contacts")
    profiles = clean_catalog(load_user_data(username, "profiles"))
    contact = contacts.get(contact_id)
    profile = profiles.get(profile_id)
    if not contact:
        raise CityError("Sélectionne un contact enregistré dans AI Assistant → Mail.")
    if not profile:
        raise CityError("Crée d'abord ton profil dans Mon profil.")
    if language not in {"Français", "English"}:
        raise CityError("Choisis Français ou English.")
    if (contact.get("sent_at") or contact.get("attempted_at")
            or contact.get("conversation") in {"Réponse", "Refus", "Erreur définitive", "En attente"}
            or contact.get("delivery") in {"en attente", "résultat incertain", "envoyé"}):
        raise CityError("Ce contact a déjà une conversation ou un envoi engagé. Consulte le suivi Mail avant une nouvelle prise de contact.")
    context_hash = _fingerprint({"profile": profile, "language": language, "recipient": {
        key: contact.get(key) for key in ("name", "role", "company", "location", "linkedin_url", "experiences", "education")}})
    saved = contact.get("_city_draft", {})
    draft_fields = ("subject", "body", "followup_body")
    reused = bool(contact.get("body")) and saved.get("context") == context_hash and saved.get("content") == _fingerprint([contact.get(k, "") for k in draft_fields])
    if any(contact.get(k) for k in draft_fields) and not reused:
        raise CityError("Un brouillon existe déjà ou a été modifié. Relis-le dans Mail : Iris ne l'écrasera pas automatiquement.")
    try:
        if reused:
            subject, body, followup = [contact.get(k, "") for k in draft_fields]
        else:
            subject, body, followup = mail_outreach.draft_mail(contact, profile, language, cv_attached=False)
    except Exception as exc:
        raise CityError(str(exc)[:300] if isinstance(exc, (ValueError, CareerAgentError)) else
                        f"La génération du brouillon a échoué ({type(exc).__name__}).") from exc
    if not reused:
        with mail_outreach._LOCK:
            current = load_user_data(username, "mail_contacts")
            current_profile = clean_catalog(load_user_data(username, "profiles")).get(profile_id)
            if current.get(contact_id) != contact or current_profile != profile:
                raise CityError("Le contact ou ton profil a changé pendant la rédaction. Aucun brouillon n'a été écrasé ; relance après vérification.")
            contact = mail_outreach.update_contact(username, contact_id, {
                "subject": subject, "body": body, "followup_body": followup,
            })
            current = load_user_data(username, "mail_contacts")
            current[contact_id]["_city_draft"] = {"context": context_hash,
                "content": _fingerprint([current[contact_id].get(k, "") for k in draft_fields])}
            save_user_data(username, "mail_contacts", current)
            subject, body, followup = [current[contact_id].get(k, "") for k in draft_fields]
    return {"title": "Brouillon prêt à relire", "contact": {"name": contact.get("name", ""),
            "company": contact.get("company", ""), "email": contact.get("email", "")},
            "subject": subject, "body": body, "followup": followup,
            "text": "Brouillon enregistré dans AI Assistant → Mail. Aucun message n'a été envoyé.",
            "source": "AI Assistant · Mail", "approval_required": True, "reused": reused}


def technical_report() -> dict:
    """Read-only diagnostic of existing collection/connectivity state."""
    from .internships import source_checks, opportunities_loading, load_opportunities
    try:
        jobs, errors, updated = load_opportunities(refresh=False)
        checks = source_checks()
        failed = [{"source": name, "status": item.get("status"), "error": redact_diagnostic(item.get("error", "")),
                   "duration_ms": item.get("duration_ms", 0)}
                  for name, item in checks.items() if item.get("status") in {"error", "stale"}]
        failed.sort(key=lambda row: -int(row["duration_ms"] or 0))
        slowest = sorted(({"source": name, "status": item.get("status", "unknown"),
                           "duration_ms": item.get("duration_ms", 0)} for name, item in checks.items()),
                         key=lambda item: -float(item["duration_ms"] or 0))[:8]
        counts = {}
        for item in checks.values():
            status = str(item.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
        return {"title": "Diagnostic en lecture seule", "total_offers": len(jobs),
                "updated_at": updated.isoformat(), "refresh_running": opportunities_loading(),
                "source_count": len(checks), "errors": failed[:12],
                "collector_errors": [redact_diagnostic(error) for error in errors[:12]],
                "slowest_sources": slowest, "status_counts": counts,
                "text": f"{len(jobs)} offres en cache · {sum(x['status'] == 'error' for x in failed)} sources en erreur · "
                        f"{sum(x['status'] == 'stale' for x in failed)} sources avec données périmées.",
                "source": "Internship Tracker · cache et état des connecteurs",
                "note": "Aucune commande système, modification de fichier ou relance de collecte n'a été exécutée."}
    except Exception as exc:
        raise CityError(f"Diagnostic indisponible ({type(exc).__name__}).") from exc
