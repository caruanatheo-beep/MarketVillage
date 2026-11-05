"""Standalone FastAPI application for MarketDesk City.

Launch with ``python -m internships_project.city_app``. It reuses the existing
SQLite account and service stores; the original Gradio apps remain separate.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .accounts import account_exists, authenticate
from .city_routes import add_city_routes
from .marketdesk_city import CityStore, CityWorker
from .registration import add_registration_routes

@asynccontextmanager
async def lifespan(_app: FastAPI):
    startup()
    try:
        yield
    finally:
        shutdown()


app = FastAPI(title="MarketDesk City", docs_url=None, redoc_url=None, openapi_url=None,
              lifespan=lifespan)
store, worker = CityStore(), None
configured: list[tuple[str, str]] = []
_sessions: dict[str, tuple[str, float]] = {}
_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()
_key = b""


def _users() -> list[tuple[str, str]]:
    raw = os.getenv("INTERNSHIPS_USERS_JSON", "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise RuntimeError("INTERNSHIPS_USERS_JSON doit être un JSON valide.") from exc
    if not isinstance(data, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in data.items()):
        raise RuntimeError("INTERNSHIPS_USERS_JSON doit contenir identifiants et mots de passe.")
    return list(data.items())


def _secure(request: Request) -> bool:
    return request.url.scheme == "https" or any(os.getenv(name) for name in
        ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "SPACE_ID", "INTERNSHIPS_PUBLIC_HTTPS"))


def _token(username: str) -> str:
    body = f"{username}|{int(time.time()) + 12 * 3600}|{secrets.token_urlsafe(12)}"
    token = f"{body}|{hmac.new(_key, body.encode(), hashlib.sha256).hexdigest()}"
    with _lock:
        _sessions[token] = (username, time.time() + 12 * 3600)
    return token


def _session(request: Request) -> str | None:
    token = request.cookies.get("marketdesk_city_session", "")
    with _lock:
        saved = _sessions.get(token)
    if not saved or saved[1] < time.time() or not _key:
        return None
    body, _, supplied = token.rpartition("|")
    expected = hmac.new(_key, body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        return None
    username = saved[0]
    return username if account_exists(username, configured) else None


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return RedirectResponse("/city/" if _session(request) else "/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if _session(request):
        return RedirectResponse("/city/", status_code=303)
    html = """<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connexion · MarketDesk City</title><style>*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(ellipse at 20% 0,#332653,#101423 62%);font:16px system-ui;color:#f5f1ff}.card{width:min(420px,calc(100% - 32px));padding:32px;border:1px solid #51476d;border-radius:18px;background:#1b2032;box-shadow:0 22px 70px #080b1490}h1{margin:0 0 8px}p{color:#b8b2ca;margin:0 0 22px}label{display:block;margin:14px 0 6px;font-size:14px;color:#e4def4}input{width:100%;height:48px;padding:0 13px;border:1px solid #55536b;border-radius:9px;background:#121827;color:white;font:inherit}input:focus{outline:2px solid #ae91ff;border-color:#ae91ff}button{width:100%;height:48px;margin-top:22px;border:0;border-radius:9px;background:#8e6ade;color:white;font:700 16px system-ui;cursor:pointer}button:hover{background:#a080f0}.error{min-height:20px;color:#ffb6c0;font-size:13px;margin-top:10px}</style>
<main class="card"><h1>MarketDesk <span style="color:#c6adff">City</span></h1><p>Connecte-toi à ton espace personnel.</p>
<form id="f"><label for="u">Identifiant</label><input id="u" name="username" autocomplete="username" required>
<label for="p">Mot de passe</label><input id="p" name="password" type="password" autocomplete="current-password" required>
<button>Se connecter</button><div class="error" id="e" role="status"></div></form></main>
<script>document.querySelector('#f').onsubmit=async e=>{e.preventDefault();let b=e.target.querySelector('button'),m=document.querySelector('#e');b.disabled=true;b.textContent='Connexion…';m.textContent='';try{let r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(e.target)))});let j=await r.json();if(!r.ok)throw Error(j.detail||'Connexion refusée');location.href='/city/'}catch(x){m.textContent=x.message}finally{b.disabled=false;b.textContent='Se connecter'}};</script></html>"""
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.post("/login")
async def login(request: Request):
    origin = request.headers.get("origin")
    if origin and (urlparse(origin).netloc != request.headers.get("host") or
                   (urlparse(origin).scheme != request.url.scheme and
                    not (_secure(request) and urlparse(origin).scheme == "https"))):
        return JSONResponse({"detail": "Origine de requête invalide."}, status_code=403)
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _lock:
        attempts = _attempts[client]
        while attempts and attempts[0] < now - 600:
            attempts.popleft()
        if len(attempts) >= 10:
            return JSONResponse({"detail": "Trop de tentatives. Réessaie dans dix minutes."}, status_code=429)
        attempts.append(now)
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > 8192):
        return JSONResponse({"detail": "Request body too large."}, status_code=413)
    try:
        body = await request.body()
        if len(body) > 8192:
            return JSONResponse({"detail": "Request body too large."}, status_code=413)
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Invalid login payload")
        username = str(data.get("username") or "")[:100]
        password = str(data.get("password") or "")[:1024]
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        username = password = ""
    if not authenticate(username, password, configured):
        return JSONResponse({"detail": "Identifiant ou mot de passe incorrect."}, status_code=401)
    response = JSONResponse({"ok": True})
    response.set_cookie("marketdesk_city_session", _token(username), max_age=43200, httponly=True,
                        secure=_secure(request), samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/logout")
def logout(request: Request):
    origin = request.headers.get("origin")
    if origin and (urlparse(origin).netloc != request.headers.get("host") or
                   (urlparse(origin).scheme != request.url.scheme and
                    not (_secure(request) and urlparse(origin).scheme == "https"))):
        return JSONResponse({"detail": "Origine de requête invalide."}, status_code=403)
    with _lock:
        _sessions.pop(request.cookies.get("marketdesk_city_session", ""), None)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("marketdesk_city_session", path="/")
    return response


def startup():
    global configured, worker, _key
    configured = _users()
    secret = os.getenv("MARKETDESK_CITY_SESSION_KEY", "").strip()
    local_host = os.getenv("MARKETDESK_CITY_HOST", "127.0.0.1").strip().lower() in {"127.0.0.1", "localhost", "::1"}
    hosted = any(os.getenv(name) for name in
                 ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "SPACE_ID", "INTERNSHIPS_PUBLIC_HTTPS"))
    if not secret and local_host and not hosted:
        # Sessions live in this process, so a fresh local-only key is sufficient.
        secret = secrets.token_urlsafe(48)
    if len(secret) < 32:
        raise RuntimeError("Définis MARKETDESK_CITY_SESSION_KEY avec une valeur aléatoire d'au moins 32 caractères pour un hébergement public.")
    _key = secret.encode()
    repository = Path(__file__).resolve().parents[1]
    try:
        revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repository, capture_output=True,
                                  text=True, timeout=5, check=True).stdout.strip()
        history = subprocess.run(['git', 'rev-list', revision], cwd=repository, capture_output=True,
                                 text=True, timeout=10, check=True).stdout
        store.active_revision = revision
        store.active_commits = set(history.splitlines())
    except (OSError, subprocess.SubprocessError):
        store.active_revision = ''
        store.active_commits = set()
    if configured:
        add_registration_routes(app, configured)
    worker = CityWorker(store)
    worker.start()
    add_city_routes(app, _session, store, worker)


def shutdown():
    if worker:
        worker.stop()


def main() -> None:
    host = os.getenv("MARKETDESK_CITY_HOST", "127.0.0.1")
    port = int(os.getenv("MARKETDESK_CITY_PORT", "7862"))
    from .local_apps import local_launch_allowed, reserve_local_socket
    if local_launch_allowed(host, "127.0.0.1"):
        # Pass the reserved socket directly to Uvicorn rather than releasing a
        # probed port that another process could claim before startup.
        with reserve_local_socket(host, port) as listener:
            actual_port = listener.getsockname()[1]
            if actual_port != port:
                print(f"Le port {port} est occupé : utilisation du port {actual_port}.", flush=True)
            address_host = "[::1]" if host == "::1" else host
            print(f"MarketDesk City : http://{address_host}:{actual_port}/city/", flush=True)
            uvicorn.Server(uvicorn.Config("internships_project.city_app:app", host=host,
                           port=actual_port, reload=False, proxy_headers=False,
                           server_header=False)).run(sockets=[listener])
        return
    uvicorn.run("internships_project.city_app:app", host=host, port=port, reload=False,
                proxy_headers=False, server_header=False)


if __name__ == "__main__":
    main()
