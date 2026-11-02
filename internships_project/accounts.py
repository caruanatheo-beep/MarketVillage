"""Self-service accounts for the authenticated internships application."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from . import state_store


USERNAME_RE = re.compile(r"[a-z][a-z0-9_.-]{2,31}\Z")
HASH_ITERATIONS = 600_000


def _connect() -> sqlite3.Connection:
    connection = state_store._connect()
    connection.execute(
        "CREATE TABLE IF NOT EXISTS registered_accounts ("
        "username TEXT PRIMARY KEY COLLATE NOCASE, password_hash TEXT NOT NULL, "
        "created_at TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS blocked_usernames ("
        "username TEXT PRIMARY KEY COLLATE NOCASE, blocked_at TEXT NOT NULL)"
    )
    return connection


def admin_username(configured: list[tuple[str, str]]) -> str:
    explicit = os.getenv("INTERNSHIPS_ADMIN_USER", "").strip()
    if explicit:
        if not any(name == explicit for name, _ in configured):
            raise ValueError("INTERNSHIPS_ADMIN_USER doit être un compte défini dans INTERNSHIPS_USERS_JSON")
        return explicit
    return configured[0][0] if configured else ""


def create_account(username: str, password: str, configured: list[tuple[str, str]]) -> None:
    if not isinstance(username, str) or not USERNAME_RE.fullmatch(username):
        raise ValueError("Identifiant invalide : 3 à 32 caractères minuscules, chiffres, point, tiret ou _.")
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError("Choisis un mot de passe de 12 à 128 caractères.")
    if any(name.casefold() == username.casefold() for name, _ in configured):
        raise ValueError("Cet identifiant est déjà utilisé.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, HASH_ITERATIONS)
    encoded = f"pbkdf2_sha256${HASH_ITERATIONS}${salt.hex()}${digest.hex()}"
    with closing(_connect()) as connection:
        with connection:
            try:
                blocked = connection.execute(
                    "SELECT 1 FROM blocked_usernames WHERE username=?", (username,)
                ).fetchone()
                if blocked:
                    raise ValueError("Cet identifiant n’est pas disponible.")
                connection.execute(
                    "INSERT INTO registered_accounts(username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, encoded, datetime.now(timezone.utc).isoformat()),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("Cet identifiant est déjà utilisé.") from exc


def authenticate(username: str, password: str, configured: list[tuple[str, str]]) -> bool:
    if not isinstance(username, str) or not isinstance(password, str):
        return False
    for name, secret in configured:
        if hmac.compare_digest(name, username):
            return hmac.compare_digest(secret, password)
    if not USERNAME_RE.fullmatch(username):
        return False
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT username, password_hash FROM registered_accounts WHERE username=?", (username,)
        ).fetchone()
    if not row or row[0] != username:
        return False
    try:
        algorithm, rounds, salt, digest = row[1].split("$")
        if algorithm != "pbkdf2_sha256" or int(rounds) != HASH_ITERATIONS:
            return False
        expected = bytes.fromhex(digest)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(rounds))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(expected, actual)


def list_accounts(configured: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    """Return public account metadata, never password hashes or private records."""
    with closing(_connect()) as connection:
        registered = connection.execute(
            "SELECT username, created_at FROM registered_accounts ORDER BY created_at DESC"
        ).fetchall()
    return ([(name, "Compte initial", "") for name, _ in configured]
            + [(name, "Inscription", created) for name, created in registered])


def account_exists(username: str, configured: list[tuple[str, str]]) -> bool:
    if any(name == username for name, _ in configured):
        return True
    if not isinstance(username, str) or not USERNAME_RE.fullmatch(username):
        return False
    with closing(_connect()) as connection:
        return connection.execute(
            "SELECT 1 FROM registered_accounts WHERE username=?", (username,)
        ).fetchone() is not None


def delete_registered_account(username: str, configured: list[tuple[str, str]]) -> None:
    """Revoke a self-registered account and remove its private dashboard state."""
    if not isinstance(username, str) or not USERNAME_RE.fullmatch(username):
        raise ValueError("Sélectionne un compte inscrit valide.")
    if any(name.casefold() == username.casefold() for name, _ in configured):
        raise ValueError("Un compte initial se retire de INTERNSHIPS_USERS_JSON, pas depuis l’application.")
    from .private_downloads import remove_user_downloads
    remove_user_downloads(username)
    with closing(_connect()) as connection:
        with connection:
            timestamp = datetime.now(timezone.utc).isoformat()
            connection.execute(
                "INSERT INTO blocked_usernames(username, blocked_at) VALUES (?, ?) "
                "ON CONFLICT(username) DO NOTHING", (username, timestamp)
            )
            result = connection.execute(
                "DELETE FROM registered_accounts WHERE username=?", (username,)
            )
            if result.rowcount != 1:
                raise ValueError("Ce compte n’existe plus.")
            connection.execute("DELETE FROM user_data WHERE username=?", (username,))
            for city_table in ("city_events", "city_awarded_offers", "city_tasks", "city_agents",
                               "city_chat_messages", "city_chat_turns", "city_chat_conversations",
                               "city_learning_progress", "city_settings", "city_network_schedule"):
                if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                                      (city_table,)).fetchone():
                    connection.execute(f"DELETE FROM {city_table} WHERE username=?", (username,))
            if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='llm_generation_limits'"
            ).fetchone():
                connection.execute("DELETE FROM llm_generation_limits WHERE username=?", (username,))
            if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='llm_usage'"
            ).fetchone():
                connection.execute(
                    "UPDATE llm_usage SET username='Compte supprimé' WHERE username=?",
                    (username,),
                )
