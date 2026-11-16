"""Per-account Responses API usage ledger. No prompts or profile text are stored."""

from __future__ import annotations

import contextvars
import html
import logging
import sqlite3
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from decimal import Decimal

from . import state_store


_current_user = contextvars.ContextVar("internships_llm_user", default="")


class GenerationLimitError(RuntimeError):
    """Raised when a paid request is already running or the account is over quota."""

# USD per million text tokens, checked against official model pages on 2026-10-26.
# Unknown model names deliberately have no estimated cost.
PRICE_SOURCE = "https://developers.openai.com/api/docs/models/"
PRICES = {
    "gpt-4o": (Decimal("2.50"), Decimal("1.25"), Decimal("10.00")),
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.075"), Decimal("0.60")),
    "gpt-4.1-mini": (Decimal("0.40"), Decimal("0.10"), Decimal("1.60")),
    "gpt-5.4-mini": (Decimal("0.75"), Decimal("0.075"), Decimal("4.50")),
}
SNAPSHOTS = {
    "gpt-4o-2024-05-13": "gpt-4o",
    "gpt-4o-2024-08-06": "gpt-4o",
    "gpt-4o-2024-11-20": "gpt-4o",
    "gpt-4o-mini-2024-07-18": "gpt-4o-mini",
    "gpt-4.1-mini-2025-04-14": "gpt-4.1-mini",
    "gpt-5.4-mini-2026-03-17": "gpt-5.4-mini",
}


@contextmanager
def llm_user(username: str):
    token = _current_user.set(username)
    try:
        yield
    finally:
        _current_user.reset(token)


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def estimate_usd(model: str, usage: dict) -> Decimal | None:
    prices = PRICES.get(SNAPSHOTS.get(model, model))
    input_tokens = _count(usage.get("input_tokens"))
    output_tokens = _count(usage.get("output_tokens"))
    details = usage.get("input_tokens_details") or {}
    cached = _count(details.get("cached_tokens")) if isinstance(details, dict) else None
    if not prices or input_tokens is None or output_tokens is None or cached is None:
        return None
    if cached > input_tokens:
        return None
    regular_price, cached_price, output_price = prices
    return ((input_tokens - cached) * regular_price + cached * cached_price
            + output_tokens * output_price) / Decimal(1_000_000)


def _connect() -> sqlite3.Connection:
    connection = state_store._connect()
    connection.execute(
        "CREATE TABLE IF NOT EXISTS llm_usage ("
        "id INTEGER PRIMARY KEY, username TEXT NOT NULL, action TEXT NOT NULL, "
        "model TEXT NOT NULL, response_id TEXT, created_at TEXT NOT NULL, "
        "input_tokens INTEGER, cached_input_tokens INTEGER, output_tokens INTEGER, "
        "estimated_cost_usd TEXT, price_source TEXT)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS llm_generation_limits ("
        "username TEXT PRIMARY KEY, window_started REAL NOT NULL, calls INTEGER NOT NULL, "
        "in_progress INTEGER NOT NULL DEFAULT 0, last_finished REAL NOT NULL DEFAULT 0)"
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(llm_generation_limits)")}
    if "in_progress" not in columns:
        connection.execute("ALTER TABLE llm_generation_limits ADD COLUMN in_progress INTEGER NOT NULL DEFAULT 0")
    if "last_finished" not in columns:
        connection.execute("ALTER TABLE llm_generation_limits ADD COLUMN last_finished REAL NOT NULL DEFAULT 0")
    return connection


@contextmanager
def generation_slot(max_per_hour: int = 12):
    """Atomically prevent concurrent duplicate paid generations and cap hourly calls."""
    username = _current_user.get()
    if not username:
        yield
        return
    now = datetime.now(timezone.utc).timestamp()
    with closing(_connect()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT window_started,calls,in_progress,last_finished FROM llm_generation_limits WHERE username=?",
                (username,),
            ).fetchone()
            if row is None or now - row[0] >= 3600:
                connection.execute(
                    "INSERT INTO llm_generation_limits(username,window_started,calls,in_progress) "
                    "VALUES (?,?,1,1) ON CONFLICT(username) DO UPDATE SET "
                    "window_started=excluded.window_started,calls=1,in_progress=1",
                    (username, now),
                )
            elif row[2]:
                raise GenerationLimitError("Une génération est déjà en cours pour ton compte. Attends sa réponse avant de relancer.")
            elif row[1] >= max_per_hour:
                raise GenerationLimitError("La limite de générations IA de ton compte est atteinte pour cette heure. Réessaie plus tard.")
            elif now - row[3] < 5:
                raise GenerationLimitError("Patiente quelques secondes avant de lancer une nouvelle génération.")
            else:
                connection.execute(
                    "UPDATE llm_generation_limits SET calls=calls+1,in_progress=1 WHERE username=?",
                    (username,),
                )
    try:
        yield
    finally:
        with closing(_connect()) as connection:
            with connection:
                connection.execute(
                    "UPDATE llm_generation_limits SET in_progress=0,last_finished=? WHERE username=?",
                    (datetime.now(timezone.utc).timestamp(), username),
                )


def record_response(action: str, requested_model: str, response: dict) -> None:
    username = _current_user.get()
    if not username:
        return
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    model = str(response.get("model") or requested_model)
    details = usage.get("input_tokens_details") or {}
    cached = _count(details.get("cached_tokens")) if isinstance(details, dict) else None
    cost = estimate_usd(model, usage)
    # Hosted web search: $10/1k search actions, in addition to model tokens.
    searches = sum(1 for item in response.get("output", []) if isinstance(item, dict)
                   and item.get("type") == "web_search_call"
                   and (item.get("action") or {}).get("type") == "search")
    if cost is not None:
        cost += Decimal("0.01") * searches
    try:
        with closing(_connect()) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO llm_usage(username,action,model,response_id,created_at,"
                    "input_tokens,cached_input_tokens,output_tokens,estimated_cost_usd,price_source) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (username, action[:60], model[:100], str(response.get("id") or "")[:100],
                     datetime.now(timezone.utc).isoformat(), _count(usage.get("input_tokens")),
                     cached, _count(usage.get("output_tokens")), str(cost) if cost is not None else None,
                     PRICE_SOURCE if cost is not None else None),
                )
    except sqlite3.Error:
        logging.exception("Could not record LLM usage metadata")


def usage_report() -> dict:
    with closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT username,action,model,created_at,input_tokens,cached_input_tokens,"
            "output_tokens,estimated_cost_usd,response_id FROM llm_usage ORDER BY id DESC"
        ).fetchall()
    total = sum((Decimal(row[7]) for row in rows if row[7] is not None), Decimal(0))
    by_user: dict[str, dict] = {}
    by_action: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    by_month: dict[str, dict] = {}
    for row in rows:
        for bucket, key in ((by_user, row[0]), (by_action, row[1]),
                            (by_model, row[2]), (by_month, row[3][:7])):
            entry = bucket.setdefault(key, {"calls": 0, "input": 0, "cached": 0, "output": 0,
                                            "cost": Decimal(0), "unknown": 0})
            entry["calls"] += 1
            entry["input"] += row[4] or 0
            entry["cached"] += row[5] or 0
            entry["output"] += row[6] or 0
            if row[7] is None:
                entry["unknown"] += 1
            else:
                entry["cost"] += Decimal(row[7])
    return {"calls": len(rows), "estimated_usd": total,
            "unknown": sum(row[7] is None for row in rows),
            "by_user": by_user, "by_action": by_action,
            "by_model": by_model, "by_month": by_month, "recent": rows[:50]}


def render_usage_report() -> str:
    report = usage_report()
    def amount(value: Decimal) -> str:
        return f"${value:.4f}"
    def summary_rows(entries: dict) -> str:
        return "".join(
            '<tr><th scope="row">' + html.escape(key) + '</th>'
            + f'<td>{item["calls"]}</td><td>{item["input"]:,}</td>'
            + f'<td>{item["cached"]:,}</td><td>{item["output"]:,}</td>'
            + f'<td>{amount(item["cost"])}' + (f' · {item["unknown"]} sans estimation' if item["unknown"] else '')
            + '</td></tr>' for key, item in entries.items()
        ) or '<tr><td colspan="6">Aucun appel enregistré.</td></tr>'
    recent = "".join(
        '<tr><td>' + html.escape(row[3][:16].replace("T", " ")) + '</td><td>'
        + html.escape(row[0]) + '</td><td>' + html.escape(row[1]) + '</td><td>'
        + html.escape(row[2]) + '</td><td>' + (str(row[4]) if row[4] is not None else '—')
        + '</td><td>' + (str(row[5]) if row[5] is not None else '—')
        + '</td><td>' + (str(row[6]) if row[6] is not None else '—')
        + '</td><td>' + (amount(Decimal(row[7])) if row[7] is not None else 'Inconnu')
        + '</td><td>' + html.escape(row[8] or '—')
        + '</td></tr>' for row in report["recent"]
    ) or '<tr><td colspan="9">Aucun appel enregistré.</td></tr>'
    return (
        '<div class="usage-summary"><strong>' + amount(report["estimated_usd"])
        + f'</strong><span>Estimation pour {report["calls"]} appel(s) enregistré(s)'
        + (f' · {report["unknown"]} sans coût calculable' if report["unknown"] else '')
        + '</span></div><p class="usage-note">Estimation en USD à partir des jetons renvoyés par l’API et '
        'des tarifs publics relevés le 26/10/2026. Ce n’est pas la facture OpenAI. '
        'Les appels antérieurs à cette fonction ne sont pas inclus. Un modèle ou un usage sans tarif connu '
        'reste « Inconnu ».</p>'
        '<h4>Par compte</h4><div class="usage-table-wrap"><table><thead><tr><th>Compte</th><th>Appels</th>'
        '<th>Entrée</th><th>En cache</th><th>Sortie</th><th>Coût estimé</th></tr></thead><tbody>'
        + summary_rows(report["by_user"]) + '</tbody></table></div>'
        '<h4>Par usage</h4><div class="usage-table-wrap"><table><thead><tr><th>Usage</th><th>Appels</th>'
        '<th>Entrée</th><th>En cache</th><th>Sortie</th><th>Coût estimé</th></tr></thead><tbody>'
        + summary_rows(report["by_action"]) + '</tbody></table></div>'
        '<h4>Par mois</h4><div class="usage-table-wrap"><table><thead><tr><th>Mois</th><th>Appels</th>'
        '<th>Entrée</th><th>En cache</th><th>Sortie</th><th>Coût estimé</th></tr></thead><tbody>'
        + summary_rows(report["by_month"]) + '</tbody></table></div>'
        '<h4>Par modèle</h4><div class="usage-table-wrap"><table><thead><tr><th>Modèle</th><th>Appels</th>'
        '<th>Entrée</th><th>En cache</th><th>Sortie</th><th>Coût estimé</th></tr></thead><tbody>'
        + summary_rows(report["by_model"]) + '</tbody></table></div>'
        '<h4>Derniers appels</h4><div class="usage-table-wrap"><table><thead><tr><th>Date UTC</th>'
        '<th>Compte</th><th>Usage</th><th>Modèle</th><th>Entrée</th><th>En cache</th>'
        '<th>Sortie</th><th>Coût estimé</th><th>ID réponse</th></tr></thead><tbody>' + recent + '</tbody></table></div>'
    )
