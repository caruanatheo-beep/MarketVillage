"""Authenticated HTTP boundary for the lightweight MarketDesk City frontend."""

from __future__ import annotations

import json
import mimetypes
import threading
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse

from .marketdesk_city import AGENTS, CityError, CityStore, CityWorker


ASSETS = Path(__file__).with_name("city_assets")


def add_city_routes(server, resolve_user, store: CityStore, worker: CityWorker) -> None:
    collection_lock = threading.Lock()
    def owner(request: Request):
        username = resolve_user(request)
        if not username:
            return None
        return username

    def denied():
        return JSONResponse({"detail": "Connecte-toi pour accéder à MarketDesk City."}, status_code=401,
                            headers={"Cache-Control": "no-store"})

    def safe_post(request: Request) -> bool:
        if request.headers.get("x-marketdesk-city") != "1":
            return False
        origin = request.headers.get("origin")
        return not origin or urlparse(origin).netloc == request.headers.get("host")

    async def bounded_json(request: Request, max_bytes: int = 1000):
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > max_bytes):
            raise ValueError("Request body too large.")
        body = await request.body()
        if len(body) > max_bytes:
            raise ValueError("Request body too large.")
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Invalid JSON body.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Invalid JSON body.")
        return payload

    @server.get("/city/")
    def city_page(request: Request):
        if not owner(request):
            return denied()
        # The HTML is never cached; content-derived URLs invalidate stale browser
        # CSS/JS after a redeploy even when the filenames remain unchanged.
        html = (ASSETS / "city.html").read_text(encoding="utf-8")
        for name in ("city.css", "city.js"):
            asset = ASSETS / name
            version = f"{asset.stat().st_mtime_ns:x}-{asset.stat().st_size:x}"
            html = html.replace(f'/city/{name}"', f'/city/{name}?v={version}"')
        return HTMLResponse(html, headers={"Cache-Control": "private, no-store",
                                           "X-Frame-Options": "SAMEORIGIN"})

    @server.get("/city/{asset_name}")
    def city_asset(asset_name: str, request: Request):
        if not owner(request):
            return denied()
        if asset_name not in {"city.css", "city.js", "pixelfloor.html", "PIXELFLOOR_LICENSE.txt", "campus.svg"}:
            return JSONResponse({"detail": "Fichier introuvable."}, status_code=404)
        return FileResponse(ASSETS / asset_name,
                            media_type=("text/html" if asset_name.endswith(".html") else
                                        "text/css" if asset_name.endswith(".css") else
                                        "text/javascript" if asset_name.endswith(".js") else
                                        "image/png" if asset_name.endswith(".png") else
                                        "image/svg+xml" if asset_name.endswith(".svg") else "text/plain"),
                            headers={"Cache-Control": "private, no-cache"})

    @server.get("/city/pixel-assets/{asset_path:path}")
    def pixel_agents_asset(asset_path: str, request: Request):
        if not owner(request):
            return denied()
        asset_root = (ASSETS / "pixel-agents" / "assets").resolve()
        asset = (asset_root / asset_path).resolve()
        if not asset.is_relative_to(asset_root) or not asset.is_file():
            return JSONResponse({"detail": "Fichier introuvable."}, status_code=404)
        media_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
        cache_control = "private, no-store" if asset.name == "manifest.json" else "private, max-age=86400"
        return FileResponse(asset, media_type=media_type,
                            headers={"Cache-Control": cache_control})

    @server.get("/city/api/state")
    def city_state(request: Request):
        username = owner(request)
        if not username:
            return denied()
        return JSONResponse(store.snapshot(username), headers={"Cache-Control": "private, no-store"})

    @server.get("/city/api/memory")
    def city_memory(request: Request):
        username = owner(request)
        if not username:
            return denied()
        query = request.query_params.get("q", "")
        agent_id = request.query_params.get("agent", "")
        try:
            entries = store.search_memory(username, query, agent_id, 20 if query else 12)
        except (ValueError, TypeError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        return JSONResponse({"entries": entries}, headers={"Cache-Control": "private, no-store"})

    @server.get("/city/api/network")
    def city_network(request: Request):
        username = owner(request)
        if not username:
            return denied()
        from .network_discovery import list_contacts
        return JSONResponse({"contacts": list_contacts(username), "schedule": store.network_schedule(username)},
                            headers={"Cache-Control": "private, no-store"})

    @server.post("/city/api/network")
    async def configure_city_network(request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requête refusée."}, status_code=403)
        try:
            payload = await bounded_json(request, 200)
            if "enabled" in payload:
                if not isinstance(payload["enabled"], bool):
                    raise ValueError("Activation invalide.")
                store.network_schedule(username, payload["enabled"])
            queued = store.enqueue_network_daily(username, manual=True) if payload.get("collect") is True else 0
            return JSONResponse({"queued": queued, "schedule": store.network_schedule(username)},
                                headers={"Cache-Control": "private, no-store"})
        except (ValueError, TypeError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)

    @server.post("/city/api/memory")
    async def save_city_memory(request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requête refusée."}, status_code=403)
        try:
            payload = await bounded_json(request, 1800)
            memory = store.record_memory(username, payload.get("title", ""), payload.get("content", ""),
                                         payload.get("kind", "preference"),
                                         payload.get("agent_id", "desk_manager"))
        except (ValueError, TypeError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        return JSONResponse({"memory": memory}, status_code=201,
                            headers={"Cache-Control": "private, no-store"})

    @server.get("/city/api/workflows/definitions")
    def list_city_workflow_definitions(request: Request):
        username = owner(request)
        if not username:
            return denied()
        return JSONResponse({"definitions": store.workflow_definitions(username)},
                            headers={"Cache-Control": "private, no-store"})

    @server.post("/city/api/workflows/definitions")
    async def save_city_workflow_definition(request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requête refusée."}, status_code=403)
        try:
            payload = await bounded_json(request, 6000)
            definition = store.save_workflow_definition(username, payload.get("name", ""),
                                                        payload.get("steps", []),
                                                        str(payload.get("id") or ""))
        except (ValueError, TypeError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        return JSONResponse({"definition": definition}, status_code=201,
                            headers={"Cache-Control": "private, no-store"})

    @server.post("/city/api/workflows/definitions/{definition_id}/run")
    async def run_city_workflow_definition(definition_id: str, request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requête refusée."}, status_code=403)
        try:
            payload = await bounded_json(request, 1000)
            workflow = store.run_workflow_definition(username, definition_id,
                                                     payload.get("request", ""),
                                                     payload.get("priority", 1))
        except (ValueError, TypeError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        worker.start()
        return JSONResponse({"workflow": workflow}, status_code=201,
                            headers={"Cache-Control": "private, no-store"})

    @server.get("/city/api/settings")
    def city_settings(request: Request):
        username = owner(request)
        if not username:
            return denied()
        from .marketdesk_city import CITY_MODELS
        settings = store.get_settings(username)
        settings["available_models"] = list(CITY_MODELS)
        settings["api_key_configured"] = bool(__import__("os").getenv("OPENAI_API_KEY", "").strip())
        return JSONResponse(settings, headers={"Cache-Control": "private, no-store"})

    @server.post("/city/api/settings")
    async def save_city_settings(request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requ\u00eate refus\u00e9e."}, status_code=403)
        try:
            payload = await bounded_json(request, 4000)
            settings = store.save_settings(username, payload)
            return JSONResponse(settings, headers={"Cache-Control": "private, no-store"})
        except (ValueError, TypeError) as exc:
            status = 413 if str(exc) == "Request body too large." else 400
            return JSONResponse({"detail": str(exc)}, status_code=status)

    @server.get("/city/api/chat/{agent_id}")
    def city_chat_history(agent_id: str, request: Request):
        username = owner(request)
        if not username:
            return denied()
        try:
            return JSONResponse({"messages": store.chat_history(username, agent_id)},
                                headers={"Cache-Control": "private, no-store"})
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=404)

    @server.post("/city/api/chat/{agent_id}")
    async def city_chat_message(agent_id: str, request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requ\u00eate refus\u00e9e."}, status_code=403)
        try:
            payload = await bounded_json(request, 5000)
            message = str(payload.get("message") or "").strip()
            selection = payload.get("selection") or {}
            if agent_id not in {agent["id"] for agent in AGENTS}:
                return JSONResponse({"detail": "Agent inconnu."}, status_code=404)
            if agent_id != "desk_manager":
                return JSONResponse({"detail": "Adresse tes demandes au Desk Manager ; il coordonne les agents sp\u00e9cialis\u00e9s."}, status_code=403)
            if not message or len(message) > 3000 or not isinstance(selection, dict):
                raise ValueError("Message invalide ou trop long.")
            if len(selection) > 4 or any(not isinstance(v, str) or len(v) > 100 for v in selection.values()):
                raise ValueError("S\u00e9lection de contexte invalide.")
            import os
            if not os.getenv("OPENAI_API_KEY", "").strip():
                return JSONResponse({"detail": "Le fournisseur IA n'est pas configur\u00e9 sur le serveur."}, status_code=503)
            from .city_chat import _budget_guard, stream_chat
            _budget_guard(username, store.get_settings(username))
            events = stream_chat(store, username, agent_id, message, selection)
            async def sse():
                async for line in events:
                    yield f"data: {line}\n\n"
            return StreamingResponse(sse(), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
        except (ValueError, TypeError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)

    @server.post("/city/api/chat/{agent_id}/clear")
    def city_chat_clear(agent_id: str, request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requ\u00eate refus\u00e9e."}, status_code=403)
        if agent_id != "desk_manager":
            return JSONResponse({"detail": "Seule la conversation avec Desk Manager peut être effacée ici."}, status_code=403)
        try:
            store.clear_chat(username, agent_id)
            return JSONResponse({"cleared": True}, headers={"Cache-Control": "no-store"})
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=404)

    @server.get("/city/api/diagnostics")
    def city_diagnostics(request: Request):
        username = owner(request)
        if not username:
            return denied()
        from .city_diagnostics import check_integrations
        return JSONResponse(check_integrations(username), headers={"Cache-Control": "private, no-store"})

    @server.get("/city/api/market-snapshot")
    def city_market_snapshot(request: Request):
        if not owner(request):
            return denied()
        try:
            from .city_services import market_snapshot
            return JSONResponse(market_snapshot(), headers={"Cache-Control": "private, max-age=50"})
        except Exception as exc:
            return JSONResponse({"points": [], "error": f"Données marché indisponibles ({type(exc).__name__})."},
                                headers={"Cache-Control": "private, no-store"})

    @server.get("/city/api/internship-highlight")
    def city_internship_highlight(request: Request):
        if not owner(request):
            return denied()
        try:
            from .city_services import internship_highlight
            return JSONResponse(internship_highlight(), headers={"Cache-Control": "private, no-store"})
        except Exception as exc:
            return JSONResponse({"featured_offer": None, "total_count": 0,
                                 "error": f"Cache Internships indisponible ({type(exc).__name__})."},
                                headers={"Cache-Control": "private, no-store"})

    @server.post("/city/api/local-apps/{kind}")
    def city_local_app(kind: str, request: Request):
        if not owner(request):
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requête refusée."}, status_code=403)
        from .local_apps import launch_app, local_launch_allowed
        if not local_launch_allowed(request.url.hostname or "", request.client.host if request.client else ""):
            return JSONResponse({"detail": "Le démarrage des sites est disponible uniquement depuis City sur cet ordinateur."}, status_code=403)
        try:
            return JSONResponse(launch_app(kind), headers={"Cache-Control": "no-store"})
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=404)
        except (RuntimeError, OSError) as exc:
            return JSONResponse({"detail": str(exc) if isinstance(exc, RuntimeError) else "Impossible de lancer le site local."}, status_code=503)

    @server.post("/city/api/collect/{kind}")
    async def city_dashboard_collection(kind: str, request: Request):
        """Run only the two explicitly approved, read-only dashboard collectors."""
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requête refusée."}, status_code=403)
        collectors = {
            "markets": ("finance_tutor", "Collecter les données Markets"),
            "internships": ("internship_scout", "Chercher les stages publiés aujourd’hui"),
        }
        if kind not in collectors:
            return JSONResponse({"detail": "Collecte inconnue."}, status_code=404)
        agent_id, description = collectors[kind]
        if not collection_lock.acquire(blocking=False):
            return JSONResponse({"detail": "Une collecte vient d'être demandée. Réessaie dans quelques secondes."}, status_code=409)
        try:
            active = next((task for task in store.snapshot(username)["tasks"]
                           if task["agent_id"] == agent_id and task["status"] in {"queued", "running", "waiting_approval"}), None)
            if active:
                return JSONResponse({"task": active, "already_running": True}, status_code=200,
                                    headers={"Cache-Control": "no-store"})
            try:
                task = store.create_task(username, agent_id, description, {"operation":"refresh_internships" if kind == "internships" else "collect_markets"}, auto_run=True)
            except (ValueError, TypeError) as exc:
                return JSONResponse({"detail": str(exc)}, status_code=400)
        finally:
            collection_lock.release()
        worker.start()
        return JSONResponse({"task": task}, status_code=201, headers={"Cache-Control": "no-store"})

    @server.post("/city/api/tasks")
    async def city_task(request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requ\u00eate refus\u00e9e."}, status_code=403)
        return JSONResponse({"detail": "Confie ta demande au Desk Manager ; les t\u00e2ches sont cr\u00e9\u00e9es par son orchestration."}, status_code=403)

    @server.post("/city/api/proposals/{task_id}/review")
    async def review_specialist_proposal(task_id: str, request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requête refusée."}, status_code=403)
        try:
            payload = await bounded_json(request)
            if type(payload.get('approved')) is not bool:
                raise ValueError("Une décision explicite est nécessaire.")
            result = store.review_specialist_proposal(username, task_id, payload['approved'])
        except (ValueError, TypeError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        worker.start()
        return JSONResponse(result)

    @server.post("/city/api/workflows")
    async def create_city_workflow(request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requête refusée."}, status_code=403)
        try:
            payload = await bounded_json(request, 1800)
            if not isinstance(payload, dict):
                raise CityError("Projet invalide.")
            workflow = store.create_workflow(username, payload.get("template"), payload.get("request"),
                                             payload.get("focus", ""), payload.get("priority", 1))
        except (ValueError, TypeError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        worker.start()
        return JSONResponse({"workflow": workflow}, status_code=201, headers={"Cache-Control": "no-store"})

    @server.post("/city/api/workflows/{workflow_id}/approve")
    def approve_city_workflow(workflow_id: str, request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requête refusée."}, status_code=403)
        if not store.approve_workflow(username, workflow_id):
            return JSONResponse({"detail": "Ce projet n'attend pas ta validation."}, status_code=409)
        worker.start()
        return JSONResponse({"approved": True}, headers={"Cache-Control": "no-store"})

    @server.post("/city/api/workflows/{workflow_id}/cancel")
    def cancel_city_workflow(workflow_id: str, request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requête refusée."}, status_code=403)
        if not store.cancel_workflow(username, workflow_id):
            return JSONResponse({"detail": "Ce projet n'est plus actif."}, status_code=409)
        return JSONResponse({"cancelled": True}, headers={"Cache-Control": "no-store"})

    @server.post("/city/api/tasks/{task_id}/cancel")
    def cancel_task(task_id: str, request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requête refusée."}, status_code=403)
        if not store.cancel_queued(username, task_id):
            return JSONResponse({"detail": "Seules tes missions en attente peuvent être annulées."}, status_code=409)
        return JSONResponse({"cancelled": True}, headers={"Cache-Control": "no-store"})

    @server.post("/city/api/tasks/{task_id}/approve")
    def approve_task(task_id: str, request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requ\u00eate refus\u00e9e."}, status_code=403)
        if not store.approve_task(username, task_id):
            return JSONResponse({"detail": "Cette mission n'attend pas ton approbation."}, status_code=409)
        worker.start()
        return JSONResponse({"approved": True}, headers={"Cache-Control": "no-store"})

    @server.post("/city/api/tasks/{task_id}/retry")
    def retry_task(task_id: str, request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requ\u00eate refus\u00e9e."}, status_code=403)
        try:
            task = store.retry_task(username, task_id)
        except (ValueError, TypeError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=409)
        worker.start()
        return JSONResponse({"task": task}, status_code=201, headers={"Cache-Control": "no-store"})

    @server.post("/city/api/tasks/{task_id}/handoff")
    async def city_handoff(task_id: str, request: Request):
        username = owner(request)
        if not username:
            return denied()
        if not safe_post(request):
            return JSONResponse({"detail": "Requ\u00eate refus\u00e9e."}, status_code=403)
        return JSONResponse({"detail": "Demande la suite au Desk Manager afin qu\u2019il r\u00e9partisse les missions."}, status_code=403)
