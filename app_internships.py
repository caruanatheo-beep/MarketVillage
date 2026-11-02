"""Independent entry point for the internships board."""

from __future__ import annotations

import os
import json
import socket
import time
import threading
from collections import defaultdict, deque
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from internships_project.internships_ui import APP_THEME, CSS, build_internships_app
from internships_project.internships import start_hourly_refresh
from internships_project.mail_outreach import start_followup_worker
from internships_project.login_page import auth_message
from internships_project.accounts import account_exists, admin_username, authenticate
from internships_project.registration import add_registration_routes


app = build_internships_app()


def configured_users() -> list[tuple[str, str]] | None:
    raw = os.getenv("INTERNSHIPS_USERS_JSON", "")
    if not raw:
        return None
    try:
        users = json.loads(raw)
    except ValueError as exc:
        raise ValueError("INTERNSHIPS_USERS_JSON doit être un objet JSON valide") from exc
    if (not isinstance(users, dict) or not users or
            any(not isinstance(name, str) or not name.strip() or
                not isinstance(password, str) or len(password) < 12
                for name, password in users.items())):
        raise ValueError("Configure des identifiants uniques et des mots de passe d'au moins 12 caractères")
    return list(users.items())


def available_port(preferred: int = 7861, attempts: int = 11) -> int:
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise OSError(f"No free local port found between {preferred} and {preferred + attempts - 1}.")


def create_shared_server(blocks, users: list[tuple[str, str]] | None, host: str = "127.0.0.1", port: int = 7861):
    import gradio as gr
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse

    shared = bool(users)
    if shared:
        admin_username(users)
    server = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    gradio_app = None
    if shared:
        add_registration_routes(server, users)
    login_attempts: dict[str, deque[float]] = defaultdict(deque)
    login_lock = threading.Lock()

    @server.get("/confidentialite", response_class=HTMLResponse)
    def privacy_page():
        return HTMLResponse('''<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Confidentialité · Offres</title>
<style>body{font:16px system-ui,sans-serif;line-height:1.6;color:#20243a;background:#f7f7fb;margin:0;padding:32px}
main{max-width:760px;margin:5vh auto;background:white;border:1px solid #e2e4ec;border-radius:14px;padding:28px}
a{color:#6242be}h1{font-size:28px}li{margin:.6em 0}</style><main><h1>Confidentialité</h1>
<p>Cette page décrit le fonctionnement observé dans cette version de l’application. Elle ne constitue pas une garantie de conformité juridique.</p>
<h2>Données enregistrées</h2><ul><li>Ton identifiant de compte et un hachage PBKDF2 salé du mot de passe ; celui-ci n’est pas conservé en clair.</li>
<li>Dans ton espace privé : ton profil et son résumé/CV extrait, tes candidatures, tes brouillons et tes préférences.</li>
<li>Dans « Mail » : les coordonnées corrigées des contacts importés, le texte extrait de leurs profils LinkedIn, les formats d'adresse, les messages, les statuts d'envoi et les notes. Les PDF LinkedIn eux-mêmes ne sont pas enregistrés dans le compte.</li>
<li>Un relevé des appels IA conserve le compte, le type d’appel, le modèle, la date, les jetons, le coût estimé et l’identifiant de réponse — pas le prompt.</li>
<li>Les offres sont mises en cache de façon partagée et ne contiennent pas les données de ton profil. Les briefs IA calculés sont mis en cache dans ton espace privé pendant 24 heures pour éviter de répéter un appel identique.</li></ul>
<h2>Traitement IA</h2><p>Lorsque tu demandes une analyse ou une lettre, ton nom, les informations de parcours et préférences du profil sélectionné, ainsi que les métadonnées et le descriptif public de l’offre, sont transmis à l’API OpenAI. Pour un message LinkedIn, le profil candidat complet (CV ou résumé, expériences, compétences, métiers, lieux, contrats, disponibilités et contraintes) et jusqu’à 60 000 caractères extraits du PDF du destinataire sont transmis uniquement après ton clic sur « Générer le message ». Le PDF et son texte ne sont pas enregistrés dans ton compte ni dans le relevé des appels IA ; le texte est traité en mémoire côté serveur. Les requêtes demandent <code>store:false</code> ; le traitement reste soumis aux conditions du fournisseur. Le CV importé est extrait côté serveur et le fichier temporaire est supprimé après lecture.</p>
<p>Dans « Mail », la génération transmet à OpenAI le profil candidat et les informations extraites et corrigées du destinataire. Les envois validés passent par le serveur SMTP configuré ou par Resend selon la configuration. Le destinataire reçoit le courriel et, si tu le choisis, le CV joint. Une relance automatique ne part que si tu l'actives explicitement ; la boîte de réception n'est pas synchronisée et tu dois indiquer les réponses ou refus dans le suivi.</p>
<h2>Cookies et suivi</h2><p>L’application utilise les cookies de session nécessaires à la connexion et, lors de la création d’un compte, un cookie temporaire de protection contre les requêtes intersites. Aucun outil publicitaire ou analytics n’est intégré au code de l’application. Les logos distants éventuels sont chargés depuis les domaines des entreprises.</p>
<h2>Suppression</h2><p>Tu peux supprimer ton profil depuis « Mon profil ». Cette action efface le CV importé (déjà effacé après sa lecture), le résumé enregistré, le cache de briefs, les contacts et formats de « Mail » et les exports PDF en attente. La suppression d’un compte inscrit par l’administrateur supprime les données privées de cette application et bloque son identifiant.</p>
<p><a href="/">Retour à l’application</a></p></main></html>''', headers={"Cache-Control": "no-store"})
    gr.mount_gradio_app(
        server, blocks, path="/", server_name=host, server_port=port,
        show_error=False, css=CSS, theme=APP_THEME,
        max_file_size=8_000_000, favicon_path=str(blocks.favicon_path) if blocks.favicon_path else None,
        auth=(lambda name, password: authenticate(name, password, users)) if shared else None,
        auth_message=auth_message() if shared else None,
    )
    gradio_app = next(route.app for route in server.routes
                      if hasattr(getattr(route, "app", None), "tokens"))

    @server.middleware("http")
    async def revoke_deleted_accounts(request, call_next):
        cloud = shared and bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID") or
                                os.getenv("SPACE_ID") or os.getenv("INTERNSHIPS_PUBLIC_HTTPS"))
        if cloud:
            request.cookies.pop(f"access-token-unsecure-{gradio_app.cookie_id}", None)
        if shared and request.method == "GET" and request.url.path == "/private-download":
            from fastapi.responses import FileResponse
            from internships_project.private_downloads import latest_download
            session = request.cookies.get(f"access-token-{gradio_app.cookie_id}")
            owner = gradio_app.tokens.get(session) if session else None
            path = latest_download(owner) if owner and account_exists(owner, users) else None
            if path is None:
                return JSONResponse({"detail": "Fichier introuvable ou accès refusé."}, status_code=404)
            from starlette.responses import FileResponse
            response = FileResponse(path, media_type="application/pdf", filename=path.name,
                                    headers={"Cache-Control": "private, no-store"})
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        # Shared dashboards serve private downloads only through the owner-checked route.
        # Deny Gradio's generic authenticated file endpoint so one account cannot fetch
        # another account's upload or temporary file by guessing its cache URL.
        if shared and request.method == "GET" and ("/file=" in request.url.path or "/file/" in request.url.path):
            return JSONResponse({"detail": "Fichier introuvable."}, status_code=404)
        # Bound password-guessing attempts at the actual Gradio authentication route.
        if request.method == "POST" and request.url.path.rstrip("/").endswith("/login"):
            address = request.client.host if request.client else "unknown"
            now = time.monotonic()
            with login_lock:
                attempts = login_attempts[address]
                while attempts and attempts[0] < now - 600:
                    attempts.popleft()
                if len(attempts) >= 10:
                    return JSONResponse({"detail": "Trop de tentatives de connexion. Réessaie dans dix minutes."}, status_code=429)
        token = (request.cookies.get(f"access-token-{gradio_app.cookie_id}")
                 or request.cookies.get(f"access-token-unsecure-{gradio_app.cookie_id}"))
        active_user = gradio_app.tokens.get(token) if token else None
        if shared and active_user and not account_exists(active_user, users):
            gradio_app.tokens.pop(token, None)
        response = await call_next(request)
        if request.method == "POST" and request.url.path.rstrip("/").endswith("/login"):
            address = request.client.host if request.client else "unknown"
            with login_lock:
                if response.status_code == 400:
                    login_attempts[address].append(time.monotonic())
                elif response.status_code < 400:
                    login_attempts.pop(address, None)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if cloud:
            # Gradio emits an HTTP fallback cookie for local development. Keep only
            # its Secure + HttpOnly token on public deployments.
            response.raw_headers = [
                (key, value) for key, value in response.raw_headers
                if not (key.lower() == b"set-cookie" and b"access-token-unsecure-" in value)
            ]
            if request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https":
                response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    return server


if __name__ == "__main__":
    if os.getenv("APP_TEST_MODE") == "1":
        print("Internships entry point: OK")
    else:
        start_hourly_refresh()
        start_followup_worker()
        cloud = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID") or
                     os.getenv("SPACE_ID") or os.getenv("INTERNSHIPS_PUBLIC_HTTPS"))
        users = configured_users()
        if cloud and not users:
            raise RuntimeError("Hébergement public refusé : configure INTERNSHIPS_USERS_JSON avant le lancement")
        port = int(os.getenv("PORT", "7861")) if cloud else int(os.environ["MARKETDESK_APP_PORT"]) if os.getenv("MARKETDESK_APP_PORT") else available_port()
        host = "0.0.0.0" if cloud else "127.0.0.1"
        print(f"Internships is starting on {host}:{port}")
        app.queue(default_concurrency_limit=2, max_size=16)
        if users:
            import uvicorn
            server = create_shared_server(app, users, host, port)
            if not cloud and os.getenv("MARKETDESK_NO_BROWSER") != "1":
                import threading
                import webbrowser
                threading.Timer(2, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()
            uvicorn.run(server, host=host, port=port)
        else:
            import uvicorn
            if not cloud and os.getenv("MARKETDESK_NO_BROWSER") != "1":
                import threading
                import webbrowser
                threading.Timer(2, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()
            uvicorn.run(create_shared_server(app, None, host, port), host=host, port=port)
