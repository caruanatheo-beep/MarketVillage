"""Persistent, account-scoped task orchestration for MarketDesk City."""

from __future__ import annotations

import json
import hashlib
import logging
import math
import os
import re
import sqlite3
import threading
import unicodedata
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import state_store


AGENTS = (
    {"id": "desk_manager", "name": "Desk Manager", "role": "Coordinateur", "area": "Trading Floor",
     "description": "Organise les agents, suit les dépendances et rassemble leurs résultats.", "available": True},
    {"id": "market_analyst", "name": "Mira", "role": "Market Analyst", "area": "Trading Floor",
     "description": "Lit les indicateurs, actualités et calendriers de Market Brief.", "available": True},
    {"id": "finance_tutor", "name": "Noé", "role": "Quant Research", "area": "Quant Research",
     "description": "Recherche quantitative, backtests datés et rapports sur demande avec coûts et limites.", "available": True},
    {"id": "job_hunter", "name": "Jules", "role": "Software Engineer", "area": "Engineering",
     "description": "Audite le code City chaque jour et prépare des propositions sur branche isolée, sans intégration automatique.", "available": True},
    {"id": "networker", "name": "Lina", "role": "Networker", "area": "Network",
     "description": "Recherche chaque jour des contacts publics en finance de marché à Paris et retrouve ton réseau enregistré.", "available": True},
    {"id": "securities_scout", "name": "Clara", "role": "Securities Services Scout", "area": "Network",
     "description": "Recherche sur demande des contacts publics en collateral, financement de titres, FX et services titres chez les conservateurs et dépositaires.", "available": True},
    {"id": "outreach_agent", "name": "Iris", "role": "Outreach Agent", "area": "Career Center",
     "description": "Prépare un brouillon depuis un contact et ton profil. Aucun envoi depuis City.", "available": True},
    {"id": "developer", "name": "Axel", "role": "Interview Coach", "area": "Interview Studio",
     "description": "Prépare des questions, évalue les réponses et organise des entretiens blancs sur demande.",
     "available": True},
    {"id": "innovation_lab", "name": "Nova", "role": "Innovation Lab", "area": "Innovation Lab",
     "description": "Veille open source le lundi et le jeudi, avec deux propositions documentées soumises au Desk Manager.", "available": True},
    {"id": "internship_scout", "name": "Hugo", "role": "Internship Scout", "area": "Internships",
     "description": "Actualise Internships chaque jour et transmet les nouveaux stages détectés au Desk Manager. Recherche aussi sur demande.", "available": True},
    {"id": "city_ui_engineer", "name": "Camille", "role": "UI Engineer", "area": "Engineering",
     "description": "Développe les interfaces City et Internships dans un worktree Codex isolé.", "available": True},
    {"id": "internships_engineer", "name": "Sacha", "role": "Sources Engineer", "area": "Engineering",
     "description": "Améliore les sources, dates et doublons d'Internships dans un worktree Codex isolé.", "available": True},
    {"id": "quality_engineer", "name": "Maël", "role": "Quality Engineer", "area": "Engineering",
     "description": "Corrige les régressions et fiabilise les tests dans un worktree Codex isolé.", "available": True},
)
AGENT_BY_ID = {agent["id"]: agent for agent in AGENTS}
TASK_REFRESH = "refresh_opportunities"
ACTIVE = ("queued", "running", "waiting_approval")
FINAL = ("completed", "failed", "cancelled")
CITY_MODELS = ("gpt-4o-mini", "gpt-4.1-mini", "gpt-4o")

_MEMORY_SYNONYMS = {
    "sales": {"commercial", "vente", "coverage", "origination", "salesperson"},
    "commercial": {"sales", "vente", "coverage", "origination"},
    "trading": {"trader", "market", "marches", "negoce", "execution"},
    "trader": {"trading", "market", "marches", "execution"},
    "fixed": {"rates", "taux", "obligataire", "bond", "bonds", "income"},
    "income": {"rates", "taux", "obligataire", "bond", "bonds", "fixed"},
    "obligataire": {"bond", "bonds", "rates", "fixed", "income"},
    "bond": {"bonds", "obligataire", "rates", "fixed", "income"},
    "stage": {"internship", "intern", "stagiaire"},
    "internship": {"stage", "stagiaire", "intern"},
    "contact": {"network", "relation", "linkedin", "interlocuteur"},
    "network": {"contact", "linkedin", "relation", "interlocuteur"},
    "draft": {"email", "mail", "message", "brouillon"},
    "email": {"draft", "mail", "message", "brouillon"},
    "quant": {"quantitative", "pricing", "modelisation"},
    "pricing": {"quant", "valuation", "valorisation"},
    "risk": {"risque", "market", "desk"},
    "fx": {"currency", "change", "foreign"},
    "asset": {"management", "gestion", "portfolio", "am"},
    "management": {"asset", "gestion", "portfolio", "am"},
    "gestion": {"asset", "management", "portfolio", "am"},
    "capital": {"markets", "ecm", "dcm", "syndicate", "syndication"},
    "markets": {"capital", "ecm", "dcm", "syndicate", "syndication"},
    "dcm": {"debt", "capital", "markets", "obligataire", "syndication"},
    "ecm": {"equity", "capital", "markets", "actions"},
}
_MEMORY_STOPWORDS = {"the", "and", "for", "with", "from", "this", "that", "dans", "pour", "avec",
                     "une", "des", "les", "sur", "par", "est", "qui", "aux", "ses", "ton", "tes"}


def _memory_tokens(value: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()
    return [token for token in re.findall(r"[a-z0-9+#]{2,}", folded) if token not in _MEMORY_STOPWORDS]


def _canonical_memory_url(value: str) -> str:
    try:
        parts = urlsplit(str(value or "").strip())
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return ""
        query = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
                 if not key.casefold().startswith(("utm_", "ref", "source"))]
        return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(),
                           parts.path.rstrip("/") or "/", urlencode(sorted(query)), ""))
    except ValueError:
        return ""


def _default_city_model(agent_id: str) -> str:
    selected = os.getenv(f"MARKETDESK_CITY_MODEL_{agent_id.upper()}",
                         os.getenv("MARKETDESK_CITY_MODEL", "gpt-4o-mini"))
    return selected if selected in CITY_MODELS else "gpt-4o-mini"


MODEL_DEFAULTS = {agent["id"]: _default_city_model(agent["id"]) for agent in AGENTS}
DEFAULT_SETTINGS = {"provider": "openai", "models": MODEL_DEFAULTS, "daily_limit_usd": 1.0,
                    "monthly_limit_usd": 15.0, "max_concurrent_tasks": 2, "auto_tasks": True}
CODING_SLOTS_PER_DAY = 6


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CityError(ValueError):
    """A safe error that may be returned to the browser."""


def _due_schedule_periods(operation: str, known: list[str], today: date) -> list[tuple[str, date]]:
    """Group missed periods since the last recorded run; never backfill before first use."""
    if operation == 'innovation_review':
        known = known + [period+'-Mon' for period in known if re.fullmatch(r'\d{4}-W\d{2}',period)]
    def period_for(day: date) -> str:
        if operation == 'innovation_review':
            return day.strftime('%G-W%V') + ('-Mon' if day.weekday() < 3 else '-Thu')
        return day.isoformat()
    previous = []
    for period in known:
        try:
            if operation == 'innovation_review':
                day = datetime.strptime(period[:8]+'-1', '%G-W%V-%u').date()
                if period.endswith('-Thu'):
                    day += timedelta(days=3)
            else:
                day = date.fromisoformat(period)
            if day <= today:
                previous.append(day)
        except ValueError:
            continue
    current = period_for(today)
    if current in known:
        return []
    start = max(previous) + timedelta(days=1) if previous else today
    missing = {}
    for offset in range(max(0, (today-start).days)+1):
        day = start + timedelta(days=offset)
        period = period_for(day)
        if period not in known:
            missing.setdefault(period, day)
    return list(missing.items())


class CityStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else state_store.USER_DB_PATH
        self.active_revision = ''
        self.active_commits: set[str] = set()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS city_agents (
                  username TEXT NOT NULL, agent_id TEXT NOT NULL, xp INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY(username, agent_id)
                );
                CREATE TABLE IF NOT EXISTS city_tasks (
                  id TEXT PRIMARY KEY, username TEXT NOT NULL, agent_id TEXT NOT NULL,
                  task_type TEXT NOT NULL, description TEXT NOT NULL, status TEXT NOT NULL,
                  created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
                  heartbeat_at TEXT, result_json TEXT, error TEXT,
                  xp_awarded INTEGER NOT NULL DEFAULT 0,
                  input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
                  api_cost_usd REAL NOT NULL DEFAULT 0, parameters_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS city_workflows (
                  id TEXT PRIMARY KEY, username TEXT NOT NULL, template TEXT NOT NULL,
                  request TEXT NOT NULL, status TEXT NOT NULL, priority INTEGER NOT NULL,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, result_json TEXT
                );
                CREATE INDEX IF NOT EXISTS city_workflows_by_user
                  ON city_workflows(username, created_at DESC);
                CREATE TABLE IF NOT EXISTS city_shared_results (
                  username TEXT NOT NULL, cache_key TEXT NOT NULL, agent_id TEXT NOT NULL,
                  result_json TEXT NOT NULL, updated_at TEXT NOT NULL,
                  PRIMARY KEY(username, cache_key)
                );
                CREATE TABLE IF NOT EXISTS city_memory (
                  id TEXT PRIMARY KEY, username TEXT NOT NULL, agent_id TEXT NOT NULL,
                  kind TEXT NOT NULL, subject_key TEXT NOT NULL, title TEXT NOT NULL,
                  content TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}',
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                  UNIQUE(username, agent_id, kind, subject_key)
                );
                CREATE INDEX IF NOT EXISTS city_memory_by_user
                  ON city_memory(username, updated_at DESC);
                CREATE TABLE IF NOT EXISTS city_workflow_definitions (
                  id TEXT PRIMARY KEY, username TEXT NOT NULL, name TEXT NOT NULL,
                  steps_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS city_workflow_definitions_by_user
                  ON city_workflow_definitions(username, updated_at DESC);
                DROP INDEX IF EXISTS city_one_active_mission;
                CREATE INDEX IF NOT EXISTS city_tasks_by_user
                  ON city_tasks(username, created_at DESC);
                CREATE TABLE IF NOT EXISTS city_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL,
                  task_id TEXT NOT NULL, agent_id TEXT NOT NULL,
                  status TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS city_events_by_user
                  ON city_events(username, id DESC);
                CREATE TABLE IF NOT EXISTS city_awarded_offers (
                  username TEXT NOT NULL, offer_url TEXT NOT NULL, task_id TEXT NOT NULL,
                  PRIMARY KEY(username, offer_url)
                );
                CREATE TABLE IF NOT EXISTS city_settings (
                  username TEXT PRIMARY KEY, settings_json TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS city_chat_messages (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, agent_id TEXT NOT NULL,
                  role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL,
                  model TEXT, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS city_chat_by_agent
                  ON city_chat_messages(username, agent_id, id DESC);
                CREATE TABLE IF NOT EXISTS city_chat_conversations (
                  username TEXT NOT NULL, agent_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
                  PRIMARY KEY(username, agent_id)
                );
                CREATE TABLE IF NOT EXISTS city_chat_turns (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL,
                  agent_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
                  messages_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS city_chat_turns_by_agent
                  ON city_chat_turns(username, agent_id, id DESC);
                CREATE TABLE IF NOT EXISTS city_learning_progress (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL,
                  question_id TEXT NOT NULL, correct INTEGER NOT NULL,
                  answered_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS city_network_schedule (
                  username TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1,
                  last_day TEXT NOT NULL DEFAULT '', last_task_id TEXT NOT NULL DEFAULT ''
                );
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(city_tasks)")}
            if "parameters_json" not in columns:
                db.execute("ALTER TABLE city_tasks ADD COLUMN parameters_json TEXT NOT NULL DEFAULT '{}'")
            if "scheduled_at" not in columns:
                db.execute("ALTER TABLE city_tasks ADD COLUMN scheduled_at TEXT")
            for column, definition in (
                ("workflow_id", "TEXT"),
                ("depends_on_json", "TEXT NOT NULL DEFAULT '[]'"),
                ("priority", "INTEGER NOT NULL DEFAULT 0"),
                ("retry_count", "INTEGER NOT NULL DEFAULT 0"),
                ("max_retries", "INTEGER NOT NULL DEFAULT 0"),
            ):
                if column not in columns:
                    db.execute(f"ALTER TABLE city_tasks ADD COLUMN {column} {definition}")
            chat_columns = {row[1] for row in db.execute("PRAGMA table_info(city_chat_messages)")}
            for column, definition in (
                ("conversation_id", "TEXT NOT NULL DEFAULT ''"),
                ("input_tokens", "INTEGER NOT NULL DEFAULT 0"),
                ("output_tokens", "INTEGER NOT NULL DEFAULT 0"),
                ("tool_calls_json", "TEXT NOT NULL DEFAULT '[]'"),
            ):
                if column not in chat_columns:
                    db.execute(f"ALTER TABLE city_chat_messages ADD COLUMN {column} {definition}")

        self.migrate_roles()

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=WAL")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _event(db, task, status: str, message: str) -> None:
        db.execute("INSERT INTO city_events(username, task_id, agent_id, status, message, created_at) "
                   "VALUES(?,?,?,?,?,?)", (task["username"], task["id"], task["agent_id"],
                                         status, message, _utc()))

    def migrate_roles(self) -> None:
        from .city_specialists import SPECIALISTS, VERSION
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("CREATE TABLE IF NOT EXISTS city_role_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS city_specialist_schedule(username TEXT NOT NULL, operation TEXT NOT NULL, period TEXT NOT NULL, task_id TEXT NOT NULL, PRIMARY KEY(username,operation,period))")
            db.execute('CREATE TABLE IF NOT EXISTS city_notification_state(username TEXT PRIMARY KEY,last_read_event_id INTEGER NOT NULL DEFAULT 0)')
            db.execute("CREATE TABLE IF NOT EXISTS city_proposal_reviews(task_id TEXT PRIMARY KEY,username TEXT NOT NULL,approved INTEGER NOT NULL,next_task_id TEXT,created_at TEXT NOT NULL)")
            columns = {row[1] for row in db.execute('PRAGMA table_info(city_workflow_definitions)')}
            if 'role_version' not in columns:
                db.execute('ALTER TABLE city_workflow_definitions ADD COLUMN role_version INTEGER NOT NULL DEFAULT 1')
            if db.execute("SELECT 1 FROM city_role_migrations WHERE version=?", (VERSION,)).fetchone():
                return
            for definition in db.execute('SELECT id,steps_json FROM city_workflow_definitions').fetchall():
                steps = json.loads(definition['steps_json'] or '[]')
                if all(step.get('agent_id') not in SPECIALISTS for step in steps):
                    db.execute('UPDATE city_workflow_definitions SET role_version=2 WHERE id=?', (definition['id'],))
            marks = ",".join("?" for _ in SPECIALISTS)
            rows = db.execute(f"SELECT * FROM city_tasks WHERE agent_id IN ({marks}) AND status IN ('queued','running','waiting_approval')", tuple(SPECIALISTS)).fetchall()
            for task in rows:
                db.execute("UPDATE city_tasks SET status='cancelled',finished_at=?,error=? WHERE id=?",
                           (_utc(), "Ancienne spécialisation : mission archivée lors de la réorganisation.", task['id']))
                self._event(db, task, "cancelled", "Ancienne spécialisation archivée ; historique conservé.")
                self._refresh_workflow(db, task['workflow_id'])
            # Keep legacy memories/results for history, outside current-role cache keys.
            # Old results/tasks stay in history, but must never be reused as new-role results.
            db.execute("INSERT INTO city_role_migrations VALUES(?,?)", (VERSION, _utc()))

    def enqueue_specialist_schedules(self, now: datetime | None = None) -> int:
        from zoneinfo import ZoneInfo
        from .city_specialists import VERSION, CODING_AGENTS
        moment = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("Europe/Paris"))
        day, week = moment.date().isoformat(), moment.strftime("%G-W%V")
        schedules = [("market_analyst", "collect_markets", day, "Brief quotidien des marchés"),
                     ("job_hunter", "repository_audit", day, "Revue quotidienne du code City"),
                     ("internship_scout", "refresh_internships", day, "Nouveaux stages détectés aujourd’hui"),
                     ("innovation_lab", "innovation_review", week + ("-Mon" if moment.weekday() < 3 else "-Thu"), "Deux innovations open source")]
        if date(2026, 11, 4) <= moment.date() < date(2026, 12, 4):
            minutes = moment.hour * 60 + moment.minute
            schedules.extend((agent_id, f'develop:{agent_id}:{slot}', day,
                              f'Développement autonome {slot}/{CODING_SLOTS_PER_DAY} · {AGENT_BY_ID[agent_id]["name"]}')
                             for index, agent_id in enumerate(CODING_AGENTS)
                             for slot in range(1, CODING_SLOTS_PER_DAY + 1)
                             if minutes >= 6 * 60 + (slot - 1) * 150 + index * 20)
        count = 0
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            # Cancel only pending automatic missions removed from the schedule, preserving manual requests/history.
            retired = db.execute("SELECT t.* FROM city_tasks t JOIN city_specialist_schedule s ON s.task_id=t.id "
                                 "AND s.username=t.username WHERE t.agent_id IN ('developer','finance_tutor') "
                                 "AND t.status IN ('queued','waiting_approval')").fetchall()
            for task in retired:
                db.execute("UPDATE city_tasks SET status='cancelled',finished_at=? WHERE id=?", (_utc(), task['id']))
                self._event(db, task, 'cancelled', 'Mission désormais disponible sur demande uniquement.')
            # An existing weekly Nova run already counts as the first half of this week.
            db.execute("INSERT OR IGNORE INTO city_specialist_schedule(username,operation,period,task_id) "
                       "SELECT username,operation,?,task_id FROM city_specialist_schedule "
                       "WHERE operation='innovation_review' AND period=?", (week+'-Mon',week))
            # One ChatGPT subscription is shared by every City account on this instance.
            users = db.execute("SELECT DISTINCT a.username FROM city_agents a ORDER BY "
                               "COALESCE((SELECT MAX(m.created_at) FROM city_chat_messages m "
                               "WHERE m.username=a.username),'') DESC").fetchall()
            priority = {row[0]: index for index, row in enumerate(users)}
            existing_code = db.execute(
                "SELECT DISTINCT s.operation,s.period,t.id,t.username,t.agent_id,t.status FROM city_specialist_schedule s "
                "JOIN city_tasks t ON t.id=s.task_id AND t.username=s.username "
                "WHERE s.operation LIKE 'develop:%' AND s.period=?", (day,)).fetchall()
            owners = {}
            for scheduled in existing_code:
                key = (scheduled['operation'], scheduled['period'])
                if key not in owners or priority.get(scheduled['username'], len(priority)) < priority.get(owners[key], len(priority)):
                    owners[key] = scheduled['username']
            for scheduled in existing_code:
                if scheduled['status'] == 'queued' and scheduled['username'] != owners[(scheduled['operation'], scheduled['period'])]:
                    db.execute("UPDATE city_tasks SET status='cancelled',finished_at=?,error=? WHERE id=? AND status='queued'",
                               (_utc(), 'Créneau de code partagé entre les comptes City.', scheduled['id']))
                    self._event(db, scheduled, 'cancelled', 'Créneau automatique partagé : doublon annulé sans appel Codex.')
            for user in users:
                saved = db.execute("SELECT settings_json FROM city_settings WHERE username=?", (user[0],)).fetchone()
                if saved and not json.loads(saved[0]).get('auto_tasks', True):
                    continue
                for agent_id, operation, period, title in schedules:
                    if operation.startswith('develop:') and db.execute(
                            "SELECT 1 FROM city_specialist_schedule WHERE operation=? AND period=? LIMIT 1",
                            (operation, period)).fetchone():
                        continue
                    if not operation.startswith('develop:') and db.execute("SELECT 1 FROM city_tasks WHERE username=? AND agent_id=? AND status IN ('queued','running','waiting_approval')", (user[0], agent_id)).fetchone():
                        continue
                    task_id = uuid.uuid4().hex
                    known = [row[0] for row in db.execute("SELECT period FROM city_specialist_schedule WHERE username=? AND operation=?", (user[0],operation))]
                    due = _due_schedule_periods(operation, known, moment.date())
                    if not due:
                        continue
                    db.executemany("INSERT INTO city_specialist_schedule VALUES(?,?,?,?)",
                                   [(user[0], operation, missed, task_id) for missed,_ in due])
                    payload = dict(operation='develop' if operation.startswith('develop:') else operation,
                                   period=period, role_version=VERSION)
                    task_title = title
                    if len(due) > 1:
                        payload['catch_up'] = {'from':due[0][1].isoformat(), 'to':day, 'periods':len(due)}
                        task_title = f"Rattrapage · {title} ({due[0][1].isoformat()} → {day})"
                    if agent_id == 'internship_scout':
                        payload.update(report_mode='detected_today', daily_digest=True)
                    if agent_id == 'market_analyst':
                        payload['daily_digest'] = True
                    parameters = json.dumps(payload)
                    db.execute("INSERT INTO city_tasks(id,username,agent_id,task_type,description,status,created_at,parameters_json) VALUES(?,?,?,?,?,'queued',?,?)",
                               (task_id, user[0], agent_id, 'agent:'+agent_id, task_title, _utc(), parameters))
                    self._event(db, dict(id=task_id, username=user[0], agent_id=agent_id), 'queued', task_title)
                    count += 1
        return count

    def ensure_agents(self, username: str) -> None:
        with self.db() as db:
            existing = {row[0] for row in db.execute("SELECT agent_id FROM city_agents WHERE username=?",
                                                     (username,))}
            missing = [(username, agent["id"]) for agent in AGENTS if agent["id"] not in existing]
            if missing:
                db.executemany("INSERT OR IGNORE INTO city_agents(username, agent_id) VALUES(?,?)", missing)
            db.execute("INSERT OR IGNORE INTO city_network_schedule(username) VALUES(?)", (username,))

    def review_specialist_proposal(self, username: str, task_id: str, approved: bool) -> dict:
        """Authenticated human decision, never an LLM approval; one handoff per result."""
        from .city_specialists import VERSION
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS city_proposal_reviews(task_id TEXT PRIMARY KEY,username TEXT NOT NULL,approved INTEGER NOT NULL,next_task_id TEXT,created_at TEXT NOT NULL)")
            source = db.execute("SELECT * FROM city_tasks WHERE id=? AND username=? AND status='completed'", (task_id, username)).fetchone()
            if not source or source['agent_id'] not in {'job_hunter', 'innovation_lab'}:
                raise CityError("Proposition spécialisée introuvable sur ton compte.")
            result = json.loads(source['result_json'] or '{}')
            if result.get('role_version') != VERSION or not result.get('approval_required') or result.get('branch'):
                raise CityError("Ce résultat ne contient pas de proposition à transmettre.")
            prior = db.execute("SELECT next_task_id,approved FROM city_proposal_reviews WHERE task_id=?", (task_id,)).fetchone()
            if prior:
                return {'task_id': prior[0], 'approved': bool(prior[1]), 'reused': True}
            if approved and source['agent_id'] == 'job_hunter' and not result.get('revision'):
                raise CityError("Préparation bloquée : un clone Git valide est nécessaire. Aucun fichier de l'application ne sera modifié.")
            next_id = uuid.uuid4().hex if approved else None
            db.execute("INSERT INTO city_proposal_reviews VALUES(?,?,?,?,?)", (task_id, username, int(approved), next_id, _utc()))
            result.update(review_decision='approved' if approved else 'rejected', next_task_id=next_id)
            db.execute('UPDATE city_tasks SET result_json=? WHERE id=? AND username=?', (json.dumps(result, ensure_ascii=False), task_id, username))
            self._record_decision(db, username, 'desk_manager', 'proposal:'+task_id,
                                  'Proposition approuvée' if approved else 'Proposition refusée', source['description'], {'source_task_id':task_id})
            if next_id:
                operation = 'prepare_branch' if source['agent_id'] == 'job_hunter' else 'repository_audit'
                parameters = dict(operation=operation, source_task_id=task_id, role_version=VERSION)
                task = dict(id=next_id, username=username, agent_id='job_hunter')
                db.execute("INSERT INTO city_tasks(id,username,agent_id,task_type,description,status,created_at,parameters_json,depends_on_json) VALUES(?,?,'job_hunter','agent:job_hunter',?,'queued',?,?,?)",
                           (next_id, username, 'Préparer une branche isolée' if operation == 'prepare_branch' else 'Étudier la proposition Nova validée', _utc(), json.dumps(parameters), json.dumps([task_id])))
                self._event(db, task, 'queued', 'Transfert à Jules après validation explicite.')
        return {'task_id': next_id, 'approved': approved, 'reused': False}

    def network_schedule(self, username: str, enabled: bool | None = None) -> dict:
        self.ensure_agents(username)
        with self.db() as db:
            if enabled is not None:
                db.execute("UPDATE city_network_schedule SET enabled=? WHERE username=?", (int(enabled), username))
            row = db.execute("SELECT * FROM city_network_schedule WHERE username=?", (username,)).fetchone()
            task = db.execute("SELECT status,error,finished_at,result_json FROM city_tasks WHERE id=? AND username=?",
                              (row['last_task_id'], username)).fetchone()
        report = json.loads(task['result_json'] or '{}') if task else {}
        return {"enabled": bool(row['enabled']), "last_day": row['last_day'],
                "last_task_id": row['last_task_id'], "status": task['status'] if task else "idle",
                "error": task['error'] if task else "", "finished_at": task['finished_at'] if task else "",
                "report": {k: report[k] for k in ('count', 'sales_count', 'duplicates', 'rejected', 'target', 'model', 'source', 'text', 'warnings') if k in report}}

    def securities_scout_status(self, username: str) -> dict:
        with self.db() as db:
            task = db.execute("SELECT id,status,created_at,finished_at,error,result_json FROM city_tasks "
                              "WHERE username=? AND agent_id='securities_scout' "
                              "ORDER BY created_at DESC,rowid DESC LIMIT 1", (username,)).fetchone()
        if not task:
            return {"status": "idle"}
        result = json.loads(task['result_json'] or '{}')
        summary = str(result.get('text') or result.get('summary') or '').splitlines()
        return {"id": task['id'], "status": task['status'], "created_at": task['created_at'],
                "finished_at": task['finished_at'], "error": task['error'],
                "summary": summary[0][:300] if summary else ''}

    def enqueue_network_daily(self, username: str | None = None, *, manual: bool = False) -> int:
        if manual:
            if not username:
                raise CityError("Compte requis pour une recherche manuelle.")
            self.ensure_agents(username)
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()
        count = 0
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT * FROM city_network_schedule WHERE (? OR (enabled=1 AND last_day!=?)) "
                              "AND (? IS NULL OR username=?)", (manual, today, username, username)).fetchall()
            for row in rows:
                if db.execute("SELECT 1 FROM city_tasks WHERE username=? AND agent_id='networker' "
                              "AND status IN ('queued','running','waiting_approval')", (row['username'],)).fetchone():
                    continue
                task = {"id": uuid.uuid4().hex, "username": row['username'], "agent_id": "networker",
                        "status": "queued", "created_at": _utc()}
                payload = {"discover_public": True, "day": today}
                try:
                    missed = (date.fromisoformat(today)-date.fromisoformat(row['last_day'])).days
                except ValueError:
                    missed = 0
                if missed > 1:
                    payload['catch_up'] = {'from':(date.fromisoformat(row['last_day'])+timedelta(days=1)).isoformat(),
                                           'to':today, 'periods':missed}
                description = "Trouver 10 nouveaux contacts, priorité Sales de marché à Paris"
                if payload.get('catch_up'):
                    description = f"Rattrapage contacts Lina ({payload['catch_up']['from']} → {today})"
                db.execute("INSERT INTO city_tasks(id,username,agent_id,task_type,description,status,created_at,parameters_json) "
                           "VALUES(?,?,'networker','agent:networker',?,'queued',?,?)",
                           (task['id'], row['username'], description, task['created_at'],
                            json.dumps(payload)))
                db.execute("UPDATE city_network_schedule SET last_day=?,last_task_id=? WHERE username=?",
                           (today, task['id'], row['username']))
                self._event(db, task, "queued", description if payload.get('catch_up') else
                            "Recherche manuelle de contacts publics demandée à Lina." if manual
                            else "Collecte quotidienne de contacts publics planifiée pour Lina.")
                count += 1
        return count

    def notification_state(self, username: str, read_through: int | None = None) -> dict:
        with self.db() as db:
            if read_through is not None:
                if isinstance(read_through,bool) or not isinstance(read_through,int) or read_through < 0:
                    raise CityError('Identifiant de notification invalide.')
                latest = db.execute('SELECT COALESCE(MAX(id),0) FROM city_events WHERE username=?',(username,)).fetchone()[0]
                db.execute('INSERT INTO city_notification_state VALUES(?,?) ON CONFLICT(username) DO UPDATE SET last_read_event_id=MAX(last_read_event_id,excluded.last_read_event_id)',
                           (username,min(read_through,latest)))
            row = db.execute('SELECT last_read_event_id FROM city_notification_state WHERE username=?',(username,)).fetchone()
        return {'last_read_event_id':row[0] if row else 0}

    def get_settings(self, username: str) -> dict:
        with self.db() as db:
            row = db.execute("SELECT settings_json FROM city_settings WHERE username=?", (username,)).fetchone()
        settings = {**DEFAULT_SETTINGS, "models": dict(MODEL_DEFAULTS)}
        if row:
            try:
                saved = json.loads(row[0])
                if isinstance(saved, dict):
                    for key in ("provider", "daily_limit_usd", "monthly_limit_usd", "max_concurrent_tasks", "auto_tasks"):
                        if key in saved:
                            settings[key] = saved[key]
                    if isinstance(saved.get("models"), dict):
                        settings["models"].update({key: value for key, value in saved["models"].items()
                                                   if key in MODEL_DEFAULTS and value in CITY_MODELS})
            except (TypeError, ValueError):
                pass
        return settings

    def save_settings(self, username: str, supplied: dict) -> dict:
        current = self.get_settings(username)
        if supplied.get("provider", "openai") != "openai":
            raise CityError("Seul le fournisseur OpenAI est configur\u00e9.")
        models = supplied.get("models", current["models"])
        if not isinstance(models, dict) or any(key not in MODEL_DEFAULTS or value not in CITY_MODELS
                                               for key, value in models.items()):
            raise CityError("Choisis un mod\u00e8le disponible dans la liste.")
        try:
            daily = float(supplied.get("daily_limit_usd", current["daily_limit_usd"]))
            monthly = float(supplied.get("monthly_limit_usd", current["monthly_limit_usd"]))
            concurrency = int(supplied.get("max_concurrent_tasks", current["max_concurrent_tasks"]))
        except (TypeError, ValueError) as exc:
            raise CityError("Les limites doivent \u00eatre des nombres valides.") from exc
        if not 0 <= daily <= 1000 or not 0 <= monthly <= 10000 or not 1 <= concurrency <= 6:
            raise CityError("Limites autoris\u00e9es : 0\u20131000 $ par jour, 0\u201310000 $ par mois et 1\u20136 t\u00e2ches simultan\u00e9es.")
        auto_tasks = supplied.get("auto_tasks", current["auto_tasks"])
        if not isinstance(auto_tasks, bool):
            raise CityError("Le r\u00e9glage d'ex\u00e9cution doit \u00eatre vrai ou faux.")
        current.update(provider="openai", models={**current["models"], **models}, daily_limit_usd=daily,
                       monthly_limit_usd=monthly, max_concurrent_tasks=concurrency, auto_tasks=auto_tasks)
        with self.db() as db:
            db.execute("INSERT INTO city_settings(username,settings_json,updated_at) VALUES(?,?,?) "
                       "ON CONFLICT(username) DO UPDATE SET settings_json=excluded.settings_json,updated_at=excluded.updated_at",
                       (username, json.dumps(current, ensure_ascii=False), _utc()))
        return current

    def chat_history(self, username: str, agent_id: str, limit: int = 80) -> list[dict]:
        if agent_id not in AGENT_BY_ID:
            raise CityError("Agent inconnu.")
        with self.db() as db:
            rows = db.execute("SELECT id,role,content,model,created_at,conversation_id,input_tokens,"
                              "output_tokens,tool_calls_json FROM city_chat_messages "
                              "WHERE username=? AND agent_id=? ORDER BY id DESC LIMIT ?",
                              (username, agent_id, max(1, min(100, limit)))).fetchall()
        history = []
        for row in reversed(rows):
            message = dict(row)
            try:
                message["tool_calls"] = json.loads(message.pop("tool_calls_json"))
            except (TypeError, ValueError):
                message["tool_calls"] = []
            history.append(message)
        return history

    def morning_briefing(self, username: str, now: datetime | None = None) -> str:
        """Summarize persisted work for one account; no model call or new collection."""
        from zoneinfo import ZoneInfo
        from .city_specialists import DEVELOPMENT_AGENTS
        moment = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("Europe/Paris"))
        names = {"market_analyst": "Mira", "internship_scout": "Hugo", "networker": "Lina", "job_hunter": "Jules"}
        day_start = moment.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
        with self.db() as db:
            latest = {agent: db.execute(
                "SELECT description,finished_at,result_json FROM city_tasks WHERE username=? AND agent_id=? "
                "AND status='completed' ORDER BY finished_at DESC,rowid DESC LIMIT 1", (username, agent)).fetchone()
                for agent in names}
            failed_today = {agent: db.execute(
                "SELECT error,finished_at FROM city_tasks WHERE username=? AND agent_id=? AND status='failed' "
                "AND finished_at>=? ORDER BY finished_at DESC LIMIT 1",
                (username, agent, day_start)).fetchone() for agent in names}
            proposals = db.execute(
                "SELECT description FROM city_tasks WHERE username=? AND status='completed' "
                "AND agent_id IN ('job_hunter','innovation_lab') "
                "AND json_extract(COALESCE(result_json,'{}'),'$.role_version')=2 "
                "AND json_extract(COALESCE(result_json,'{}'),'$.approval_required')=1 "
                "AND COALESCE(json_extract(COALESCE(result_json,'{}'),'$.review_decision'),'')='' "
                "AND COALESCE(json_extract(COALESCE(result_json,'{}'),'$.branch'),'')='' "
                "ORDER BY finished_at DESC LIMIT 5", (username,)).fetchall()
            waiting = db.execute(
                "SELECT description FROM city_tasks WHERE username=? AND status='waiting_approval' "
                "ORDER BY created_at DESC LIMIT 5", (username,)).fetchall()
            failures = db.execute(
                "SELECT COUNT(*) FROM city_tasks WHERE username=? AND status='failed' AND finished_at>=?",
                (username, (moment - timedelta(days=7)).astimezone(timezone.utc).isoformat())).fetchone()[0]
            marks = ','.join('?' for _ in DEVELOPMENT_AGENTS)
            development = db.execute(
                f"SELECT agent_id,status,result_json,error FROM city_tasks WHERE username=? AND agent_id IN ({marks}) "
                "AND json_extract(parameters_json,'$.operation')='develop' AND finished_at>=? "
                "ORDER BY finished_at LIMIT 16", (username, *DEVELOPMENT_AGENTS, day_start)).fetchall()
            development_active = db.execute(
                "SELECT COUNT(*) FROM city_tasks WHERE username=? AND created_at>=? "
                "AND json_extract(parameters_json,'$.operation')='develop' AND status IN ('queued','running')",
                (username, day_start)).fetchone()[0]
        lines = [f"### Briefing du {moment:%d/%m/%Y} · Desk Manager", "", "**Derniers résultats enregistrés**"]
        for agent, label in names.items():
            row = latest[agent]
            if not row:
                lines.append(f"- {label} : aucun résultat enregistré.")
                if failed_today[agent]:
                    lines.append(f"  Collecte du jour en échec : {failed_today[agent][0][:160]}")
                continue
            result = json.loads(row["result_json"] or "{}")
            finished = datetime.fromisoformat(row["finished_at"]).astimezone(ZoneInfo("Europe/Paris"))
            summary = str(result.get("summary") or result.get("text") or row["description"]).splitlines()[0].lstrip('# ')[:220]
            lines.append(f"- {label} ({finished:%d/%m %H:%M}) : {summary}")
            if failed_today[agent] and failed_today[agent][1] > row['finished_at']:
                lines.append(f"  Collecte du jour en échec : {failed_today[agent][0][:160]}")
            if finished.date() == moment.date() and agent == "market_analyst" and result.get("text"):
                lines.extend(["", "**Analyse de Mira**", str(result["text"])[:3500]])
            if finished.date() == moment.date() and agent == "internship_scout":
                offers = result.get("offers") or []
                if offers:
                    lines.append("**Stages détectés**")
                    lines.extend(f"- {offer['title']} · {offer['company']} — {offer['url']}"
                                 for offer in offers[:20])
                    if len(offers) > 20:
                        lines.append(f"- {len(offers)-20} autres offres dans le résultat de Hugo.")
            if finished.date() == moment.date() and agent == "networker":
                contacts = result.get("contacts") or []
                if contacts:
                    lines.append("**Contacts ajoutés**")
                    lines.extend(f"- {contact['name']} · {contact['role']} · {contact['company']}"
                                 for contact in contacts[:10])
        lines.extend(["", "**Développement du jour**"])
        integrated = 0
        for row in development:
            result = json.loads(row['result_json'] or '{}')
            if result.get('integrated'):
                integrated += 1
                name = AGENT_BY_ID[row['agent_id']]['name']
                summary = str(result.get('text') or '').splitlines()[0][:180]
                lines.append(f"- {name} · {result['commit'][:12]} : {summary} ({len(result.get('files') or [])} fichier(s))")
        if not integrated:
            lines.append('- Aucun changement intégré aujourd’hui.')
        blocked = [row for row in development if row['status'] == 'failed']
        if blocked:
            lines.append(f"- {len(blocked)} mission(s) non intégrée(s) : détails dans Notifications.")
        if development_active:
            lines.append(f"- {development_active} mission(s) de code encore en attente ou en cours : suivi dans Missions > Équipe de code.")
        decisions = [row["description"] for row in [*proposals, *waiting]]
        lines.extend(["", "**À décider**"])
        lines.extend(f"- {item[:180]}" for item in decisions[:5])
        if not decisions:
            lines.append("- Aucune décision en attente.")
        if failures:
            lines.append(f"- {failures} mission(s) en erreur sur les sept derniers jours : voir Notifications.")
        lines.append("\nLes horaires sont à l'heure de Paris. Ouvre Notifications pour consulter les sources et les résultats complets.")
        return "\n".join(lines)

    def enqueue_daily_digest(self, now: datetime | None = None) -> int:
        """Publish one free, persisted manager digest after today's scheduled work finishes."""
        from zoneinfo import ZoneInfo
        from .city_specialists import CODING_AGENTS
        moment = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("Europe/Paris"))
        if moment.hour < 8:
            return 0
        day = moment.date().isoformat()
        count = 0
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            users = db.execute("SELECT DISTINCT username FROM city_agents").fetchall()
            for user in users:
                username = user[0]
                saved = db.execute("SELECT settings_json FROM city_settings WHERE username=?", (username,)).fetchone()
                if saved and not json.loads(saved[0]).get("auto_tasks", True):
                    continue
                if db.execute("SELECT 1 FROM city_tasks WHERE username=? AND task_type='daily_digest' "
                              "AND json_extract(parameters_json,'$.day')=?", (username, day)).fetchone():
                    continue
                scheduled = db.execute("SELECT s.operation,t.status FROM city_specialist_schedule s "
                                       "JOIN city_tasks t ON t.id=s.task_id AND t.username=s.username "
                                       "WHERE s.username=? AND s.period=? AND s.operation IN "
                                       "('collect_markets','refresh_internships','repository_audit')",
                                       (username, day)).fetchall()
                states = {row[0]: row[1] for row in scheduled}
                if any(states.get(operation) not in FINAL for operation in
                       ("collect_markets", "refresh_internships", "repository_audit")):
                    continue
                if date(2026, 11, 4) <= moment.date() < date(2026, 12, 4):
                    development = db.execute("SELECT t.status FROM city_specialist_schedule s "
                                             "JOIN city_tasks t ON t.id=s.task_id AND t.username=s.username "
                                             "WHERE s.username=? AND s.period=? AND s.operation LIKE 'develop:%'",
                                             (username, day)).fetchall()
                    if (len(development) < CODING_SLOTS_PER_DAY * len(CODING_AGENTS)
                            or any(row[0] not in FINAL for row in development)) and moment.hour < 22:
                        continue
                lina = db.execute("SELECT enabled,last_day,last_task_id FROM city_network_schedule WHERE username=?",
                                  (username,)).fetchone()
                if lina and lina['enabled']:
                    lina_task = db.execute("SELECT status FROM city_tasks WHERE id=? AND username=?",
                                           (lina['last_task_id'], username)).fetchone()
                    if lina['last_day'] != day or not lina_task or lina_task[0] not in FINAL:
                        continue
                content = self.morning_briefing(username, moment)
                task_id = uuid.uuid4().hex
                now_utc = _utc()
                db.execute("INSERT INTO city_tasks(id,username,agent_id,task_type,description,status,created_at,finished_at,result_json,parameters_json) "
                           "VALUES(?,?, 'desk_manager','daily_digest',?,'completed',?,?,?,?)",
                           (task_id, username, f"Synthèse City du {moment:%d/%m/%Y}", now_utc, now_utc,
                            json.dumps({"title": "Synthèse quotidienne", "text": content,
                                        "summary": "Marchés, stages, contacts et décisions du jour."}, ensure_ascii=False),
                            json.dumps({"day": day})))
                self._event(db, {"id": task_id, "username": username, "agent_id": "desk_manager"},
                            "completed", "Synthèse quotidienne disponible : marchés, stages, contacts et décisions.")
                db.execute("INSERT OR IGNORE INTO city_chat_conversations(username,agent_id,conversation_id) "
                           "VALUES(?,'desk_manager',?)", (username, uuid.uuid4().hex))
                conversation = db.execute("SELECT conversation_id FROM city_chat_conversations "
                                          "WHERE username=? AND agent_id='desk_manager'", (username,)).fetchone()[0]
                db.execute("INSERT INTO city_chat_messages(username,agent_id,role,content,model,created_at,conversation_id,input_tokens,output_tokens,tool_calls_json) "
                           "VALUES(?,'desk_manager','assistant',?,'',?,?,0,0,'[]')",
                           (username, content[:12000], now_utc, conversation))
                count += 1
        return count

    def conversation_id(self, username: str, agent_id: str) -> str:
        if agent_id not in AGENT_BY_ID:
            raise CityError("Agent inconnu.")
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO city_chat_conversations(username,agent_id,conversation_id) "
                       "VALUES(?,?,?)", (username, agent_id, uuid.uuid4().hex))
            return db.execute("SELECT conversation_id FROM city_chat_conversations WHERE username=? AND agent_id=?",
                              (username, agent_id)).fetchone()[0]

    def chat_turns(self, username: str, agent_id: str, limit: int = 6) -> list[str]:
        with self.db() as db:
            rows = db.execute("SELECT messages_json FROM city_chat_turns WHERE username=? AND agent_id=? "
                              "ORDER BY id DESC LIMIT ?", (username, agent_id, max(1, min(10, limit)))).fetchall()
        return [row[0] for row in reversed(rows)]

    def save_chat_turn(self, username: str, agent_id: str, messages_json: str) -> None:
        if len(messages_json) > 120000:
            return  # Never persist a broken partial JSON document.
        conversation_id = self.conversation_id(username, agent_id)
        with self.db() as db:
            db.execute("INSERT INTO city_chat_turns(username,agent_id,conversation_id,messages_json,created_at) "
                       "VALUES(?,?,?,?,?)", (username, agent_id, conversation_id,
                                              messages_json, _utc()))
            db.execute("DELETE FROM city_chat_turns WHERE username=? AND agent_id=? AND id NOT IN "
                       "(SELECT id FROM city_chat_turns WHERE username=? AND agent_id=? ORDER BY id DESC LIMIT 20)",
                       (username, agent_id, username, agent_id))

    def append_chat_message(self, username: str, agent_id: str, role: str, content: str, model: str = "",
                            input_tokens: int = 0, output_tokens: int = 0,
                            tool_calls: list[dict] | None = None) -> None:
        if agent_id not in AGENT_BY_ID or role not in {"user", "assistant"}:
            raise CityError("Message de conversation invalide.")
        conversation_id = self.conversation_id(username, agent_id)
        with self.db() as db:
            db.execute("INSERT INTO city_chat_messages(username,agent_id,role,content,model,created_at,"
                       "conversation_id,input_tokens,output_tokens,tool_calls_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (username, agent_id, role, content[:12000], model[:100], _utc(),
                        conversation_id, max(0, input_tokens),
                        max(0, output_tokens), json.dumps(tool_calls or [], ensure_ascii=False)[:12000]))
            db.execute("DELETE FROM city_chat_messages WHERE username=? AND agent_id=? AND id NOT IN "
                       "(SELECT id FROM city_chat_messages WHERE username=? AND agent_id=? ORDER BY id DESC LIMIT 200)",
                       (username, agent_id, username, agent_id))

    def clear_chat(self, username: str, agent_id: str) -> None:
        if agent_id not in AGENT_BY_ID:
            raise CityError("Agent inconnu.")
        with self.db() as db:
            db.execute("DELETE FROM city_chat_messages WHERE username=? AND agent_id=?", (username, agent_id))
            db.execute("DELETE FROM city_chat_turns WHERE username=? AND agent_id=?", (username, agent_id))
            db.execute("DELETE FROM city_chat_conversations WHERE username=? AND agent_id=?", (username, agent_id))

    def record_learning_answer(self, username: str, question_id: str, correct: bool) -> None:
        with self.db() as db:
            db.execute("INSERT INTO city_learning_progress(username,question_id,correct,answered_at) "
                       "VALUES(?,?,?,?)", (username, question_id, int(correct), _utc()))

    def learning_progress(self, username: str) -> dict:
        with self.db() as db:
            row = db.execute("SELECT COUNT(*), COALESCE(SUM(correct),0) FROM city_learning_progress "
                             "WHERE username=?", (username,)).fetchone()
        return {"attempts": row[0], "correct": row[1], "source": "réponses évaluées dans City"}

    def create_task(self, username: str, agent_id: str, description: str, parameters: dict | None = None,
                    scheduled_at: str | None = None, source_task_id: str | None = None,
                    auto_run: bool = False) -> dict:
        if not username or len(username) > 128:
            raise CityError("Compte invalide.")
        agent = AGENT_BY_ID.get(agent_id)
        if agent is None:
            raise CityError("Agent inconnu.")
        if agent_id == "desk_manager" and (parameters or {}).get("operation") not in {"refresh_internships", "develop"}:
            raise CityError("Utilise un processus du Desk Manager pour coordonner les agents.")
        if not agent["available"]:
            raise CityError("Aucun workflow n'est connecté à cet agent.")
        description = (description or "").strip()
        if len(description) > 240:
            raise CityError("La mission est trop longue (240 caractères maximum).")
        from .city_specialists import validate_mission
        parameters = validate_mission(agent_id, parameters or {}, description)
        if not description:
            description = AGENT_BY_ID[agent_id]['role']
        self.ensure_agents(username)
        if scheduled_at:
            try:
                scheduled = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise CityError("Invalid scheduled time.") from exc
            if scheduled.tzinfo is None:
                raise CityError("Scheduled time must include a timezone.")
            now_utc = datetime.now(timezone.utc)
            if not now_utc < scheduled <= now_utc + timedelta(days=30):
                raise CityError("Schedule a mission within the next 30 days.")
            scheduled_at = scheduled.astimezone(timezone.utc).isoformat(timespec="seconds")
        settings = self.get_settings(username)
        now = _utc()
        parameters_json = json.dumps(parameters or {}, ensure_ascii=False)
        if len(parameters_json) > 4000:
            raise CityError("Paramètres de mission trop longs.")
        task = {"id": uuid.uuid4().hex, "username": username, "agent_id": agent_id,
                "task_type": f"agent:{agent_id}", "description": description,
                "status": "queued" if settings["auto_tasks"] or auto_run else "waiting_approval",
                "parameters_json": parameters_json,
                "created_at": now, "scheduled_at": scheduled_at,
                "depends_on_json": json.dumps([source_task_id] if source_task_id else [])}
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if source_task_id and not db.execute(
                    "SELECT 1 FROM city_tasks WHERE id=? AND username=? AND status='completed'",
                    (source_task_id, username)).fetchone():
                raise CityError("La mission source doit être terminée et t'appartenir.")
            limit = max(1, int(os.getenv("MARKETDESK_CITY_DAILY_MISSIONS", "5")))
            today = datetime.now(timezone.utc).date().isoformat()
            count = db.execute("SELECT COUNT(*) FROM city_tasks WHERE username=? AND agent_id=? "
                               "AND substr(created_at,1,10)=? AND status!='cancelled'",
                               (username, agent_id, today)).fetchone()[0]
            if count >= limit:
                raise CityError(f"Limite de {limit} actualisations City atteinte aujourd'hui.")
            active = db.execute("SELECT COUNT(*) FROM city_tasks WHERE username=? AND status IN "
                                "('queued','running','waiting_approval')", (username,)).fetchone()[0]
            if active >= settings["max_concurrent_tasks"]:
                raise CityError("Concurrent mission limit reached. Finish or cancel a mission first.")
            if db.execute("SELECT 1 FROM city_tasks WHERE username=? AND agent_id=? AND status IN "
                          "('queued','running','waiting_approval') LIMIT 1", (username, agent_id)).fetchone():
                raise CityError(f"{agent['name']} a déjà une mission active.")
            try:
                db.execute("INSERT INTO city_tasks(id,username,agent_id,task_type,description,status,created_at,parameters_json,scheduled_at,depends_on_json) "
                           "VALUES(:id,:username,:agent_id,:task_type,:description,:status,:created_at,:parameters_json,:scheduled_at,:depends_on_json)", task)
            except sqlite3.IntegrityError as exc:
                raise CityError("Une actualisation est déjà en attente ou en cours pour ce compte.") from exc
            task.pop("parameters_json", None)
            task["depends_on"] = json.loads(task.pop("depends_on_json"))
            self._event(db, task, task["status"], "Mission added to queue." if task["status"] == "queued" else "Mission waiting for your approval.")
        return task

    def create_workflow(self, username: str, template: str, request: str, focus: str = "",
                        priority: int = 1) -> dict:
        """Persist a bounded DAG. Only the listed service adapters can execute its steps."""
        if not username or len(username) > 128 or not isinstance(request, str) or not request.strip() or len(request) > 500:
            raise CityError("Décris le projet en 500 caractères maximum.")
        if not isinstance(focus, str) or len(focus) > 100 or priority not in (0, 1, 2):
            raise CityError("Priorité ou thème de recherche invalide.")
        plans = {
            "careers_outreach": (
                ("networker", "Identifier les contacts enregistrés", {"query": focus}, ()),
                ("outreach_agent", "Préparer un brouillon pour un contact pertinent", {}, (0,)),
            ),
            "market_learning": (
                ("market_analyst", "Lire le brief de marché", {}, ()),
                ("finance_tutor", "Produire un backtest quantitatif", {"operation":"quant_report", "role_version":2}, (0,)),
            ),
            "source_review": (("job_hunter", "Auditer le code City", {"operation":"repository_audit", "role_version":2}, ()),),
            "innovation_engineering": (("innovation_lab", "Proposer deux innovations documentées", {"operation":"innovation_review", "role_version":2}, ()),),
            "interview_training": (("developer", "Préparer cinq questions de marché", {"operation":"daily_questions", "role_version":2}, ()),),
        }
        if template not in plans:
            raise CityError("Choisis un processus disponible.")
        self.ensure_agents(username)
        from .candidate_profiles import clean_catalog
        profile_id = next(iter(clean_catalog(state_store.load_user_data(username, "profiles"))), "")
        if template == "careers_outreach" and not profile_id:
            raise CityError("Crée ton profil avant de préparer des brouillons.")
        now, workflow_id = _utc(), uuid.uuid4().hex
        task_ids = [uuid.uuid4().hex for _ in plans[template]]
        status = "queued" if self.get_settings(username)["auto_tasks"] else "waiting_approval"
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            # Repeated requests must not create another paid workflow or conflict with themselves.
            existing = db.execute("SELECT id,status FROM city_workflows WHERE username=? AND template=? "
                                  "AND request=? AND status IN ('queued','running','waiting_approval') "
                                  "ORDER BY created_at DESC", (username, template, request.strip())).fetchall()
            for prior in existing:
                steps = db.execute("SELECT id,agent_id,parameters_json FROM city_tasks WHERE username=? AND workflow_id=?",
                                   (username, prior["id"])).fetchall()
                payloads = [json.loads(step["parameters_json"] or "{}") for step in steps]
                if (steps and all(p.get("query", focus) == focus for p in payloads)
                        and all(p.get("profile_id", profile_id) == profile_id for p in payloads)):
                    return {"id": prior["id"], "template": template, "status": prior["status"],
                            "task_ids": [step["id"] for step in steps], "reused": True}
            active = db.execute("SELECT COUNT(*) FROM city_workflows WHERE username=? AND status IN "
                                "('queued','running','waiting_approval')", (username,)).fetchone()[0]
            if active >= 2:
                raise CityError("Deux projets sont déjà actifs sur ce compte.")
            db.execute("INSERT INTO city_workflows(id,username,template,request,status,priority,created_at,updated_at) "
                       "VALUES(?,?,?,?,?,?,?,?)", (workflow_id, username, template, request.strip(), status,
                                                   priority, now, now))
            for index, (agent_id, description, parameters, dependencies) in enumerate(plans[template]):
                payload = dict(parameters)
                if agent_id == "outreach_agent":
                    payload.update(profile_id=profile_id, language="Français")
                if db.execute("SELECT 1 FROM city_tasks WHERE username=? AND agent_id=? AND status IN "
                              "('queued','running','waiting_approval') LIMIT 1", (username, agent_id)).fetchone():
                    raise CityError(f"{AGENT_BY_ID[agent_id]['name']} a déjà une mission active.")
                task = {"id": task_ids[index], "username": username, "agent_id": agent_id}
                try:
                    db.execute("INSERT INTO city_tasks(id,username,agent_id,task_type,description,status,created_at,"
                               "parameters_json,workflow_id,depends_on_json,priority,max_retries) "
                               "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                               (task["id"], username, agent_id, f"agent:{agent_id}", description, status, now,
                                json.dumps(payload, ensure_ascii=False), workflow_id,
                                json.dumps([task_ids[i] for i in dependencies]), priority, 2))
                except sqlite3.IntegrityError as exc:
                    raise CityError(f"{AGENT_BY_ID[agent_id]['name']} a déjà une mission active.") from exc
                self._event(db, task, status, f"Projet : {description}")
        return {"id": workflow_id, "template": template, "status": status, "task_ids": task_ids, "reused": False}

    def workflow_details(self, username: str, workflow_id: str) -> dict:
        """Fetch even older projects by their persistent ID, always scoped to their owner."""
        with self.db() as db:
            row = db.execute("SELECT id,template,request,status,created_at,updated_at FROM city_workflows "
                             "WHERE username=? AND id=?", (username, workflow_id)).fetchone()
            if row is None:
                raise CityError("Projet introuvable sur ton compte.")
            steps = [dict(step) for step in db.execute(
                "SELECT id,agent_id,description,status,error,result_json,depends_on_json FROM city_tasks "
                "WHERE username=? AND workflow_id=? ORDER BY created_at,id", (username, workflow_id))]
        for step in steps:
            step["depends_on"] = json.loads(step.pop("depends_on_json") or "[]")
            raw = step.pop("result_json") or "{}"
            parsed = json.loads(raw)
            step["result"] = parsed if len(raw) <= 1600 else {
                **{key: parsed[key] for key in ('title', 'text', 'source', 'as_of', 'metrics', 'proposal', 'ideas', 'blockage', 'approval_required') if key in parsed},
                "truncated": True}
        return {**dict(row), "steps": steps, "completed_steps": sum(s["status"] == "completed" for s in steps),
                "total_steps": len(steps)}

    @staticmethod
    def _normalize_workflow_steps(steps: object) -> list[dict]:
        if not isinstance(steps, list) or not 1 <= len(steps) <= 7:
            raise CityError("Un workflow doit contenir entre 1 et 7 étapes spécialisées.")
        normalized: list[dict] = []
        seen: set[str] = set()
        seen_agents: set[str] = set()
        for index, supplied in enumerate(steps):
            if not isinstance(supplied, dict):
                raise CityError("Une étape du workflow est invalide.")
            node_id = str(supplied.get("id") or uuid.uuid4().hex[:12]).strip()
            agent_id = str(supplied.get("agent_id") or "").strip()
            description = str(supplied.get("description") or "").strip()
            dependencies = supplied.get("depends_on", [])
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", node_id) or node_id in seen:
                raise CityError("Identifiant d'étape invalide ou répété.")
            if agent_id not in AGENT_BY_ID or agent_id == "desk_manager":
                raise CityError("Choisis un agent spécialisé pour chaque étape.")
            if agent_id in seen_agents:
                raise CityError("Chaque agent ne peut apparaître qu'une fois dans un même workflow.")
            if not AGENT_BY_ID[agent_id]["available"]:
                raise CityError("Un agent sélectionné n'a pas de processus connecté.")
            if not description or len(description) > 240:
                raise CityError("Chaque consigne doit contenir de 1 à 240 caractères.")
            if not isinstance(dependencies, list) or len(dependencies) > 6:
                raise CityError("Dépendances d'étape invalides.")
            prior_ids = {item["id"] for item in normalized}
            deps = list(dict.fromkeys(str(item) for item in dependencies))
            if any(item not in prior_ids for item in deps):
                raise CityError("Chaque dépendance doit pointer vers une étape précédente.")
            from .city_specialists import validate_mission
            params = validate_mission(agent_id, {"operation": supplied.get("operation", "")}, description)
            normalized.append({"operation": params.get("operation", ""), "id": node_id, "agent_id": agent_id,
                               "description": description, "depends_on": deps})
            seen.add(node_id)
            seen_agents.add(agent_id)
        return normalized

    def save_workflow_definition(self, username: str, name: str, steps: object,
                                 definition_id: str = "") -> dict:
        name = str(name or "").strip()
        if not username or len(username) > 128 or not name or len(name) > 80:
            raise CityError("Donne un nom de 1 à 80 caractères au workflow.")
        normalized = self._normalize_workflow_steps(steps)
        now = _utc()
        definition_id = definition_id if re.fullmatch(r"[A-Za-z0-9_-]{1,40}", definition_id or "") else uuid.uuid4().hex
        with self.db() as db:
            existing = db.execute("SELECT username,created_at FROM city_workflow_definitions WHERE id=?",
                                  (definition_id,)).fetchone()
            if existing and existing["username"] != username:
                raise CityError("Identifiant de workflow invalide.")
            if not existing:
                saved_count = db.execute("SELECT COUNT(*) FROM city_workflow_definitions WHERE username=?",
                                         (username,)).fetchone()[0]
                if saved_count >= 50:
                    raise CityError("Limite de 50 workflows enregistrés atteinte.")
            created = existing["created_at"] if existing else now
            db.execute("INSERT INTO city_workflow_definitions(id,username,name,steps_json,created_at,updated_at) "
                       "VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,"
                       "steps_json=excluded.steps_json,updated_at=excluded.updated_at WHERE username=excluded.username",
                       (definition_id, username, name, json.dumps(normalized, ensure_ascii=False), created, now))
            db.execute('UPDATE city_workflow_definitions SET role_version=2 WHERE id=? AND username=?', (definition_id, username))
        return {"id": definition_id, "name": name, "steps": normalized,
                "created_at": created, "updated_at": now}

    def workflow_definitions(self, username: str) -> list[dict]:
        with self.db() as db:
            rows = db.execute("SELECT id,name,steps_json,created_at,updated_at FROM city_workflow_definitions "
                              "WHERE username=? AND role_version=2 ORDER BY updated_at DESC LIMIT 30", (username,)).fetchall()
        return [{"id": row[0], "name": row[1], "steps": json.loads(row[2]),
                 "created_at": row[3], "updated_at": row[4]} for row in rows]

    def run_workflow_definition(self, username: str, definition_id: str,
                                request: str = "", priority: int = 1) -> dict:
        with self.db() as db:
            row = db.execute("SELECT id,name,steps_json FROM city_workflow_definitions WHERE id=? AND username=? AND role_version=2",
                             (definition_id, username)).fetchone()
        if not row:
            raise CityError("Workflow enregistré introuvable sur ce compte.")
        goal = str(request or row[1]).strip()
        if not goal or len(goal) > 500 or priority not in (0, 1, 2):
            raise CityError("Objectif ou priorité invalide.")
        return self.create_custom_workflow(username, row[1], goal, json.loads(row[2]), priority)

    def create_custom_workflow(self, username: str, name: str, request: str,
                               steps: object, priority: int = 1) -> dict:
        if not username or len(username) > 128 or not isinstance(request, str) or not request.strip() or len(request) > 500:
            raise CityError("Décris le projet en 500 caractères maximum.")
        if priority not in (0, 1, 2):
            raise CityError("Priorité invalide.")
        normalized = self._normalize_workflow_steps(steps)
        self.ensure_agents(username)
        profile_id = ""
        if any(step["agent_id"] == "outreach_agent" for step in normalized):
            from .candidate_profiles import clean_catalog
            profile_id = next(iter(clean_catalog(state_store.load_user_data(username, "profiles"))), "")
            if not profile_id:
                raise CityError("Crée ton profil avant d'ajouter Iris à ce workflow.")
        now, workflow_id = _utc(), uuid.uuid4().hex
        task_ids = {step["id"]: uuid.uuid4().hex for step in normalized}
        status = "queued" if self.get_settings(username)["auto_tasks"] else "waiting_approval"
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            active = db.execute("SELECT COUNT(*) FROM city_workflows WHERE username=? AND status IN "
                                "('queued','running','waiting_approval')", (username,)).fetchone()[0]
            if active >= 2:
                raise CityError("Deux projets sont déjà actifs sur ce compte.")
            db.execute("INSERT INTO city_workflows(id,username,template,request,status,priority,created_at,updated_at) "
                       "VALUES(?,?,?,?,?,?,?,?)", (workflow_id, username, "custom", request.strip(), status,
                                                   priority, now, now))
            for step in normalized:
                agent_id = step["agent_id"]
                if db.execute("SELECT 1 FROM city_tasks WHERE username=? AND agent_id=? AND status IN "
                              "('queued','running','waiting_approval') LIMIT 1", (username, agent_id)).fetchone():
                    raise CityError(f"{AGENT_BY_ID[agent_id]['name']} a déjà une mission active.")
                step_query = request if agent_id == "job_hunter" else f"{request} {step['description']}"
                parameters = {"query": step_query[:160], "memory_query": request[:160],
                              "instruction": step["description"]}
                from .city_specialists import SPECIALISTS, VERSION
                if agent_id in SPECIALISTS:
                    parameters.update(operation=step['operation'], role_version=VERSION)
                if agent_id == "outreach_agent":
                    parameters.update(profile_id=profile_id, language="Français")
                dependency_ids = [task_ids[item] for item in step["depends_on"]]
                task = {"id": task_ids[step["id"]], "username": username, "agent_id": agent_id}
                try:
                    db.execute("INSERT INTO city_tasks(id,username,agent_id,task_type,description,status,created_at,"
                               "parameters_json,workflow_id,depends_on_json,priority,max_retries) "
                               "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                               (task["id"], username, agent_id, f"agent:{agent_id}", step["description"], status, now,
                                json.dumps(parameters, ensure_ascii=False), workflow_id,
                                json.dumps(dependency_ids), priority, 2))
                except sqlite3.IntegrityError as exc:
                    raise CityError(f"{AGENT_BY_ID[agent_id]['name']} a déjà une mission active.") from exc
                self._event(db, task, status, f"Workflow « {name[:80]} » : {step['description']}")
        return {"id": workflow_id, "template": "custom", "request": request.strip(),
                "status": status, "task_ids": list(task_ids.values())}

    @staticmethod
    def _upsert_memory(db, username: str, agent_id: str, kind: str, subject_key: str,
                       title: str, content: str, metadata: dict | None = None) -> str:
        memory_id = uuid.uuid4().hex
        now = _utc()
        packed = json.dumps(metadata or {}, ensure_ascii=False, default=str)
        if len(packed) > 6000:
            packed = json.dumps({"truncated": True}, ensure_ascii=False)
        content = str(content or "").strip()[:5000]
        title = str(title or kind).strip()[:160]
        subject_key = str(subject_key or hashlib.sha256((title + content).encode()).hexdigest()).strip()[:300]
        db.execute("INSERT INTO city_memory(id,username,agent_id,kind,subject_key,title,content,metadata_json,created_at,updated_at) "
                   "VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(username,agent_id,kind,subject_key) DO UPDATE SET "
                   "title=excluded.title,content=excluded.content,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at",
                   (memory_id, username, agent_id, kind, subject_key, title, content, packed, now, now))
        row = db.execute("SELECT id FROM city_memory WHERE username=? AND agent_id=? AND kind=? AND subject_key=?",
                         (username, agent_id, kind, subject_key)).fetchone()
        return row[0] if row else memory_id

    def record_memory(self, username: str, title: str, content: str, kind: str = "preference",
                      agent_id: str = "desk_manager", subject_key: str = "", metadata: dict | None = None) -> dict:
        if agent_id not in AGENT_BY_ID:
            raise CityError("Agent mémoire inconnu.")
        if kind not in {"preference", "decision", "note"}:
            raise CityError("Seules les préférences, décisions et notes manuelles peuvent être ajoutées ici.")
        title, content = str(title or "").strip(), str(content or "").strip()
        if not title or len(title) > 120 or not content or len(content) > 1000:
            raise CityError("Renseigne un titre et un contenu de 1 000 caractères maximum.")
        subject_key = subject_key or hashlib.sha256((kind + ":" + title.casefold()).encode()).hexdigest()
        with self.db() as db:
            memory_id = self._upsert_memory(db, username, agent_id, kind, subject_key, title, content, metadata)
        return {"id": memory_id, "kind": kind, "agent_id": agent_id, "title": title, "content": content}

    def get_memory(self, username: str, agent_id: str, kind: str, subject_key: str) -> dict | None:
        with self.db() as db:
            row = db.execute("SELECT * FROM city_memory WHERE username=? AND agent_id=? AND kind=? AND subject_key=?",
                             (username, agent_id, kind, subject_key)).fetchone()
        if not row:
            return None
        return {"id": row["id"], "title": row["title"], "content": row["content"],
                "metadata": json.loads(row["metadata_json"] or "{}"), "updated_at": row["updated_at"]}

    def search_memory(self, username: str, query: str = "", agent_id: str = "", limit: int = 8) -> list[dict]:
        if agent_id and agent_id not in AGENT_BY_ID:
            raise CityError("Agent mémoire inconnu.")
        query = str(query or "").strip()[:240]
        if not isinstance(limit, int):
            limit = 8
        limit = max(1, min(20, limit))
        with self.db() as db:
            rows = [dict(row) for row in db.execute(
                "SELECT id,agent_id,kind,title,content,metadata_json,created_at,updated_at "
                "FROM city_memory WHERE username=? ORDER BY updated_at DESC LIMIT 1200", (username,))]
        query_tokens = _memory_tokens(query)
        expanded = set(query_tokens)
        for token in query_tokens:
            expanded.update(_MEMORY_SYNONYMS.get(token, ()))
        scored = []
        for row in rows:
            metadata = json.loads(row["metadata_json"] or "{}")
            if agent_id and row["kind"] == "outreach_draft" and agent_id != "outreach_agent":
                continue
            tags = metadata.get("tags", []) if isinstance(metadata, dict) else []
            title_tokens = _memory_tokens(row["title"] + " " + " ".join(map(str, tags)))
            body_tokens = _memory_tokens(row["content"] + " " + json.dumps(metadata, ensure_ascii=False))
            counts = Counter(body_tokens)
            for token in title_tokens:
                counts[token] += 3
            if query_tokens:
                overlap = sum(min(3, counts[token]) for token in expanded)
                if not overlap:
                    continue
                length_norm = math.sqrt(max(1, len(body_tokens)))
                phrase_bonus = 2.0 if len(query) > 3 and query.casefold() in (row["title"] + " " + row["content"]).casefold() else 0.0
                score = overlap / length_norm + phrase_bonus + (0.8 if agent_id and row["agent_id"] == agent_id else 0)
            else:
                score = 0.0
            scored.append((score, row, metadata))
        scored.sort(key=lambda item: (item[0], item[1]["updated_at"]), reverse=True)
        return [{"id": row["id"], "agent_id": row["agent_id"], "kind": row["kind"],
                 "title": row["title"], "content": row["content"][:2200], "metadata": metadata,
                 "created_at": row["created_at"], "updated_at": row["updated_at"], "score": round(score, 3)}
                for score, row, metadata in scored[:limit]]

    def shared_results(self, username: str, agent_id: str = "", limit: int = 6) -> list[dict]:
        if agent_id and agent_id not in AGENT_BY_ID:
            raise CityError("Agent inconnu.")
        with self.db() as db:
            rows = db.execute("SELECT agent_id,result_json,updated_at FROM city_shared_results "
                              "WHERE username=? AND (?='' OR agent_id=?) ORDER BY updated_at DESC LIMIT ?",
                              (username, agent_id, agent_id, max(1, min(12, limit)))).fetchall()
        return [{"agent_id": row[0], "result": json.loads(row[1]), "updated_at": row[2]} for row in rows]

    @staticmethod
    def _cache_key(agent_id: str, parameters_json: str) -> str:
        return hashlib.sha256(f"{agent_id}:{parameters_json}".encode("utf-8")).hexdigest()

    def cached_result(self, username: str, agent_id: str, parameters_json: str, minutes: int = 10) -> dict | None:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec="seconds")
        with self.db() as db:
            row = db.execute("SELECT result_json FROM city_shared_results WHERE username=? AND cache_key=? "
                             "AND updated_at>=?", (username, self._cache_key(agent_id, parameters_json), cutoff)).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def _refresh_workflow(db, workflow_id: str) -> None:
        if not workflow_id:
            return
        current = db.execute("SELECT status FROM city_workflows WHERE id=?", (workflow_id,)).fetchone()
        if current and current[0] == "cancelled":
            return
        rows = db.execute("SELECT id,agent_id,status,result_json,error FROM city_tasks WHERE workflow_id=? "
                          "ORDER BY rowid", (workflow_id,)).fetchall()
        statuses = {row["status"] for row in rows}
        if statuses <= {"completed", "failed", "cancelled"}:
            status = "completed" if statuses == {"completed"} else "failed"
        elif "running" in statuses:
            status = "running"
        elif "waiting_approval" in statuses:
            status = "waiting_approval"
        else:
            status = "queued"
        summary = [{"agent_id": row["agent_id"], "status": row["status"],
                    "result": json.loads(row["result_json"] or "{}"), "error": row["error"]} for row in rows]
        db.execute("UPDATE city_workflows SET status=?,updated_at=?,result_json=? WHERE id=?",
                   (status, _utc(), json.dumps(summary, ensure_ascii=False) if status in FINAL else None, workflow_id))

    def claim_next(self) -> dict | None:
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT * FROM city_tasks WHERE status='queued' "
                              "AND (scheduled_at IS NULL OR scheduled_at<=?) "
                              "ORDER BY priority DESC,COALESCE(scheduled_at,created_at),created_at,id",
                              (_utc(),)).fetchall()
            task = None
            for row in rows:
                from .city_specialists import SPECIALISTS, VERSION, validate_mission
                try:
                    params = json.loads(row['parameters_json'] or '{}')
                    if row['agent_id'] in SPECIALISTS and params.get('role_version') != VERSION:
                        raise CityError("Ancienne spécialisation : relance depuis le Desk Manager.")
                    validate_mission(row['agent_id'], params)
                except CityError as exc:
                    db.execute("UPDATE city_tasks SET status='cancelled',finished_at=?,error=? WHERE id=?", (_utc(), str(exc), row['id']))
                    self._event(db, row, 'cancelled', str(exc))
                    self._refresh_workflow(db, row['workflow_id'])
                    continue
                dependencies = json.loads(row["depends_on_json"] or "[]")
                if dependencies:
                    marks = ",".join("?" for _ in dependencies)
                    predecessors = db.execute(f"SELECT id,status FROM city_tasks WHERE username=? AND id IN ({marks})",
                                              (row["username"], *dependencies)).fetchall()
                    states = {item["id"]: item["status"] for item in predecessors}
                    if any(states.get(item) in (None, "failed", "cancelled") for item in dependencies):
                        db.execute("UPDATE city_tasks SET status='cancelled',finished_at=?,error=? WHERE id=?",
                                   (_utc(), "Dépendance indisponible.", row["id"]))
                        self._event(db, row, "cancelled", "Mission arrêtée : dépendance indisponible.")
                        self._refresh_workflow(db, row["workflow_id"])
                        continue
                    if any(states[item] != "completed" for item in dependencies):
                        continue
                running = db.execute("SELECT COUNT(*) FROM city_tasks WHERE username=? AND status='running'",
                                     (row["username"],)).fetchone()[0]
                saved = db.execute("SELECT settings_json FROM city_settings WHERE username=?",
                                   (row["username"],)).fetchone()
                concurrency = json.loads(saved[0]).get("max_concurrent_tasks", 2) if saved else 2
                if running >= concurrency:
                    continue
                if params.get('operation') == 'develop':
                    active_code = db.execute("SELECT COUNT(*) FROM city_tasks WHERE status='running' "
                                             "AND json_extract(parameters_json,'$.operation')='develop'").fetchone()[0]
                    same_agent = db.execute("SELECT 1 FROM city_tasks WHERE username=? AND agent_id=? AND status='running' LIMIT 1",
                                            (row['username'], row['agent_id'])).fetchone()
                    if active_code >= 4 or same_agent:
                        continue
                task = dict(row)
                break
            if task is None:
                return None
            now = _utc()
            db.execute("UPDATE city_tasks SET status='running',started_at=?,heartbeat_at=? "
                       "WHERE id=? AND status='queued'", (now, now, task["id"]))
            self._event(db, task, "running", "Collecte des sources démarrée.")
            self._refresh_workflow(db, task.get("workflow_id"))
            task.update(status="running", started_at=now, heartbeat_at=now)
            return task

    def heartbeat(self, task_id: str) -> None:
        with self.db() as db:
            db.execute("UPDATE city_tasks SET heartbeat_at=? WHERE id=? AND status='running'",
                       (_utc(), task_id))

    def progress(self, task_id: str, message: str) -> None:
        with self.db() as db:
            task = db.execute("SELECT id,username,agent_id FROM city_tasks WHERE id=? AND status='running'",
                              (task_id,)).fetchone()
            if task:
                db.execute("UPDATE city_tasks SET heartbeat_at=? WHERE id=?", (_utc(), task_id))
                self._event(db, task, 'running', message)

    def defer_coding(self, task_id: str, reason: str, *, delay_minutes: int = 60) -> None:
        next_try = (datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)).isoformat(timespec='seconds')
        with self.db() as db:
            task = db.execute("SELECT * FROM city_tasks WHERE id=? AND status='running'", (task_id,)).fetchone()
            if not task:
                return
            db.execute("UPDATE city_tasks SET status='queued',scheduled_at=?,started_at=NULL,heartbeat_at=NULL "
                       "WHERE id=?", (next_try, task_id))
            self._event(db, task, 'queued', reason + f' Nouvelle tentative dans {delay_minutes} minutes.')

    @classmethod
    def _remember_task_result(cls, db, task: dict, result: dict) -> None:
        agent_id, username = task["agent_id"], task["username"]
        parameters = json.loads(task.get("parameters_json") or "{}")
        if agent_id == "desk_manager":
            offers = list(result.get("offers") or [])
            featured = result.get("featured_offer")
            if isinstance(featured, dict):
                offers.insert(0, featured)
            seen: set[str] = set()
            for offer in offers[:40]:
                if not isinstance(offer, dict):
                    continue
                url = str(offer.get("url") or "").strip()
                title = str(offer.get("title") or "").strip()
                company = str(offer.get("company") or "").strip()
                if not title or not (url.startswith("https://") or company):
                    continue
                key = _canonical_memory_url(url) or hashlib.sha256(f"{title}|{company}".casefold().encode()).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                fields = {name: str(offer.get(name) or "")[:240] for name in
                          ("location", "kind", "start_period", "published", "source", "selection_reason")}
                content = " · ".join(value for value in (title, company, fields["location"],
                                                          fields["kind"], fields["start_period"]) if value)
                cls._upsert_memory(db, username, agent_id, "offer", key, title, content,
                                   {"url": url, **fields, "tags": ["offre", "finance de marché"]})
        elif agent_id in {"networker", "securities_scout"}:
            for contact in (result.get("contacts") or [])[:40]:
                if not isinstance(contact, dict):
                    continue
                name = str(contact.get("name") or "").strip()
                company = str(contact.get("company") or "").strip()
                if not name and not company:
                    continue
                url = str(contact.get("linkedin_url") or "").strip()
                key = _canonical_memory_url(url) or str(contact.get("id") or hashlib.sha256(
                    f"{name}|{company}".casefold().encode()).hexdigest())
                role = str(contact.get("role") or "")[:240]
                location = str(contact.get("location") or "")[:160]
                content = " · ".join(value for value in (name, role, company, location) if value)
                cls._upsert_memory(db, username, agent_id, "contact", key,
                                   name or company, content,
                                   {"linkedin_url": url, "role": role, "company": company, "location": location,
                                    "verification": str(contact.get("verification") or "À vérifier")[:80],
                                    "tags": ["contact", "réseau professionnel"]})
        elif agent_id == "outreach_agent":
            contact_id = str(parameters.get("contact_id") or "")
            if not contact_id:
                dependencies = json.loads(task.get("depends_on_json") or "[]")
                if dependencies:
                    rows = db.execute("SELECT agent_id,result_json FROM city_tasks WHERE username=? AND id IN (" +
                                      ",".join("?" for _ in dependencies) + ")",
                                      (username, *dependencies)).fetchall()
                    contacts = next((json.loads(row["result_json"] or "{}").get("contacts", []) for row in rows
                                     if row["agent_id"] == "networker"), [])
                    contact_id = str(contacts[0].get("id") or "") if contacts else ""
            contact = result.get("contact") if isinstance(result.get("contact"), dict) else {}
            body, subject = str(result.get("body") or "").strip(), str(result.get("subject") or "").strip()
            profile_id = str(parameters.get("profile_id") or "")
            language = str(parameters.get("language") or "Français")
            if contact_id and profile_id and body:
                key = f"{profile_id}:{contact_id}:{language.casefold()}"
                cls._upsert_memory(db, username, agent_id, "outreach_draft", key,
                                   f"Brouillon · {contact.get('name') or 'contact'}",
                                   (subject + "\n" + body)[:5000],
                                   {"contact_id": contact_id, "profile_id": profile_id, "language": language,
                                    "subject": subject[:500], "body": body[:4200],
                                    "followup": str(result.get("followup") or "")[:1500],
                                    "contact_name": str(contact.get("name") or "")[:160],
                                    "contact_company": str(contact.get("company") or "")[:160],
                                    "tags": ["brouillon", "prise de contact"]})
        else:
            title = str(result.get("title") or result.get("text") or "Résultat de mission").strip()[:150]
            content = str(result.get("text") or result.get("summary") or "").strip()
            if not content and (result.get("question") or result.get("answer")):
                content = "\n".join(value for value in (
                    str(result.get("question") or "").strip(),
                    str(result.get("answer") or "").strip(),
                    str(result.get("note") or "").strip()) if value)
            if title and content:
                kind = {"market_analyst": "market_brief", "finance_tutor": "quant_research", "job_hunter": "code_review",
                        "developer": "interview", "innovation_lab": "innovation"}.get(agent_id, "result")
                key = cls._cache_key(agent_id, task.get("parameters_json") or "{}")
                cls._upsert_memory(db, username, agent_id, kind, key, title, content[:3500],
                                   {"source": str(result.get("source") or "")[:180],
                                    "as_of": str(result.get("as_of") or "")[:80],
                                    "tags": [kind, agent_id]})

    @classmethod
    def _record_decision(cls, db, username: str, agent_id: str, key: str,
                         title: str, content: str, metadata: dict | None = None) -> None:
        cls._upsert_memory(db, username, agent_id, "decision", key, title, content, metadata)

    def finish(self, task_id: str, *, result: dict | None = None, error: str = "",
               usage: dict | None = None) -> None:
        status = "failed" if error else "completed"
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM city_tasks WHERE id=? AND status='running'", (task_id,)).fetchone()
            if row is None:
                return
            task = dict(row)
            catch_up = json.loads(task['parameters_json'] or '{}').get('catch_up')
            if catch_up and not error:
                result = dict(result or {})
                result['catch_up'] = catch_up
                result['text'] = (f"Rattrapage regroupé : {catch_up['periods']} périodes du {catch_up['from']} au {catch_up['to']}. "
                                  "Une seule actualisation exécutée maintenant ; les états historiques manqués ne sont pas reconstitués.\n\n"
                                  + str(result.get('text') or result.get('title') or 'Résultat disponible.'))
            new_count = max(0, int((result or {}).get("new_count", 0))) if not error else 0
            awarded = 0
            if not error:
                for offer_url in dict.fromkeys((result or {}).get("new_urls") or []):
                    if not isinstance(offer_url, str) or not offer_url.startswith("https://"):
                        continue
                    inserted = db.execute("INSERT OR IGNORE INTO city_awarded_offers(username,offer_url,task_id) "
                                          "VALUES(?,?,?)", (task["username"], offer_url, task_id))
                    awarded += inserted.rowcount
            xp = (min(awarded, new_count, 20) * 10 if task["agent_id"] == "job_hunter"
                  else max(0, min(50, int((result or {}).get("xp_award", 0)))) if not error else 0)
            db.execute("UPDATE city_tasks SET status=?,finished_at=?,result_json=?,error=?,xp_awarded=?,"
                       "input_tokens=?,output_tokens=?,api_cost_usd=? WHERE id=?",
                       (status, _utc(), json.dumps(result or {}, ensure_ascii=False) if not error else None,
                        error[:500] if error else None, xp, int((usage or {}).get("input_tokens", 0)),
                        int((usage or {}).get("output_tokens", 0)), float((usage or {}).get("cost", 0)), task_id))
            if xp:
                db.execute("UPDATE city_agents SET xp=xp+? WHERE username=? AND agent_id=?",
                           (xp, task["username"], task["agent_id"]))
            if error:
                message = "Mission échouée : " + error[:250]
            else:
                summary = str((result or {}).get("text") or (result or {}).get("title") or "Résultat disponible.")
                message = summary[:250]
            self._event(db, task, status, message)
            if not error and task["agent_id"] in {"job_hunter", "networker", "securities_scout", "market_analyst", "finance_tutor", "developer", "innovation_lab", "internship_scout"}:
                compact = json.dumps(result or {}, ensure_ascii=False)
                if len(compact) <= 24000:
                    db.execute("INSERT INTO city_shared_results(username,cache_key,agent_id,result_json,updated_at) "
                               "VALUES(?,?,?,?,?) ON CONFLICT(username,cache_key) DO UPDATE SET "
                               "result_json=excluded.result_json,updated_at=excluded.updated_at",
                               (task["username"], self._cache_key(task["agent_id"], task["parameters_json"]),
                                task["agent_id"], compact, _utc()))
            if not error:
                self._remember_task_result(db, task, result or {})
            self._refresh_workflow(db, task.get("workflow_id"))

    def approve_task(self, username: str, task_id: str) -> bool:
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM city_tasks WHERE id=? AND username=? AND status='waiting_approval'",
                             (task_id, username)).fetchone()
            if row is None:
                return False
            db.execute("UPDATE city_tasks SET status='queued' WHERE id=?", (task_id,))
            self._event(db, row, "queued", "Mission approved and added to the queue.")
            self._record_decision(db, username, row["agent_id"], f"task:{task_id}:approved",
                                  "Mission approuvée", row["description"], {"task_id": task_id})
            return True

    def approve_workflow(self, username: str, workflow_id: str) -> bool:
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id,request FROM city_workflows WHERE id=? AND username=? AND status='waiting_approval'",
                             (workflow_id, username)).fetchone()
            if not row:
                return False
            db.execute("UPDATE city_tasks SET status='queued' WHERE workflow_id=? AND status='waiting_approval'",
                       (workflow_id,))
            self._refresh_workflow(db, workflow_id)
            self._record_decision(db, username, "desk_manager", f"workflow:{workflow_id}:approved",
                                  "Workflow approuvé", row["request"], {"workflow_id": workflow_id})
            return True

    def cancel_workflow(self, username: str, workflow_id: str) -> bool:
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            workflow = db.execute("SELECT id,request FROM city_workflows WHERE id=? AND username=? AND status IN "
                                  "('queued','running','waiting_approval')", (workflow_id, username)).fetchone()
            if not workflow:
                return False
            rows = db.execute("SELECT * FROM city_tasks WHERE workflow_id=? AND status IN ('queued','waiting_approval')",
                              (workflow_id,)).fetchall()
            for row in rows:
                db.execute("UPDATE city_tasks SET status='cancelled',finished_at=? WHERE id=?", (_utc(), row["id"]))
                self._event(db, row, "cancelled", "Projet annulé avant cette étape.")
            db.execute("UPDATE city_workflows SET status='cancelled',updated_at=? WHERE id=?",
                       (_utc(), workflow_id))
            self._record_decision(db, username, "desk_manager", f"workflow:{workflow_id}:cancelled",
                                  "Workflow annulé", workflow["request"], {"workflow_id": workflow_id})
            return True

    def retry_task(self, username: str, task_id: str) -> dict:
        with self.db() as db:
            row = db.execute("SELECT * FROM city_tasks WHERE id=? AND username=? AND status='failed'",
                             (task_id, username)).fetchone()
        if row is None:
            raise CityError("This mission is not available for retry.")
        parameters = json.loads(row['parameters_json'] or '{}')
        if parameters.get('operation') == 'develop' and row['workflow_id'] is None:
            settings = self.get_settings(username)
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute("SELECT 1 FROM city_tasks WHERE username=? AND agent_id=? AND status='running' LIMIT 1",
                              (username, row['agent_id'])).fetchone():
                    raise CityError('Cet agent a déjà une mission en cours.')
                if db.execute("SELECT COUNT(*) FROM city_tasks WHERE username=? AND status IN ('queued','running','waiting_approval')",
                              (username,)).fetchone()[0] >= settings['max_concurrent_tasks']:
                    raise CityError('Termine ou annule une mission avant de la relancer.')
                changed = db.execute("UPDATE city_tasks SET status='queued',scheduled_at=NULL,error=NULL,started_at=NULL,"
                                     "finished_at=NULL,heartbeat_at=NULL,retry_count=retry_count+1 "
                                     "WHERE id=? AND username=? AND status='failed'", (task_id, username)).rowcount
                if not changed:
                    raise CityError('Cette mission a déjà été relancée.')
                self._event(db, row, 'queued', 'Nouvelle tentative sur la même branche de travail.')
            return {'id': task_id, 'status': 'queued'}
        if row['agent_id']=='job_hunter' and parameters.get('operation')=='prepare_branch':
            # The human approval is bound to this task ID. Creating another ID loses it.
            settings = self.get_settings(username)
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='city_proposal_reviews'").fetchone():
                    raise CityError('La préparation de branche nécessite une proposition explicitement validée sur ton compte.')
                approval = db.execute('SELECT 1 FROM city_proposal_reviews WHERE task_id=? AND username=? AND next_task_id=? AND approved=1',
                                      (parameters.get('source_task_id'),username,task_id)).fetchone()
                if not approval:
                    raise CityError('La préparation de branche nécessite une proposition explicitement validée sur ton compte.')
                if db.execute("SELECT 1 FROM city_tasks WHERE username=? AND agent_id='job_hunter' AND status IN ('queued','running','waiting_approval')",(username,)).fetchone():
                    raise CityError('Jules a déjà une mission active.')
                if db.execute("SELECT COUNT(*) FROM city_tasks WHERE username=? AND status IN ('queued','running','waiting_approval')",(username,)).fetchone()[0]>=settings['max_concurrent_tasks']:
                    raise CityError('Termine ou annule une mission avant de relancer Jules.')
                changed = db.execute("UPDATE city_tasks SET status='queued',error=NULL,started_at=NULL,finished_at=NULL,heartbeat_at=NULL,retry_count=retry_count+1 WHERE id=? AND username=? AND status='failed'",
                                     (task_id,username)).rowcount
                if not changed:
                    raise CityError('Cette mission a déjà été relancée.')
                self._event(db,row,'queued','Nouvelle tentative sur la version validée ; validation humaine conservée.')
            return {'id':task_id,'status':'queued','reused_approval':True}
        if row["workflow_id"]:
            with self.db() as db:
                workflow = db.execute("SELECT status FROM city_workflows WHERE id=? AND username=?",
                                      (row["workflow_id"], username)).fetchone()
            if workflow is None or workflow["status"] == "cancelled":
                raise CityError("Ce projet a été annulé. Lance un nouveau projet pour recommencer.")
            if row["retry_count"] >= row["max_retries"]:
                raise CityError("Le nombre maximal de tentatives est atteint.")
            with self.db() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("UPDATE city_tasks SET status='queued',error=NULL,started_at=NULL,finished_at=NULL,"
                           "retry_count=retry_count+1 WHERE id=? AND username=? AND status='failed'",
                           (task_id, username))
                db.execute("UPDATE city_workflows SET status='queued',updated_at=?,result_json=NULL "
                           "WHERE id=? AND username=?", (_utc(), row["workflow_id"], username))
                db.execute("UPDATE city_tasks SET status='queued',error=NULL,finished_at=NULL "
                           "WHERE workflow_id=? AND status='cancelled' AND error='Dépendance indisponible.'",
                           (row["workflow_id"],))
                self._event(db, row, "queued", "Nouvelle tentative demandée.")
            return {"id": task_id, "workflow_id": row["workflow_id"], "status": "queued"}
        parameters["retry_of"] = task_id
        return self.create_task(username, row["agent_id"], row["description"], parameters, None)

    def cancel_queued(self, username: str, task_id: str) -> bool:
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM city_tasks WHERE id=? AND username=? AND status IN ('queued','waiting_approval')",
                             (task_id, username)).fetchone()
            if row is None:
                return False
            db.execute("UPDATE city_tasks SET status='cancelled',finished_at=? WHERE id=?", (_utc(), task_id))
            self._event(db, row, "cancelled", "Mission retirée avant son démarrage.")
            self._record_decision(db, username, row["agent_id"], f"task:{task_id}:cancelled",
                                  "Mission annulée", row["description"], {"task_id": task_id})
            self._refresh_workflow(db, row["workflow_id"])
            return True

    def recover_stale(self, seconds: int = 90) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat(timespec="seconds")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT * FROM city_tasks WHERE status='running' AND heartbeat_at<?",
                              (cutoff,)).fetchall()
            for row in rows:
                parameters = json.loads(row['parameters_json'] or '{}')
                if parameters.get('operation') == 'develop' and re.fullmatch(r'[a-f0-9]{32}', row['id']):
                    from .city_specialists import repo_root
                    marker = repo_root() / '.city-worktrees' / row['id'] / '.jules-complete.json'
                    if marker.is_file():
                        db.execute("UPDATE city_tasks SET status='queued',scheduled_at=NULL,started_at=NULL,"
                                   "heartbeat_at=NULL,error=NULL,retry_count=retry_count+1 WHERE id=?", (row['id'],))
                        self._event(db, row, 'queued', 'Travail Codex terminé retrouvé ; intégration reprise sans nouvel appel.')
                        continue
                db.execute("UPDATE city_tasks SET status='failed',finished_at=?,error=? WHERE id=?",
                           (_utc(), "Exécution interrompue ; relance la mission si nécessaire.", row["id"]))
                self._event(db, row, "failed", "Exécution interrompue après une perte de contact avec le worker.")
                self._refresh_workflow(db, row["workflow_id"])
            return len(rows)

    def coding_history(self, username: str) -> dict:
        """Compact month-long coding feed; full diffs stay behind the task detail route."""
        since = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat(timespec='seconds')
        with self.db() as db:
            rows = db.execute(
                "SELECT id,agent_id,task_type,description,status,created_at,started_at,finished_at,"
                "result_json,error,retry_count,parameters_json FROM city_tasks WHERE username=? AND created_at>=? "
                "AND json_extract(parameters_json,'$.operation') IN ('develop','code_change','prepare_branch') "
                "ORDER BY created_at DESC,rowid DESC LIMIT 700", (username, since)).fetchall()
            ids = [row['id'] for row in rows]
            events = []
            if ids:
                marks = ','.join('?' for _ in ids)
                events = [dict(row) for row in db.execute(
                    f"SELECT id,agent_id,task_id,status,message,created_at FROM city_events "
                    f"WHERE username=? AND task_id IN ({marks}) ORDER BY id DESC LIMIT 1800", (username, *ids))]
        tasks = []
        for row in rows:
            result = json.loads(row['result_json'] or '{}')
            payload = json.loads(row['parameters_json'] or '{}')
            task = {key: row[key] for key in ('id','agent_id','task_type','description','status',
                    'created_at','started_at','finished_at','error','retry_count')}
            task['operation'] = payload.get('operation', '')
            task['period'] = payload.get('period', '')
            task['result'] = {key: result[key] for key in ('title','plain_summary','summary','files',
                              'integrated','already_present','commit','branch') if key in result}
            if result.get('integrated'):
                task['result']['live'] = (result.get('commit') in self.active_commits
                                          if self.active_revision else None)
            tasks.append(task)
        return {'tasks': tasks, 'events': events, 'active_revision': self.active_revision}

    def task_detail(self, username: str, task_id: str) -> dict | None:
        with self.db() as db:
            row = db.execute('SELECT * FROM city_tasks WHERE id=? AND username=?', (task_id, username)).fetchone()
        if row is None:
            return None
        task = dict(row)
        task['result'] = json.loads(task.pop('result_json') or '{}')
        payload = json.loads(task.pop('parameters_json') or '{}')
        task['operation'] = payload.get('operation', '')
        task.pop('username', None)
        task.pop('heartbeat_at', None)
        return task

    def snapshot(self, username: str) -> dict:
        self.ensure_agents(username)
        with self.db() as db:
            progress = {row["agent_id"]: row["xp"] for row in db.execute(
                "SELECT agent_id,xp FROM city_agents WHERE username=?", (username,))}
            tasks = [dict(row) for row in db.execute(
                "SELECT * FROM city_tasks WHERE username=? AND (id IN (SELECT id FROM city_tasks WHERE username=? ORDER BY created_at DESC,rowid DESC LIMIT 100) "
                "OR status IN ('queued','running','waiting_approval') OR (status='completed' AND agent_id IN ('job_hunter','innovation_lab') "
                "AND json_extract(COALESCE(result_json,'{}'),'$.role_version')=2 AND json_extract(COALESCE(result_json,'{}'),'$.approval_required')=1 "
                "AND COALESCE(json_extract(COALESCE(result_json,'{}'),'$.review_decision'),'')='' AND COALESCE(json_extract(COALESCE(result_json,'{}'),'$.branch'),'')='')) "
                "ORDER BY created_at DESC,rowid DESC", (username,username))]
            events = [dict(row) for row in db.execute(
                "SELECT id,agent_id,task_id,status,message,created_at FROM city_events "
                "WHERE username=? ORDER BY id DESC LIMIT 80", (username,))]
            workflows = [dict(row) for row in db.execute(
                "SELECT id,template,request,status,priority,created_at,updated_at,result_json "
                "FROM city_workflows WHERE username=? ORDER BY created_at DESC,id DESC LIMIT 20", (username,))]
            workflow_steps = [dict(row) for row in db.execute(
                "SELECT id,workflow_id,agent_id,description,status,error,priority,retry_count,max_retries,"
                "depends_on_json FROM city_tasks WHERE username=? AND workflow_id IS NOT NULL "
                "ORDER BY rowid", (username,))]
        for workflow in workflows:
            workflow["result"] = json.loads(workflow.pop("result_json") or "[]")
            workflow["steps"] = [{**step, "depends_on": json.loads(step["depends_on_json"])}
                                 for step in workflow_steps if step["workflow_id"] == workflow["id"]]
            for step in workflow["steps"]:
                step.pop("depends_on_json")
        for task in tasks:
            task["result"] = json.loads(task.pop("result_json") or "{}")
            task["result"].pop("new_urls", None)
            payload = json.loads(task.pop("parameters_json") or "{}")
            task["delegated_by"] = payload.get("delegated_by", "")
            task["role_version"] = payload.get("role_version", 1)
            task["operation"] = payload.get("operation", "")
            task["retry_of"] = payload.get("retry_of", "")
            task.pop("username", None)
            task.pop("heartbeat_at", None)
            task["depends_on"] = json.loads(task.pop("depends_on_json") or "[]")
        agents = []
        for agent in AGENTS:
            xp = progress.get(agent["id"], 0)
            from .city_specialists import SPECIALISTS, VERSION
            own = [task for task in tasks if task["agent_id"] == agent["id"] and
                   (agent["id"] not in SPECIALISTS or task['role_version'] == VERSION)]
            achievements = ((["Première découverte"] if xp >= 10 else [])
                            + (["10 offres inédites"] if xp >= 100 else [])
                            + (["50 offres inédites"] if xp >= 500 else [])) if agent["id"] == "job_hunter" else (
                                (["Première mission"] if xp >= 10 else [])
                                + (["10 missions terminées"] if xp >= 100 else [])
                                + (["50 missions terminées"] if xp >= 500 else []))
            manager_status = next((workflow["status"] for workflow in workflows
                                   if workflow["status"] in ACTIVE), "idle")
            agents.append({**agent, "xp": xp, "level": xp // 100 + 1,
                           "level_progress": xp % 100,
                           "achievements": achievements,
                           "status": manager_status if agent["id"] == "desk_manager" else
                           own[0]["status"] if own and own[0]["status"] in ACTIVE else "idle",
                           "latest": own[0] if own else None})
        from .state_store import load_user_data
        from .candidate_profiles import clean_catalog
        profiles = clean_catalog(load_user_data(username, "profiles"))
        contacts = load_user_data(username, "mail_contacts")
        usage = {"input_tokens": 0, "output_tokens": 0, "estimated_usd": 0.0,
                 "calls": 0, "unknown_costs": 0, "by_agent": {},
                 "note": "Coûts et jetons relevés par le journal IA de tous les modules pour ce compte."}
        try:
            from .llm_usage import _connect
            with _connect() as usage_db:
                row = usage_db.execute("SELECT COUNT(*),COALESCE(SUM(input_tokens),0),COALESCE(SUM(output_tokens),0),"
                                       "COALESCE(SUM(CASE WHEN estimated_cost_usd IS NULL THEN 1 ELSE 0 END),0) "
                                       "FROM llm_usage WHERE username=?", (username,)).fetchone()
                costs = usage_db.execute("SELECT estimated_cost_usd FROM llm_usage WHERE username=? "
                                         "AND estimated_cost_usd IS NOT NULL", (username,)).fetchall()
                agent_rows = usage_db.execute("SELECT action,estimated_cost_usd FROM llm_usage WHERE username=? "
                                              "AND action LIKE 'city_chat:%'", (username,)).fetchall()
            usage.update(calls=row[0], input_tokens=row[1], output_tokens=row[2], unknown_costs=row[3],
                         estimated_usd=round(sum(float(item[0]) for item in costs), 6))
            for action, cost in agent_rows:
                agent_id = action.removeprefix("city_chat:")
                entry = usage["by_agent"].setdefault(agent_id, {"calls": 0, "estimated_usd": 0.0, "unknown": 0})
                entry["calls"] += 1
                entry["estimated_usd"] += float(cost or 0)
                entry["unknown"] += cost is None
            with self.db() as db:
                task_costs = db.execute("SELECT agent_id,COUNT(*),COALESCE(SUM(api_cost_usd),0) "
                                        "FROM city_tasks WHERE username=? AND "
                                        "(input_tokens>0 OR output_tokens>0 OR api_cost_usd>0) "
                                        "GROUP BY agent_id", (username,)).fetchall()
            for agent_id, calls, cost in task_costs:
                entry = usage["by_agent"].setdefault(agent_id, {"calls": 0, "estimated_usd": 0.0, "unknown": 0})
                entry["calls"] += calls
                entry["estimated_usd"] += float(cost)
        except Exception:
            usage["note"] = "Le journal des coûts IA est temporairement indisponible."
        return {"agents": agents, "tasks": tasks, "events": events, "workflows": workflows,
                "workspace": {"profiles": [{"id": key, "name": item.get("name", "Profil")}
                                            for key, item in profiles.items()],
                              "contacts": [{"id": key, "name": item.get("name", "Contact à vérifier"),
                                            "company": item.get("company", "")}
                                           for key, item in contacts.items()]},
                "today_completed": sum(1 for task in tasks if task["status"] == "completed"
                                       and task["created_at"].startswith(datetime.now(timezone.utc).date().isoformat())),
                "week_completed": sum(1 for task in tasks if task["status"] == "completed"
                                      and task["created_at"] >= (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()),
                "api_usage": usage}

    def delete_account(self, username: str) -> None:
        with self.db() as db:
            for table in ("city_events", "city_awarded_offers", "city_tasks", "city_agents",
                          "city_chat_messages", "city_chat_turns", "city_chat_conversations",
                          "city_learning_progress", "city_settings", "city_workflows", "city_shared_results",
                          "city_memory", "city_workflow_definitions", "city_network_schedule",
                          "city_specialist_schedule", "city_proposal_reviews", "city_notification_state"):
                db.execute(f"DELETE FROM {table} WHERE username=?", (username,))


def refresh_jobs_workflow(*, published_today: bool = False, detected_today: bool = False,
                          profile: dict | None = None) -> dict:
    """Run the existing collector once, without its optional email side effect."""
    from . import internships

    if internships.opportunities_loading():
        raise CityError("La collecte planifiée est déjà en cours. Réessaie après sa fin.")
    before, _, previous_update = internships.load_opportunities(refresh=False)
    before_urls = {job.url for job in before}
    try:
        jobs, errors, updated = internships.refresh_opportunities(force=True, notify_email=False,
                                                                   fail_if_busy=True)
    except RuntimeError as exc:
        raise CityError("Une autre collecte est déjà en cours. Réessaie après sa fin.") from exc
    if updated <= previous_update:
        raise CityError("La collecte n'a pas produit de nouvelle donnée. Vérifie l'état des sources avant de réessayer.")
    discovered = [job for job in jobs if job.url not in before_urls]
    priority = [job for job in discovered
                if ("paris" in job.location.casefold() or "défense" in job.location.casefold()
                    or "defense" in job.location.casefold())
                and "2027-04" <= internships.start_month(job.start_period) <= "2027-09"]
    priority_urls = {job.url for job in priority}
    remaining = sorted((job for job in discovered if job.url not in priority_urls),
                       key=lambda job: (job.score, job.published or "", job.title.casefold()), reverse=True)
    prioritized = priority + remaining
    if published_today or detected_today:
        from zoneinfo import ZoneInfo
        today = datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()
        prioritized = sorted((job for job in (discovered if detected_today else jobs) if job.kind.casefold() in {"stage", "internship"}
                              and (detected_today or (job.published == today and not job.published_inferred))),
                             key=lambda job: job.score, reverse=True)
    from .internship_relevance import rank_offers
    from zoneinfo import ZoneInfo
    ranked = rank_offers(prioritized, profile, datetime.now(ZoneInfo("Europe/Paris")).date())
    prioritized = [job for job, _ in ranked]
    featured = prioritized[0] if prioritized else None
    selection_reason = ("Paris / La Defense; start between April and September 2027"
                        if featured in priority else "Highest relevance score among newly detected offers") if featured else ""
    if published_today:
        selection_reason = "Publication confirmée aujourd’hui, Europe/Paris" if featured else ""
    if detected_today:
        selection_reason = "Stage nouvellement détecté pendant la collecte du jour" if featured else ""
    return {**({"title": "Hugo · nouveaux stages détectés", "as_of": today,
                "text": f"Hugo : {len(prioritized)} nouveaux stages détectés lors de la collecte du {today} (Europe/Paris). "
                        f"{len(errors)} erreur(s) de source. La date de détection ne garantit pas une publication aujourd’hui."
                        + (" Les 20 premières offres sont reprises dans le chat ; le résultat contient la liste complète." if len(prioritized) > 20 else ""),
                "today_count":len(prioritized)} if detected_today else
              {"title": "Hugo · stages publiés aujourd’hui", "as_of": today,
                "text": f"{len(prioritized)} stages avec publication confirmée le {today} (Europe/Paris). "
                        f"{len(errors)} erreur(s) de source. Les dates inconnues ou estimées sont exclues.",
                "today_count": len(prioritized)} if published_today else {}),
            "new_count": len(discovered), "new_urls": [job.url for job in discovered], "total_count": len(jobs),
            "priority_count": len(priority), "source_errors": len(errors), "updated_at": updated.isoformat(),
            "featured_offer": ({"title": featured.title, "company": featured.company,
                                "location": featured.location, "url": featured.url,
                                "kind": featured.kind, "start_period": featured.start_period,
                                "published": featured.published, "published_inferred": featured.published_inferred,
                                "source": featured.source, "detected_at": updated.isoformat(),
                                "selection_reason": selection_reason} if featured else None),
            "profile_name": str(profile.get("name") or "")[:100] if profile else "",
            "ranking_note": ("Classement indicatif d'après les métiers, lieux et dates de début renseignés dans le premier profil enregistré."
                             if profile else "Aucun profil renseigné : classement général des offres."),
            "offers": [{"title": job.title, "company": job.company, "location": job.location,
                        "url": job.url, "kind": job.kind, "start_period": job.start_period,
                        "published": job.published, "published_inferred": job.published_inferred,
                        "source": job.source, "relevance": detail["relevance"],
                        "match_reasons": detail["match_reasons"],
                        "deadline": detail["deadline"]}
                       for job, detail in (ranked if published_today or detected_today else ranked[:12])]}


class CityWorker:
    def __init__(self, store: CityStore, workflow: Callable[[], dict] = refresh_jobs_workflow):
        self.store = store
        self.workflow = workflow
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._start_lock = threading.Lock()

    def start(self) -> None:
        with self._start_lock:
            if any(thread.is_alive() for thread in self._threads):
                return
            self._stop.clear()
            self.store.recover_stale()
            self._threads = [threading.Thread(target=self._loop, daemon=True,
                                              name=f"marketdesk-city-worker-{i}") for i in range(6)]
            for thread in self._threads:
                thread.start()

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=2)

    def _loop(self) -> None:
        next_network_check = 0.0
        while not self._stop.is_set():
            try:
                import time
                if time.monotonic() >= next_network_check:
                    self.store.enqueue_network_daily()
                    self.store.enqueue_specialist_schedules()
                    self.store.enqueue_daily_digest()
                    next_network_check = time.monotonic() + 60
                worked = self.run_once()
            except sqlite3.Error as exc:
                logging.warning("MarketDesk City storage temporarily unavailable (%s)", type(exc).__name__)
                worked = False
            if not worked:
                self._stop.wait(2)

    def run_once(self) -> bool:
        task = self.store.claim_next()
        if task is None:
            return False
        beating = threading.Event()

        def pulse() -> None:
            while not beating.wait(15):
                self.store.heartbeat(task["id"])

        heartbeat = threading.Thread(target=pulse, daemon=True)
        heartbeat.start()
        usage = None
        parameters = {}
        try:
            parameters = json.loads(task.get("parameters_json") or "{}")
            if task['agent_id'] == 'innovation_lab':
                with self.store.db() as db:
                    prior_reports = db.execute("SELECT result_json FROM city_tasks WHERE username=? AND agent_id='innovation_lab' AND status='completed' ORDER BY created_at DESC LIMIT 52", (task['username'],)).fetchall()
                parameters['excluded_repositories'] = list({idea['repository'] for report in prior_reports
                    for idea in json.loads(report[0] or '{}').get('ideas', []) if idea.get('repository')})
            if task['agent_id'] == 'job_hunter' and parameters.get('operation') == 'prepare_branch':
                from .city_specialists import prepare_branch
                with self.store.db() as db:
                    approval = db.execute("SELECT approved FROM city_proposal_reviews WHERE task_id=? AND username=? AND next_task_id=?",
                                          (parameters.get('source_task_id'), task['username'], task['id'])).fetchone()
                    source = db.execute("SELECT result_json FROM city_tasks WHERE id=? AND username=? AND status='completed'",
                                        (parameters.get('source_task_id'), task['username'])).fetchone()
                result = prepare_branch(task['id'], json.loads(source[0]) if source else {}, bool(approval and approval[0]))
                self.store.finish(task['id'], result=result)
                return True
            if parameters.get('operation') == 'develop':
                from .city_coding import implement_change
                result = implement_change(task['id'], {'coding_request': parameters.get('request', '')},
                                          agent_id=task['agent_id'], auto_integrate=True,
                                          on_progress=lambda message: self.store.progress(task['id'], message))
                self.store.finish(task['id'], result=result)
                if result.get('integrated') and os.getenv('MARKETDESK_CITY_SUPERVISED') == '1':
                    self._stop.set()  # Drain other running missions before the launcher activates this commit.
                return True
            if task["agent_id"] == "outreach_agent" and task.get("workflow_id"):
                dependencies = json.loads(task.get("depends_on_json") or "[]")
                with self.store.db() as db:
                    upstream, pending = set(), list(dependencies)
                    while pending and len(upstream) < 7:
                        current = pending.pop()
                        if current in upstream:
                            continue
                        upstream.add(current)
                        parent = db.execute("SELECT depends_on_json FROM city_tasks WHERE username=? AND id=?",
                                            (task["username"], current)).fetchone()
                        if parent:
                            pending.extend(json.loads(parent[0] or "[]"))
                    rows = db.execute("SELECT agent_id,result_json FROM city_tasks WHERE username=? AND id IN ("
                                      + ",".join("?" for _ in upstream) + ")",
                                      (task["username"], *upstream)).fetchall() if upstream else []
                contacts = next((json.loads(row["result_json"] or "{}").get("contacts", []) for row in rows
                                 if row["agent_id"] == "networker"), [])
                if not contacts:
                    raise CityError("Aucun contact pertinent enregistré : importe ou vérifie tes contacts dans Mail.")
                parameters["contact_id"] = contacts[0]["id"]
                # finish() reloads the persisted task; store the selected contact there too.
                task["parameters_json"] = json.dumps(parameters, ensure_ascii=False)
                with self.store.db() as db:
                    db.execute("UPDATE city_tasks SET parameters_json=? WHERE id=? AND username=? AND status='running'",
                               (task["parameters_json"], task["id"], task["username"]))
            remembered_draft = None
            if task["agent_id"] == "outreach_agent" and parameters.get("contact_id") and parameters.get("profile_id"):
                draft_key = (str(parameters["profile_id"]) + ":" + str(parameters["contact_id"]) + ":" +
                             str(parameters.get("language") or "Français").casefold())
                remembered_draft = self.store.get_memory(task["username"], "outreach_agent",
                                                         "outreach_draft", draft_key)
                if remembered_draft and not remembered_draft.get("metadata", {}).get("body"):
                    remembered_draft = None
                if remembered_draft:
                    from .state_store import load_user_data
                    contact = load_user_data(task["username"], "mail_contacts").get(str(parameters["contact_id"]), {})
                    current_body = str(contact.get("body") or "").strip()
                    if current_body:
                        metadata = dict(remembered_draft.get("metadata") or {})
                        metadata.update(subject=str(contact.get("subject") or metadata.get("subject") or ""),
                                        body=current_body,
                                        followup=str(contact.get("followup_body") or metadata.get("followup") or ""),
                                        contact_name=str(contact.get("name") or metadata.get("contact_name") or ""),
                                        contact_company=str(contact.get("company") or metadata.get("contact_company") or ""))
                        remembered_draft["metadata"] = metadata
            reusable = task["agent_id"] in {"networker", "market_analyst"} and not parameters.get("discover_public") and not parameters.get("operation")
            result = self.store.cached_result(task["username"], task["agent_id"], task["parameters_json"]) if reusable else None
            if remembered_draft:
                metadata = remembered_draft["metadata"]
                result = {"title": "Brouillon réutilisé depuis la mémoire", "subject": metadata.get("subject", ""),
                          "body": metadata.get("body", ""), "followup": metadata.get("followup", ""),
                          "contact": {"name": metadata.get("contact_name", ""),
                                      "company": metadata.get("contact_company", "")},
                          "text": "Un brouillon déjà préparé pour ce contact, ce profil et cette langue a été réutilisé.",
                          "source": "Mémoire MarketDesk City", "reused_memory": True, "xp_award": 0}
            elif result is not None:
                result = {**result, "reused_result": True}
            elif task["agent_id"] == "desk_manager" and parameters.get("operation") == "refresh_internships":
                result = self.workflow()
            else:
                from .city_services import run_agent
                if task["agent_id"] == "outreach_agent" or (task["agent_id"] == "networker" and
                        (parameters.get('operation')=='enrich_schools' or parameters.get("discover_public")
                         and os.getenv("MARKETDESK_NETWORK_SEARCH_MODE", "ai") != "public")):
                    from .city_chat import _budget_guard
                    from .llm_usage import _connect, llm_user, generation_slot
                    action = "lina_contact_discovery" if task["agent_id"] == "networker" else "speculative_mail"
                    _budget_guard(task["username"], self.store.get_settings(task["username"]),
                                  reserve_usd=0.20 if task["agent_id"] == "networker" else 0)
                    with _connect() as usage_db:
                        last_usage_id = usage_db.execute("SELECT COALESCE(MAX(id),0) FROM llm_usage "
                                                         "WHERE username=? AND action=?",
                                                         (task["username"], action)).fetchone()[0]
                    with llm_user(task["username"]), generation_slot():
                        result = run_agent(task["agent_id"], task["username"], parameters)
                    with _connect() as usage_db:
                        entries = usage_db.execute("SELECT input_tokens,output_tokens,estimated_cost_usd "
                                                   "FROM llm_usage WHERE username=? AND action=? "
                                                   "AND id>?", (task["username"], action, last_usage_id)).fetchall()
                    usage = {"input_tokens": sum(int(row[0] or 0) for row in entries),
                             "output_tokens": sum(int(row[1] or 0) for row in entries),
                             "cost": sum(float(row[2] or 0) for row in entries)}
                else:
                    result = run_agent(task["agent_id"], task["username"], parameters)
                if task["agent_id"] != "job_hunter":
                    result.setdefault("xp_award", 10)
            if task['agent_id'] == 'job_hunter' and parameters.get('source_task_id'):
                with self.store.db() as db:
                    prior = db.execute("SELECT result_json FROM city_tasks WHERE id=? AND username=? AND agent_id='innovation_lab' AND status='completed'", (parameters['source_task_id'], task['username'])).fetchone()
                if prior:
                    result['approved_innovation'] = json.loads(prior[0]).get('ideas', [])
                    result['text'] += '\n\nCahier des charges Nova validé joint à cette revue. Aucune innovation installée automatiquement.'
            self.store.finish(task["id"], result=result, usage=usage)
        except Exception as exc:
            # Public logs and the UI receive only the exception type for unknown errors.
            from .llm_usage import GenerationLimitError
            safe = str(exc) if isinstance(exc, (CityError, GenerationLimitError)) else f"Erreur de mission ({type(exc).__name__})."
            if (parameters.get('operation') == 'develop' and isinstance(exc, CityError)
                    and safe.startswith(('Quota Codex indisponible', 'Développement reporté', 'Connecte Codex'))):
                self.store.defer_coding(task['id'], safe)
            elif (parameters.get('operation') == 'develop' and isinstance(exc, CityError)
                    and safe in ('Développement suspendu : le dépôt courant contient des modifications locales suivies.',
                                 'Intégration suspendue : le dépôt courant contient des modifications locales suivies.',
                                 'Le dépôt a changé pendant les vérifications : intégration suspendue. La branche reste disponible.',
                                 'Git indisponible pour cette opération. Vérifie le clone local du dépôt.',
                                 'Dépôt Git inaccessible ou délai dépassé.')):
                self.store.defer_coding(task['id'], safe, delay_minutes=5)
            elif task['agent_id'] == 'market_analyst' and isinstance(exc, CityError) and safe.startswith("Markets n'a retourné aucune observation"):
                self.store.defer_coding(task['id'], safe)
            else:
                self.store.finish(task["id"], error=safe)
        finally:
            beating.set()
        return True
