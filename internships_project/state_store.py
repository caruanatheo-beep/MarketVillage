"""Local, single-user persistence for internship applications and offer feedback."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .internships import import_tracking


STATE_PATH = Path(__file__).resolve().parent / "data" / "user_state.json"
BACKUP_PATH = STATE_PATH.with_name("user_state.backup.json")
_state_lock = threading.RLock()
_VERDICTS = {"pertinent", "hors_cible"}
USER_DB_PATH = Path(os.getenv("INTERNSHIPS_USER_DB", str(STATE_PATH.with_name("accounts.sqlite3"))))


def local_state_enabled() -> bool:
    """A shared cloud process must not expose one person's applications to others."""
    return not (os.getenv("INTERNSHIPS_USERS_JSON") or any(
        os.getenv(name) for name in ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "SPACE_ID")))


def shared_mode() -> bool:
    return bool(os.getenv("INTERNSHIPS_USERS_JSON"))


def _connect() -> sqlite3.Connection:
    USER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(USER_DB_PATH, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE IF NOT EXISTS user_data ("
                       "username TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, "
                       "PRIMARY KEY (username, kind))")
    return connection


def load_user_data(username: str, kind: str) -> dict:
    if not username or kind not in {"tracking", "feedback", "profiles", "drafts", "ai_cache", "mail_contacts", "mail_templates"}:
        raise ValueError("Compte ou type de données invalide")
    with _connect() as connection:
        row = connection.execute("SELECT payload FROM user_data WHERE username=? AND kind=?",
                                 (username, kind)).fetchone()
    if not row:
        return {}
    try:
        value = json.loads(row[0])
    except (ValueError, TypeError):
        return {}
    if kind == "tracking":
        return _clean_tracking(value)
    if kind == "feedback":
        return _clean_feedback(value)
    return value if isinstance(value, dict) else {}


def save_user_data(username: str, kind: str, value: dict) -> None:
    if not username or kind not in {"tracking", "feedback", "profiles", "drafts", "ai_cache", "mail_contacts", "mail_templates"}:
        raise ValueError("Compte ou type de données invalide")
    if kind == "tracking":
        value = _clean_tracking(value)
    elif kind == "feedback":
        value = _clean_feedback(value)
    if not isinstance(value, dict):
        raise ValueError("Format de données invalide")
    with _connect() as connection:
        connection.execute("INSERT INTO user_data(username, kind, payload) VALUES (?, ?, ?) "
                           "ON CONFLICT(username, kind) DO UPDATE SET payload=excluded.payload",
                           (username, kind, json.dumps(value, ensure_ascii=False)))


def _clean_feedback(value: object) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, dict[str, str]] = {}
    for url, entry in list(value.items())[-1000:]:
        if not isinstance(url, str) or len(url) > 2000 or not isinstance(entry, dict):
            continue
        parsed = urlparse(url)
        verdict = entry.get("verdict")
        if parsed.scheme != "https" or not parsed.hostname or verdict not in _VERDICTS:
            continue
        cleaned[url] = {
            "verdict": str(verdict),
            "title": str(entry.get("title") or "")[:180],
            "company": str(entry.get("company") or "")[:100],
            "updated": str(entry.get("updated") or "")[:32],
        }
    return cleaned


def _clean_tracking(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    cleaned, _ = import_tracking(json.dumps(value, ensure_ascii=False), {})
    return cleaned


def _read_unlocked() -> tuple[dict, dict, bool]:
    for path in (STATE_PATH, BACKUP_PATH):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("version") == 1:
                return _clean_tracking(payload.get("tracking")), _clean_feedback(payload.get("feedback")), True
        except (OSError, ValueError, AttributeError, TypeError):
            continue
    return {}, {}, False


def _write_unlocked(tracking: dict, feedback: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    payload = {
        "version": 1,
        "updated": datetime.now(timezone.utc).isoformat(),
        "tracking": _clean_tracking(tracking),
        "feedback": _clean_feedback(feedback),
    }
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if STATE_PATH.exists():
        shutil.copyfile(STATE_PATH, BACKUP_PATH)
    temporary.replace(STATE_PATH)


def hydrate_local_state(browser_tracking: object, browser_feedback: object) -> tuple[dict, dict]:
    """Migrate browser records once; disk wins when another browser has an older copy."""
    tracking = _clean_tracking(browser_tracking)
    feedback = _clean_feedback(browser_feedback)
    if not local_state_enabled():
        return tracking, feedback
    with _state_lock:
        disk_tracking, disk_feedback, found = _read_unlocked()
        if found:
            return disk_tracking, disk_feedback
        if tracking or feedback:
            _write_unlocked(tracking, feedback)
        return tracking, feedback


def persist_tracking(tracking: dict) -> bool:
    if not local_state_enabled():
        return False
    with _state_lock:
        _, feedback, _ = _read_unlocked()
        _write_unlocked(tracking, feedback)
    return True


def persist_feedback(feedback: dict) -> bool:
    if not local_state_enabled():
        return False
    with _state_lock:
        tracking, _, _ = _read_unlocked()
        _write_unlocked(tracking, feedback)
    return True
