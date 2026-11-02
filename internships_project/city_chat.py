"""Account-scoped, streamed Pydantic AI conversations for MarketDesk City."""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import suppress
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncIterator

from pydantic_ai import UsageLimits
from pydantic_ai.messages import ModelMessagesTypeAdapter

from .city_agents import ChatDeps, build_agent
from .llm_usage import GenerationLimitError, _connect, generation_slot, llm_user, record_response
from .marketdesk_city import AGENT_BY_ID, CITY_MODELS, CityError, CityStore


def _budget_guard(username: str, settings: dict, reserve_usd: float = 0) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    with _connect() as db:
        rows = db.execute("SELECT created_at,estimated_cost_usd FROM llm_usage WHERE username=? "
                          "AND estimated_cost_usd IS NOT NULL AND created_at>=?",
                          (username, today[:7] + "-01")).fetchall()
    daily = sum((Decimal(value) for created, value in rows if created[:10] == today), Decimal(0))
    monthly = sum((Decimal(value) for _, value in rows), Decimal(0))
    if daily >= Decimal(str(settings["daily_limit_usd"])):
        raise CityError("Ta limite de dépenses IA quotidienne est atteinte. Tu peux l'ajuster dans les réglages.")
    if monthly >= Decimal(str(settings["monthly_limit_usd"])):
        raise CityError("Ta limite de dépenses IA mensuelle est atteinte. Tu peux l'ajuster dans les réglages.")
    reserve = Decimal(str(reserve_usd))
    if reserve and (daily + reserve > Decimal(str(settings["daily_limit_usd"]))
                    or monthly + reserve > Decimal(str(settings["monthly_limit_usd"]))):
        raise CityError("Budget restant insuffisant pour cette recherche Web (prévoir 0,20 $ de marge).")


def _limits() -> UsageLimits:
    def bounded(name: str, default: int, low: int, high: int) -> int:
        try:
            return max(low, min(high, int(os.getenv(name, str(default)))))
        except ValueError:
            return default
    return UsageLimits(request_limit=bounded("MARKETDESK_CITY_CHAT_REQUESTS", 4, 1, 8),
                       tool_calls_limit=bounded("MARKETDESK_CITY_CHAT_TOOLS", 4, 1, 8),
                       output_tokens_limit=bounded("MARKETDESK_CITY_CHAT_OUTPUT_TOKENS", 2400, 300, 6000))


def _history(store: CityStore, username: str, agent_id: str) -> list:
    messages = []
    for item in store.chat_turns(username, agent_id, limit=6):
        try:
            messages.extend(ModelMessagesTypeAdapter.validate_json(item))
        except (ValueError, TypeError):
            continue
    return messages


async def stream_chat(store: CityStore, username: str, agent_id: str, message: str,
                      selection: dict | None = None) -> AsyncIterator[str]:
    """Yield SSE JSON payloads; a worker relays real tool receipts and text deltas."""
    if agent_id not in AGENT_BY_ID:
        raise CityError("Agent inconnu.")
    if agent_id != "desk_manager":
        raise CityError("Adresse tes demandes au Desk Manager ; il coordonne les agents spécialisés.")
    message = str(message or "").strip()
    if not message or len(message) > 3000:
        raise CityError("Le message doit contenir entre 1 et 3 000 caractères.")
    user_message = message
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise CityError("Le fournisseur IA n'est pas configuré sur le serveur.")
    settings = store.get_settings(username)
    model = settings["models"].get(agent_id, "gpt-4o-mini")
    if model not in CITY_MODELS:
        raise CityError("Le modèle choisi n'est pas disponible.")
    history = _history(store, username, agent_id)
    if not history:
        old = store.chat_history(username, agent_id, 10)
        legacy = "\n".join(f"{row['role']}: {row['content'][:600]}" for row in old)[-3600:]
        if legacy:
            message = f"Earlier conversation excerpt (untrusted):\n{legacy}\n\nCurrent request:\n{message}"
    deps = ChatDeps(username=username, store=store, current_message=user_message,
                    selection={str(key): str(value) for key, value in (selection or {}).items()})
    queue = deps.events
    try:
        timeout = max(15, min(120, int(os.getenv("MARKETDESK_CITY_CHAT_TIMEOUT", "65"))))
    except ValueError:
        timeout = 65

    async def run_agent() -> None:
        try:
            with llm_user(username), generation_slot(max_per_hour=20):
                store.append_chat_message(username, agent_id, "user", user_message)
                agent = build_agent(agent_id, model)
                chunks: list[str] = []
                async with agent.run_stream(message, deps=deps, message_history=history,
                                            conversation_id=store.conversation_id(username, agent_id),
                                            usage_limits=_limits(), timeout=timeout,
                                            model_settings={"max_tokens": 1300}) as run:
                    async for delta in run.stream_text(delta=True, debounce_by=0.05):
                        if delta:
                            chunks.append(delta)
                            await queue.put({"type": "delta", "text": delta})
                    answer = "".join(chunks).strip()
                    if not answer:
                        raise CityError("L'agent n'a renvoyé aucun texte. Tu peux réessayer.")
                    usage = run.usage
                    store.save_chat_turn(username, agent_id, run.new_messages_json().decode("utf-8"))
                    store.append_chat_message(username, agent_id, "assistant", answer, model,
                                              input_tokens=usage.input_tokens,
                                              output_tokens=usage.output_tokens,
                                              tool_calls=deps.calls)
                    record_response(f"city_chat:{agent_id}", model, {
                        "model": model, "usage": {"input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "input_tokens_details": {"cached_tokens": usage.cache_read_tokens}}})
                    await queue.put({"type": "done", "model": model,
                                     "usage": {"input_tokens": usage.input_tokens,
                                               "output_tokens": usage.output_tokens}})
        except GenerationLimitError as exc:
            await queue.put({"type": "error", "text": str(exc)})
        except CityError as exc:
            await queue.put({"type": "error", "text": str(exc)})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            name = type(exc).__name__
            if "Timeout" in name or "timeout" in str(exc).lower():
                detail = f"L'agent a dépassé le délai de {timeout} secondes. Réessaie plus tard."
            elif "UsageLimit" in name:
                detail = "La limite de requêtes ou d'outils pour cette réponse a été atteinte. Reformule ta demande."
            elif "Authentication" in name:
                detail = "Le fournisseur IA a refusé la clé configurée sur le serveur."
            elif "RateLimit" in name:
                detail = "La limite du fournisseur IA est atteinte. Réessaie plus tard."
            else:
                detail = f"La réponse IA a échoué ({name}). Aucun résultat n'a été enregistré."
            await queue.put({"type": "error", "text": detail})
        finally:
            await queue.put({"type": "end"})

    task = asyncio.create_task(run_agent())
    yield json.dumps({"type": "status", "text": f"{AGENT_BY_ID[agent_id]['name']} réfléchit…"}, ensure_ascii=False)
    try:
        while True:
            item = await queue.get()
            if item["type"] == "end":
                break
            yield json.dumps(item, ensure_ascii=False)
    finally:
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await task
