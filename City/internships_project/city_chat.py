"""Account-scoped, streamed Pydantic AI conversations for MarketDesk City."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
from contextlib import suppress
from typing import AsyncIterator

from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from .city_agents import COMMON, PROMPTS, ChatDeps, build_agent
from .city_development_report import format_coding_report
from .city_coding import codex_binary, codex_environment, require_chatgpt
from .marketdesk_city import AGENT_BY_ID, CityError, CityStore


_CHAT_HEARTBEAT_SECONDS = 10
CODEX_CHAT_MODEL = "gpt-6-luna"


def _closed_codex_error(diagnostic: bytes | bytearray = b'') -> CityError:
    detail = bytes(diagnostic).decode('utf-8', errors='replace').casefold()
    if any(value in detail for value in ('access is denied', 'os error 5', 'sqlite state runtime')):
        return CityError("Codex ne peut pas accéder à ses fichiers locaux. Relance City avec les droits de ton compte Windows. Aucune reprise de mission n’est confirmée sans résultat affiché.")
    return CityError("Le processus Codex s’est arrêté avant de répondre. Les boutons de reprise restent disponibles sans Codex.")


async def _resume_shortcut(deps: ChatDeps, status: str) -> str:
    tools = build_agent('desk_manager', TestModel())._function_toolset.tools
    ctx = RunContext(deps=deps, model=None, usage=RunUsage())
    inspected = await tools['inspect_mission_queue'].function_schema.call({'status': status, 'page': 1}, ctx)
    if inspected.get('status') != 'completed':
        raise CityError('Impossible de lire les missions ; aucune reprise lancée.')
    missions = inspected['data']['missions']
    if not missions:
        return 'Aucune mission en échec à relancer.' if status == 'failed' else 'Aucune mission en attente à reprendre.'
    eligible = [item for item in missions if item['retry_advice']['eligible']]
    results = {}
    if eligible:
        resumed = await tools['resume_missions'].function_schema.call({'task_ids': [item['id'] for item in eligible]}, ctx)
        if resumed.get('status') != 'completed':
            raise CityError('La reprise n’a pas pu être confirmée. Consulte les résultats enregistrés.')
        results = {item['id']: result for item, result in zip(eligible, resumed['data']['missions'])}
    count = sum(result.get('changed') and result.get('status') == 'queued' for result in results.values())
    lines = [f'{count} mission(s) remise(s) en file · {len(missions) - len(eligible)} à examiner avant relance.', '']
    for original in missions:
        result = results.get(original['id'])
        recorded = str(original.get('error') or '').strip()
        reason = f" Cause enregistrée : {recorded[:240]}." if recorded else ''
        scheduled = original.get('scheduled_at')
        if scheduled and (result is None or not result.get('changed')):
            from datetime import datetime
            from zoneinfo import ZoneInfo
            try:
                when = datetime.fromisoformat(scheduled.replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Paris'))
                reason += f" Reprise prévue le {when:%d/%m à %H:%M} (Paris)."
            except (ValueError, TypeError):
                pass
        if result is None:
            advice = original['retry_advice']
            lines.append(f"- {original['agent']} · {original['description']} : {advice['category']} — {advice['reason']}{reason} [[mission:{original['id']}]]")
            continue
        state = result.get('status')
        label = ('Remise en file' if result.get('changed') and state == 'queued' else
                 'Reprise refusée' if state == 'refused' else
                 'Déjà en cours' if state == 'running' else 'Aucune nouvelle mise en file')
        detail = result.get('message') or ''
        dependencies = ' Dépendances conservées : le démarrage attend leur résolution.' if original.get('depends_on') and state == 'queued' else ''
        lines.append(f"- {original['agent']} · {original['description']} : {label}. {detail}{dependencies}{reason} [[mission:{result['id']}]]")
    lines.extend(['', 'Une mise en file ne signifie pas que la mission a démarré ou réussi.'])
    if inspected['data']['total'] > len(missions):
        lines.append('Seules les huit missions les plus récentes de cette sélection ont été examinées.')
    return '\n'.join(lines)


def codex_chat_available() -> bool:
    try:
        require_chatgpt(codex_binary(), codex_environment())
        return True
    except CityError:
        return False


async def _rpc(process: asyncio.subprocess.Process, method: str, params: dict,
               request_id: int, timeout: int, diagnostic: bytearray | None = None) -> dict:
    if process.stdin is None or process.stdout is None:
        raise CityError("Le processus Codex n’a pas ouvert son canal de conversation.")
    process.stdin.write((json.dumps({"method": method, "id": request_id, "params": params}) + "\n").encode())
    await process.stdin.drain()
    while True:
        line = await asyncio.wait_for(process.stdout.readline(), timeout)
        if not line:
            raise _closed_codex_error(diagnostic or b'')
        try:
            response = json.loads(line)
        except (ValueError, TypeError):
            continue
        if response.get("id") != request_id:
            continue
        if response.get("error"):
            raise CityError("Codex n’a pas accepté la demande de conversation.")
        return response.get("result") or {}


async def _run_codex_turn(deps: ChatDeps, message: str, queue: asyncio.Queue,
                          timeout: int) -> str:
    binary, env = codex_binary(), codex_environment()
    await asyncio.to_thread(require_chatgpt, binary, env)
    # TestModel is used only to construct the registered Pydantic tool schemas;
    # no inference is performed by it and this does not require an API key.
    manager = build_agent("desk_manager", TestModel())
    tools = manager._function_toolset.tools
    dynamic_tools = [{"type": "function", "name": tool.tool_def.name,
                      "description": tool.tool_def.description or "",
                      "inputSchema": tool.tool_def.parameters_json_schema}
                     for tool in tools.values()]
    task_dir = tempfile.TemporaryDirectory(prefix="marketdesk-city-chat-")
    options = {"cwd": task_dir.name, "env": env,
               "stdin": asyncio.subprocess.PIPE, "stdout": asyncio.subprocess.PIPE,
               "stderr": asyncio.subprocess.PIPE}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    process = await asyncio.create_subprocess_exec(
        binary, "app-server", "--listen", "stdio://", "--disable", "apps", "--disable", "plugins",
        "-c", 'features.shell_tool=false', "-c", 'web_search="disabled"',
        "-c", 'forced_login_method="chatgpt"', **options)
    diagnostic = bytearray()
    async def read_diagnostic() -> None:
        if process.stderr is not None:
            while chunk := await process.stderr.read(4096):
                diagnostic.extend(chunk)
                del diagnostic[:-8192]
    diagnostic_task = asyncio.create_task(read_diagnostic())
    answer: list[str] = []
    message_ids: set[str] = set()
    last_message_id = ''
    request_id = 0
    last_report_key, last_report_result = None, None

    async def request(method: str, params: dict) -> dict:
        nonlocal request_id
        request_id += 1
        return await _rpc(process, method, params, request_id, timeout, diagnostic)

    async def call_city_tool(payload: dict, call_id: int | str) -> None:
        nonlocal last_report_key, last_report_result
        name = str(payload.get("tool") or "")
        tool = tools.get(name)
        success, result = False, {"error": "Outil City inconnu."}
        try:
            raw_args = payload.get("arguments") or {}
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            if not isinstance(args, dict) or tool is None:
                raise CityError("Arguments de l’outil invalides.")
            parsed = tool.function_schema.validator.validate_python(args)
            report_key = json.dumps(parsed, sort_keys=True) if name == 'read_daily_coding_changes' else None
            if report_key is not None and report_key == last_report_key:
                result = last_report_result
            else:
                last_report_key, last_report_result = None, None
                ctx = RunContext(deps=deps, model=None, usage=RunUsage(), tool_name=name,
                                 conversation_id=deps.store.conversation_id(deps.username, "desk_manager"))
                result = await tool.function_schema.call(parsed, ctx)
                if report_key is not None and result.get('status') == 'completed':
                    last_report_key, last_report_result = report_key, result
            success = True
        except Exception as exc:
            result = {"error": str(exc)[:300] if isinstance(exc, CityError)
                      else f"L’action City a échoué ({type(exc).__name__})."}
        process.stdin.write((json.dumps({"id": call_id, "result": {
            "success": success,
            "contentItems": [{"type": "inputText", "text": json.dumps(result, ensure_ascii=False, default=str)}],
        }}) + "\n").encode())
        await process.stdin.drain()

    try:
        await request("initialize", {"clientInfo": {"name": "marketdesk_city", "title": "MarketDesk City",
                            "version": "1.0.0"}, "capabilities": {"experimentalApi": True}})
        process.stdin.write(b'{"method":"initialized"}\n')
        await process.stdin.drain()
        started = await request("thread/start", {
            "model": CODEX_CHAT_MODEL, "ephemeral": True, "cwd": task_dir.name,
            "runtimeWorkspaceRoots": [], "sandbox": "read-only", "approvalPolicy": "never",
            "developerInstructions": PROMPTS["desk_manager"] + "\n" + COMMON +
                "\nRéponds brièvement et naturellement. N’utilise que les outils City fournis ; "
                "n’exécute pas de commandes et ne lis aucun fichier.",
            "dynamicTools": dynamic_tools, "serviceName": "marketdesk_city",
        })
        thread = started.get("thread") or {}
        thread_id = thread.get("id")
        if not thread_id:
            raise CityError("Codex n’a pas créé la conversation.")
        history = deps.store.chat_history(deps.username, "desk_manager", 10)
        # stream_chat persists the current user message before starting Codex;
        # it is supplied separately to turn/start and must not be injected twice.
        if history and history[-1].get("role") == "user" and history[-1].get("content") == message:
            history.pop()
        history_items = []
        for row in history:
            role, content = row.get("role"), str(row.get("content") or "")[:4000]
            if role in {"user", "assistant"} and content:
                history_items.append({"type": "message", "role": role,
                                      "content": [{"type": "input_text" if role == "user" else "output_text",
                                                   "text": content}]})
        if history_items:
            await request("thread/inject_items", {"threadId": thread_id, "items": history_items})
        request_id += 1
        turn_id = request_id
        process.stdin.write((json.dumps({"method": "turn/start", "id": turn_id,
            "params": {"threadId": thread_id, "input": [{"type": "text", "text": message}],
                       "model": CODEX_CHAT_MODEL, "effort": "low", "summary": "concise",
                       "approvalPolicy": "never", "sandboxPolicy": {"type": "readOnly"}}}) + "\n").encode())
        await process.stdin.drain()
        turn_accepted = False
        while True:
            line = await asyncio.wait_for(process.stdout.readline(), timeout)
            if not line:
                raise _closed_codex_error(diagnostic)
            try:
                event = json.loads(line)
            except (ValueError, TypeError):
                continue
            if event.get("id") == turn_id:
                if event.get("error"):
                    raise CityError("Codex n’a pas démarré la réponse.")
                turn_accepted = True
                continue
            method, params = event.get("method"), event.get("params") or {}
            if method == "item/tool/call":
                await call_city_tool(params, event.get("id"))
            elif method == "item/agentMessage/delta":
                delta = params.get("delta") or ""
                if delta:
                    message_id = str(params.get('itemId') or '')
                    if message_id and message_id != last_message_id and answer:
                        answer.append('\n\n')
                        await queue.put({'type': 'delta', 'text': '\n\n'})
                    if message_id:
                        message_ids.add(message_id)
                        last_message_id = message_id
                    answer.append(delta)
                    await queue.put({"type": "delta", "text": delta})
            elif method == "item/completed":
                item = params.get("item") or {}
                message_id = str(item.get('id') or '')
                if (item.get("type") == "agentMessage" and item.get("text")
                        and (message_id not in message_ids if message_id else not answer)):
                    if answer:
                        answer.append('\n\n')
                        await queue.put({'type': 'delta', 'text': '\n\n'})
                    answer.append(item["text"])
                    if message_id:
                        message_ids.add(message_id)
                        last_message_id = message_id
                    await queue.put({"type": "delta", "text": item["text"]})
            elif method == "turn/completed":
                turn = params.get("turn") or {}
                if turn.get("status") != "completed":
                    error = turn.get("error") or {}
                    reason = str(error.get("message") or "")
                    if "auth" in reason.casefold():
                        raise CityError("La connexion ChatGPT de Codex doit être renouvelée avec `codex login`.")
                    if "limit" in reason.casefold() or "quota" in reason.casefold():
                        raise CityError("La limite Codex est atteinte. La conversation reprendra quand elle sera renouvelée.")
                    raise CityError("Codex n’a pas terminé la réponse. Réessaie dans un instant.")
                break
        if not turn_accepted:
            raise CityError("Codex n’a pas confirmé le démarrage de la réponse.")
        result = "".join(answer).strip()
        if not result:
            raise CityError("Codex n’a renvoyé aucun texte. Tu peux réessayer.")
        return result
    finally:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 3)
            except (TimeoutError, asyncio.CancelledError):
                process.kill()
                with suppress(TimeoutError, asyncio.CancelledError):
                    await asyncio.wait_for(process.wait(), 3)
        diagnostic_task.cancel()
        with suppress(asyncio.CancelledError):
            await diagnostic_task
        task_dir.cleanup()


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
    deps = ChatDeps(username=username, store=store, current_message=user_message,
                    selection={str(key): str(value) for key, value in (selection or {}).items()})
    queue = deps.events
    try:
        timeout = max(15, min(120, int(os.getenv("MARKETDESK_CITY_CHAT_TIMEOUT", "65"))))
    except ValueError:
        timeout = 65

    async def run_agent() -> None:
        async def publish_report(*, fallback: bool = False) -> None:
            answer = format_coding_report(deps.coding_report)
            if fallback:
                answer = "La rédaction Codex n’a pas abouti. Voici le bilan enregistré.\n\n" + answer
                await queue.put({'type': 'replace', 'text': ''})
            model = 'Bilan enregistré · City'
            store.append_chat_message(username, agent_id, 'assistant', answer, model, tool_calls=deps.calls)
            await queue.put({'type': 'delta', 'text': answer})
            await queue.put({'type': 'done', 'model': model})

        def save_interrupted_actions(reason: str) -> None:
            if deps.calls:
                store.append_chat_message(username, agent_id, 'assistant',
                    reason + '\n\nLes résultats des outils ci-dessous sont conservés. '
                    + ('Une mission déjà remise en file continue indépendamment de cette réponse.'
                       if deps.resumed or deps.delegated else ''),
                    f'{CODEX_CHAT_MODEL} · Codex', tool_calls=deps.calls)
        try:
            store.append_chat_message(username, agent_id, "user", user_message)
            intent = deps.selection.get('intent')
            if intent in {'resume_pending', 'resume_failed'}:
                answer = await _resume_shortcut(deps, 'pending' if intent == 'resume_pending' else 'failed')
                model = 'Reprises vérifiées · City'
                store.append_chat_message(username, agent_id, 'assistant', answer, model, tool_calls=deps.calls)
                await queue.put({'type': 'delta', 'text': answer})
                await queue.put({'type': 'done', 'model': model})
                return
            if intent in {'daily_summary', 'contacts_report'}:
                from .city_manager_reports import daily_report, contacts_report, format_contacts_report
                answer = await asyncio.to_thread(
                    lambda: daily_report(store, username) if intent == 'daily_summary'
                    else format_contacts_report(contacts_report(store, username)))
                model = 'Bilan enregistré · City'
                store.append_chat_message(username, agent_id, 'assistant', answer, model)
                await queue.put({'type': 'delta', 'text': answer})
                await queue.put({'type': 'done', 'model': model})
                return
            if deps.selection.get('intent') == 'development_report':
                deps.coding_report = await asyncio.to_thread(store.daily_coding_changes, username)
                receipt = {'name': 'Desk Manager · changements de code du jour',
                           'status': 'completed', 'text': deps.coding_report['overview']}
                deps.calls.append(receipt)
                await queue.put({'type': 'tool', **receipt})
                await publish_report()
                return
            async with asyncio.timeout(timeout):
                answer = await _run_codex_turn(deps, message, queue, timeout)
            store.append_chat_message(username, agent_id, "assistant", answer,
                                      f"{CODEX_CHAT_MODEL} · Codex", tool_calls=deps.calls)
            await queue.put({"type": "done", "model": f"{CODEX_CHAT_MODEL} · Codex"})
        except CityError as exc:
            if deps.coding_report is not None:
                await publish_report(fallback=True)
                return
            save_interrupted_actions(str(exc))
            await queue.put({"type": "error", "text": str(exc)})
        except asyncio.CancelledError:
            save_interrupted_actions('Réponse interrompue.')
            raise
        except Exception as exc:
            if deps.coding_report is not None:
                await publish_report(fallback=True)
                return
            name = type(exc).__name__
            if "Timeout" in name or "timeout" in str(exc).lower():
                detail = f"L'agent a dépassé le délai de {timeout} secondes. Réessaie plus tard."
            else:
                detail = f"La réponse Codex a échoué ({name})."
            save_interrupted_actions(detail)
            await queue.put({"type": "error", "text": detail})
        finally:
            await queue.put({"type": "end"})

    task = asyncio.create_task(run_agent())
    try:
        yield json.dumps({"type": "status", "text": f"{AGENT_BY_ID[agent_id]['name']} réfléchit…"}, ensure_ascii=False)
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=_CHAT_HEARTBEAT_SECONDS)
            except TimeoutError:
                # Tools may be silent for longer than a proxy's idle timeout.
                # This transport-only event must not enter chat history or reset
                # the producer's overall deadline.
                yield json.dumps({"type": "heartbeat"})
                continue
            if item["type"] == "end":
                break
            yield json.dumps(item, ensure_ascii=False)
    finally:
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await task
