"""Small same-origin sign-up page alongside Gradio's protected routes."""

from __future__ import annotations

import base64
import hmac
import html
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .accounts import create_account


_LOGO = base64.b64encode((Path(__file__).parent / "assets" / "skema_emblem_2026.png").read_bytes()).decode()
_attempts: dict[str, deque[float]] = defaultdict(deque)
_attempt_lock = threading.Lock()


def _limited(address: str) -> bool:
    now = time.monotonic()
    with _attempt_lock:
        attempts = _attempts[address]
        while attempts and attempts[0] < now - 600:
            attempts.popleft()
        if len(attempts) >= 10:
            return True
        attempts.append(now)
    return False


def _secure_cookie(request: Request) -> bool:
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID") or
                os.getenv("SPACE_ID") or os.getenv("INTERNSHIPS_PUBLIC_HTTPS") or
                request.url.scheme == "https")


def _page(token: str, requires_code: bool) -> str:
    code_field = ('<label for="signup-code">Code d’invitation</label>'
                  '<input id="signup-code" name="code" type="text" autocomplete="off" required>'
                  if requires_code else '')
    return f'''<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Créer un compte · Offres</title>
<style>
* {{ box-sizing:border-box }}
body {{ margin:0; min-height:100dvh; display:grid; place-items:center; padding:20px;
  background:radial-gradient(circle at 50% 8%,#eee8ff 0,#f7f7fb 42%,#f8f9fc 100%);
  color:#17213a; font-family:Arial,Helvetica,sans-serif }}
.card {{ width:min(100%,420px); padding:28px 32px 24px; border:1px solid #e8e3f1;
  border-radius:16px; background:#fff; box-shadow:0 18px 46px rgba(49,36,90,.09) }}
.brand {{ display:flex; align-items:center; gap:12px; margin-bottom:20px }}
.emblem {{ width:84px; height:88px; flex:none; overflow:hidden; clip-path:circle(37px at 42px 44px) }}
.emblem img {{ display:block; width:1078px; height:135px; max-width:none; transform:translate(-497px,-7px) }}
.wordmark {{ display:grid; gap:4px; line-height:1 }}
.wordmark strong {{ font-size:22px; letter-spacing:.055em }}
.wordmark small {{ color:#48516b; font-size:9px; font-weight:700; letter-spacing:.15em }}
h1 {{ margin:0 0 7px; font-size:29px; line-height:1.15; letter-spacing:-.035em }}
.subtitle {{ margin:0 0 22px; color:#626d82; font-size:14px; line-height:1.5 }}
form {{ display:grid; gap:8px }}
label {{ margin-top:8px; color:#28334d; font-size:14px; font-weight:600 }}
input {{ width:100%; height:48px; padding:0 14px; border:1px solid #d8dce7; border-radius:10px;
  background:#fff; color:#17213a; font:400 16px Arial,Helvetica,sans-serif }}
input::placeholder {{ color:#8290a5 }}
input:focus-visible,button:focus-visible,a:focus-visible {{ outline:3px solid rgba(112,81,207,.22);
  outline-offset:1px; border-color:#7051cf }}
.password-wrap {{ position:relative }}
.password-wrap input {{ padding-right:88px }}
.toggle {{ position:absolute; right:7px; top:10px; padding:7px 8px; border:0;
  background:transparent; color:#6546bc; font:600 12px Arial,Helvetica,sans-serif; cursor:pointer }}
.hint {{ margin:2px 0 0; color:#68748a; font-size:12px; line-height:1.4 }}
.submit {{ width:100%; height:48px; margin-top:20px; border:0; border-radius:10px;
  background:#7051cf; color:white; font:700 15px Arial,Helvetica,sans-serif; cursor:pointer }}
.submit:hover {{ background:#5c3db8 }}
.submit:disabled {{ opacity:.72; cursor:wait }}
.message {{ min-height:18px; margin:9px 0 0; color:#a12635; font-size:13px; line-height:1.35 }}
.message.success {{ color:#267044 }}
.back {{ display:inline-block; margin-top:4px; color:#6546bc; font-size:14px; text-decoration:none }}
.back:hover {{ text-decoration:underline }}
footer {{ margin-top:19px; padding-top:14px; border-top:1px solid #eceaf2; color:#758094;
  font-size:11px; line-height:1.5; text-align:center }}
@media(max-width:520px) {{ .card {{ padding:24px 22px 20px }} h1 {{ font-size:28px }} }}
</style></head><body><main class="card">
<div class="brand"><span class="emblem"><img src="data:image/png;base64,{_LOGO}" alt=""></span>
<span class="wordmark"><strong>SKEMA</strong><small>BUSINESS SCHOOL</small></span></div>
<h1>Créer ton compte</h1><p class="subtitle">Retrouve tes offres, tes candidatures et ton profil personnel.</p>
<form id="signup" data-token="{html.escape(token, quote=True)}">
<label for="signup-user">Identifiant</label><input id="signup-user" name="username" type="text"
  autocomplete="username" autocapitalize="none" spellcheck="false" minlength="3" maxlength="32"
  pattern="[a-z][a-z0-9_.-]{{2,31}}" placeholder="ex. prenom.nom" required>
<p class="hint">3 à 32 caractères minuscules, chiffres, point, tiret ou _.</p>
<label for="signup-password">Mot de passe</label><div class="password-wrap">
<input id="signup-password" name="password" type="password" autocomplete="new-password"
  minlength="12" maxlength="128" placeholder="12 caractères minimum" required>
<button class="toggle" type="button" aria-label="Afficher le mot de passe">Afficher</button></div>
<label for="signup-confirm">Confirmer le mot de passe</label>
<input id="signup-confirm" name="confirm" type="password" autocomplete="new-password" required>
{code_field}
<button class="submit" type="submit">Créer mon compte</button></form>
<p class="message" id="signup-message" role="status" aria-live="polite"></p>
<a class="back" href="/">J’ai déjà un compte</a>
<footer>MSc Financial Markets &amp; Investments<br>Théo Caruana</footer>
</main><script>
const form=document.querySelector('#signup'),message=document.querySelector('#signup-message');
document.querySelector('.toggle').addEventListener('click',e=>{{
  const input=document.querySelector('#signup-password'),visible=input.type==='password';
  input.type=visible?'text':'password';e.currentTarget.textContent=visible?'Masquer':'Afficher';
  e.currentTarget.setAttribute('aria-label',visible?'Masquer le mot de passe':'Afficher le mot de passe');
}});
form.addEventListener('submit',async e=>{{
  e.preventDefault();message.textContent='';message.classList.remove('success');
  const data=Object.fromEntries(new FormData(form));
  if(data.password!==data.confirm){{message.textContent='Les mots de passe ne correspondent pas.';return}}
  const button=form.querySelector('.submit');button.disabled=true;button.textContent='Création en cours…';
  try {{
    const response=await fetch('/inscription',{{method:'POST',credentials:'same-origin',
      headers:{{'Content-Type':'application/json','X-Signup-Token':form.dataset.token}},body:JSON.stringify(data)}});
    const result=await response.json();
    message.textContent=result.message||'Une erreur est survenue.';
    if(response.ok){{message.classList.add('success');form.reset();}}
  }} catch (_) {{message.textContent='Connexion impossible. Réessaie dans un instant.'}}
  finally {{button.disabled=false;button.textContent='Créer mon compte'}}
}});
</script></body></html>'''


def add_registration_routes(app: FastAPI, configured: list[tuple[str, str]]) -> None:
    @app.get("/inscription", response_class=HTMLResponse)
    def signup_page(request: Request):
        token = secrets.token_urlsafe(32)
        response = HTMLResponse(_page(token, bool(os.getenv("INTERNSHIPS_SIGNUP_CODE"))))
        response.set_cookie("signup_csrf", token, max_age=3600, httponly=True,
                            secure=_secure_cookie(request),
                            samesite="strict", path="/inscription")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/inscription")
    async def signup(request: Request):
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"message": "Format de requête invalide."}, status_code=415)
        token = request.headers.get("x-signup-token", "")
        cookie = request.cookies.get("signup_csrf", "")
        if not token or not cookie or not hmac.compare_digest(token, cookie):
            return JSONResponse({"message": "Recharge la page avant de réessayer."}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"message": "Origine de requête invalide."}, status_code=403)
        if _limited(request.client.host if request.client else "unknown"):
            return JSONResponse({"message": "Trop de tentatives. Réessaie dans dix minutes."}, status_code=429)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 8192:
                return JSONResponse({"message": "Requête trop volumineuse."}, status_code=413)
        try:
            data = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"message": "Formulaire invalide."}, status_code=400)
        if not isinstance(data, dict):
            return JSONResponse({"message": "Formulaire invalide."}, status_code=400)
        username, password, confirm = data.get("username"), data.get("password"), data.get("confirm")
        if password != confirm:
            return JSONResponse({"message": "Les mots de passe ne correspondent pas."}, status_code=400)
        required_code = os.getenv("INTERNSHIPS_SIGNUP_CODE", "")
        if required_code and not hmac.compare_digest(str(data.get("code") or ""), required_code):
            return JSONResponse({"message": "Code d’invitation incorrect."}, status_code=403)
        try:
            create_account(username, password, configured)
        except ValueError as exc:
            message = str(exc)
            return JSONResponse({"message": message},
                                status_code=409 if "déjà utilisé" in message else 400)
        return JSONResponse({"message": "Compte créé. Tu peux maintenant te connecter."}, status_code=201)
