"""Opt-in SMTP digest for newly detected direct-source opportunities.

The first completed collection establishes a baseline. Subsequent collections
send one digest for unseen offers; failed deliveries remain eligible for retry.
Only public offer metadata is included, never candidate or account data.
"""

from __future__ import annotations

import logging
import os
import re
import smtplib
import ssl
import threading
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape
from urllib.parse import urlparse

_send_lock = threading.Lock()
_EMAIL_RE = re.compile(r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+\Z")


@dataclass(frozen=True)
class MailConfig:
    recipient: str
    sender: str
    host: str
    port: int
    username: str
    password: str
    security: str


def _configuration(*, require_enabled: bool = True) -> MailConfig | None:
    if require_enabled and os.getenv("INTERNSHIPS_EMAIL_ALERTS_ENABLED", "").strip().casefold() not in {
        "1", "true", "yes", "on",
    }:
        return None
    names = {
        "recipient": "INTERNSHIPS_ALERT_EMAIL_TO",
        "sender": "INTERNSHIPS_ALERT_EMAIL_FROM",
        "host": "INTERNSHIPS_SMTP_HOST",
        "username": "INTERNSHIPS_SMTP_USERNAME",
        "password": "INTERNSHIPS_SMTP_PASSWORD",
    }
    values = {key: os.getenv(variable, "").strip() for key, variable in names.items()}
    missing = [names[key] for key, value in values.items() if not value]
    if missing:
        raise ValueError("Configuration e-mail incomplète : " + ", ".join(missing))
    if not _EMAIL_RE.fullmatch(values["recipient"]) or not _EMAIL_RE.fullmatch(values["sender"]):
        raise ValueError("Les adresses d'alerte doivent être des adresses e-mail uniques et valides.")
    security = os.getenv("INTERNSHIPS_SMTP_SECURITY", "starttls").strip().casefold()
    if security not in {"starttls", "ssl"}:
        raise ValueError("INTERNSHIPS_SMTP_SECURITY doit être starttls ou ssl.")
    try:
        port = int(os.getenv("INTERNSHIPS_SMTP_PORT", "465" if security == "ssl" else "587"))
    except ValueError as exc:
        raise ValueError("INTERNSHIPS_SMTP_PORT doit être un nombre.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("INTERNSHIPS_SMTP_PORT est hors limites.")
    return MailConfig(port=port, security=security, **values)


def _offer_key(job: object) -> str:
    # Mirror the dashboard's cross-source deduplication, so the same posting
    # does not trigger another email when a second connector discovers it.
    from .internships import _canonical_company, _canonical_title, _is_paris

    location = str(getattr(job, "location", "") or "")
    location_key = "paris-area" if _is_paris(location) else location.casefold().strip()
    return "\x1f".join((
        _canonical_company(str(getattr(job, "company", "") or "")),
        _canonical_title(str(getattr(job, "title", "") or "")),
        location_key,
    ))


def _eligible_offers(jobs: list[object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for job in jobs:
        # Sitemap-only JobTeaser links are not confirmed open vacancies.
        if str(getattr(job, "source", "")).startswith("JobTeaser"):
            continue
        url = urlparse(str(getattr(job, "url", "") or ""))
        if url.scheme != "https" or not url.hostname:
            continue
        result.setdefault(_offer_key(job), job)
    return result


def _connect():
    from . import state_store

    connection = state_store._connect()
    connection.execute(
        "CREATE TABLE IF NOT EXISTS email_alert_seen ("
        "identity TEXT PRIMARY KEY, seen_at TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS email_alert_baseline ("
        "id INTEGER PRIMARY KEY CHECK(id=1), initialized_at TEXT NOT NULL)"
    )
    return connection


def _message(jobs: list[object], recipient: str, sender: str, *, preview: bool = False) -> EmailMessage:
    count = len(jobs)
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = ("Aperçu des alertes offres" if preview else
                          f"{count} nouvelle{'s' if count > 1 else ''} offre{'s' if count > 1 else ''} en finance de marché")
    lines = [
        (f"Aperçu du format avec {count} offre{'s' if count > 1 else ''} déjà en cache."
         if preview else
         f"{count} nouvelle{'s' if count > 1 else ''} offre{'s' if count > 1 else ''} détectée{'s' if count > 1 else ''} depuis la dernière alerte."),
        "",
    ]
    cards = []
    for job in jobs:
        title = str(getattr(job, "title", "") or "").strip()[:220]
        company = str(getattr(job, "company", "") or "").strip()[:120]
        location = str(getattr(job, "location", "") or "").strip()[:120]
        kind = str(getattr(job, "kind", "") or "").strip()[:60]
        family = str(getattr(job, "family", "") or "").strip()[:80]
        start_period = str(getattr(job, "start_period", "") or "").strip()[:80]
        deadline = str(getattr(job, "deadline", "") or "").strip()[:80]
        source = str(getattr(job, "source", "") or "").strip()[:100]
        url = str(getattr(job, "url", "") or "").strip()
        published = str(getattr(job, "published", "") or "").strip()
        inferred = bool(getattr(job, "published_inferred", False))
        initials = "".join(part[0] for part in company.split()[:2]).upper() or "?"
        date_text = (f"{'Détectée' if inferred else 'Publiée'} le {published}"
                     if published else "Date non indiquée")
        lines.extend((
            f"{company} — {title}",
            f"Lieu : {location or 'non indiqué'}",
        ))
        if start_period:
            lines.append(f"Début annoncé : {start_period}")
        if deadline:
            lines.append(f"Date limite : {deadline}")
        lines.extend((
            date_text,
            url,
            "",
        ))
        badge = (
            '<span style="display:inline-block;margin:0 6px 6px 0;padding:5px 9px;'
            'border:1px solid #e1d6fb;border-radius:7px;background:#f2edff;'
            'color:#6240b5;font-size:12px;font-weight:700;line-height:16px;">'
            f'{escape(kind)}</span>' if kind else ''
        )
        if family:
            badge += (
                '<span style="display:inline-block;margin:0 6px 6px 0;padding:5px 9px;'
                'border:1px solid #e0e3eb;border-radius:7px;background:#f8f9fc;'
                'color:#344159;font-size:12px;line-height:16px;">'
                f'{escape(family)}</span>'
            )
        for label in ([f"Début : {start_period}"] if start_period else []) + (
            [f"Limite : {deadline}"] if deadline else []
        ):
            badge += (
                '<span style="display:inline-block;margin:0 6px 6px 0;padding:5px 9px;'
                'border:1px solid #f0dfb8;border-radius:7px;background:#fff8e8;'
                'color:#845e16;font-size:12px;line-height:16px;">'
                f'{escape(label)}</span>'
            )
        cards.append(
            '<tr><td style="padding:0 0 12px;">'
            '<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
            'style="border:1px solid #e0e3eb;border-radius:12px;background:#ffffff;">'
            '<tr><td style="padding:20px 22px 17px;font-family:Arial,Helvetica,sans-serif;">'
            '<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
            'style="margin:0 0 14px;"><tr>'
            '<td width="43" valign="top" style="padding-right:11px;">'
            '<span style="display:block;width:38px;height:38px;border-radius:9px;'
            'background:#eee9f9;color:#6240b5;text-align:center;line-height:38px;'
            'font-size:13px;font-weight:700;">'
            f'{escape(initials)}</span></td>'
            '<td valign="middle"><p style="margin:0 0 2px;color:#17203a;font-size:15px;'
            f'font-weight:700;line-height:20px;">{escape(company or "Employeur non indiqué")}</p>'
            '<p style="margin:0;color:#647184;font-size:13px;line-height:18px;">'
            f'{escape(location or "Lieu non indiqué")}</p></td>'
            '<td align="right" valign="top" style="color:#647184;font-size:11px;'
            f'line-height:18px;white-space:nowrap;">{escape(date_text)}</td>'
            '</tr></table>'
            '<h2 style="margin:0 0 13px;color:#17203a;font-size:19px;font-weight:700;line-height:26px;">'
            f'{escape(title)}</h2>'
            f'<div style="margin:0 0 12px;line-height:28px;">{badge}</div>'
            '<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
            'style="border-top:1px solid #e8eaf0;"><tr>'
            '<td style="padding:13px 8px 0 0;color:#647184;font-size:12px;line-height:18px;">'
            f'{escape(source or "Source non indiquée")}</td>'
            '<td align="right" style="padding:13px 0 0;white-space:nowrap;">'
            f'<a href="{escape(url, quote=True)}" style="color:#6240b5;font-size:13px;'
            'font-weight:700;text-decoration:underline;">Voir l’offre ↗</a></td>'
            '</tr></table></td></tr></table></td></tr>'
        )
    lines.append("Ces offres sont sélectionnées par les filtres de finance de marché du dashboard. Vérifie l'annonce d'origine avant de postuler.")
    message.set_content("\n".join(lines))
    html_body = (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#f7f7fb;color:#17203a;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
        'style="background:#f7f7fb;"><tr><td align="center" style="padding:24px 14px;">'
        '<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
        'style="max-width:620px;"><tr><td style="padding:23px 24px 24px;'
        'border:1px solid #e1d6fb;border-radius:14px;background:#f2edff;'
        'font-family:Arial,Helvetica,sans-serif;">'
        '<p style="margin:0 0 8px;color:#6240b5;font-size:12px;font-weight:700;'
        f'letter-spacing:1px;">{"APERÇU DES ALERTES" if preview else "ALERTES OFFRES"}</p>'
        f'<h1 style="margin:0 0 8px;color:#17203a;font-size:26px;line-height:32px;">'
        f'{count} offre{"s" if count > 1 else ""} {"en exemple" if preview else "nouvelle" + ("s" if count > 1 else "")}</h1>'
        '<p style="margin:0;color:#526079;font-size:14px;line-height:21px;">'
        f'{"Offres déjà en cache · aucun suivi modifié." if preview else "En finance de marché, depuis ta dernière alerte."}</p>'
        '</td></tr><tr><td style="height:16px;"></td></tr>'
        + ''.join(cards) +
        '<tr><td style="padding:7px 3px;color:#647184;font-family:Arial,Helvetica,sans-serif;'
        'font-size:12px;line-height:19px;">Les annonces proviennent des sources indiquées. '
        'Vérifie chaque offre sur son site d’origine avant de postuler.</td></tr>'
        '</table></td></tr></table></body></html>'
    )
    message.add_alternative(html_body, subtype="html")
    return message


def _send_message(config: MailConfig, message: EmailMessage) -> None:
    context = ssl.create_default_context()
    if config.security == "ssl":
        with smtplib.SMTP_SSL(config.host, config.port, timeout=12, context=context,
                              local_hostname="localhost") as smtp:
            smtp.login(config.username, config.password)
            smtp.send_message(message, from_addr=config.sender, to_addrs=[config.recipient])
    else:
        with smtplib.SMTP(config.host, config.port, timeout=12,
                          local_hostname="localhost") as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(config.username, config.password)
            smtp.send_message(message, from_addr=config.sender, to_addrs=[config.recipient])


def notify_new_offers(jobs: list[object], *, now: datetime | None = None) -> int:
    """Send one digest after a completed refresh; return the delivered offer count."""
    try:
        config = _configuration()
        if config is None:
            return 0
        eligible = _eligible_offers(jobs)
        if not eligible:
            return 0
        timestamp = (now or datetime.now(timezone.utc)).isoformat()
        with _send_lock, closing(_connect()) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                baseline = connection.execute("SELECT 1 FROM email_alert_baseline WHERE id=1").fetchone()
                if not baseline:
                    connection.executemany(
                        "INSERT OR IGNORE INTO email_alert_seen(identity,seen_at) VALUES (?,?)",
                        ((key, timestamp) for key in eligible),
                    )
                    connection.execute(
                        "INSERT INTO email_alert_baseline(id,initialized_at) VALUES (1,?)", (timestamp,)
                    )
                    return 0
                seen = {row[0] for row in connection.execute("SELECT identity FROM email_alert_seen")}
            new = [(key, job) for key, job in eligible.items() if key not in seen]
            if not new:
                return 0
            _send_message(config, _message([job for _, job in new], config.recipient, config.sender))
            with connection:
                connection.executemany(
                    "INSERT OR IGNORE INTO email_alert_seen(identity,seen_at) VALUES (?,?)",
                    ((key, timestamp) for key, _ in new),
                )
            return len(new)
    except Exception as exc:
        # A mail outage must not break or discard the completed offer refresh.
        logging.warning("Internship email alert was not sent (%s).", type(exc).__name__)
        return 0


def send_test_email() -> None:
    """Explicit smoke test; never called by the refresh scheduler."""
    config = _configuration(require_enabled=False)
    assert config is not None
    message = EmailMessage()
    message["From"] = config.sender
    message["To"] = config.recipient
    message["Subject"] = "Test des alertes offres"
    message.set_content("L'envoi SMTP fonctionne. Les alertes d'offres commenceront après la première collecte de référence.")
    _send_message(config, message)


def send_preview_email() -> int:
    """Email up to three cached offers without collecting or changing alert history."""
    from .internships import _read_cache

    config = _configuration(require_enabled=False)
    assert config is not None
    snapshot = _read_cache()
    jobs = list(_eligible_offers(snapshot[1]).values())[:3] if snapshot else []
    if not jobs:
        raise ValueError("Aucune offre en cache pour l'aperçu. Actualise d'abord les offres dans l'application.")
    _send_message(config, _message(jobs, config.recipient, config.sender, preview=True))
    return len(jobs)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    parser = argparse.ArgumentParser(description="Tester les alertes offres")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--test", action="store_true",
                        help="envoyer un courriel de test SMTP")
    action.add_argument("--preview", action="store_true",
                        help="envoyer un aperçu HTML avec trois offres en cache au maximum")
    args = parser.parse_args()
    if args.preview:
        count = send_preview_email()
        print(f"Aperçu envoyé avec {count} offre{'s' if count > 1 else ''} en cache.")
    else:
        send_test_email()
        print("Courriel de test envoyé.")
