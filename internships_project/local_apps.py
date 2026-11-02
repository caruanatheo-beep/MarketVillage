"""Local-only, allowlisted launchers for the two independent dashboards."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parent.parent
APPS = {"markets": "app.py", "internships": "app_internships.py"}
_lock = threading.Lock()
_children: dict[str, tuple[subprocess.Popen, int]] = {}


def reserve_local_socket(host: str, preferred: int) -> socket.socket:
    """Keep the chosen port bound until Uvicorn takes over, avoiding probe races."""
    if host.lower() not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("La sélection automatique du port est réservée au serveur local.")
    if not 1 <= preferred <= 65535:
        raise ValueError("Le port doit être compris entre 1 et 65535.")
    listener = socket.socket(socket.AF_INET6 if host == "::1" else socket.AF_INET)
    try:
        for port in [*range(preferred, min(preferred + 20, 65536)), 0]:
            try:
                listener.bind((host, port))
                return listener
            except OSError:
                continue
        raise OSError("Impossible de réserver un port local pour MarketDesk City.")
    except BaseException:
        listener.close()
        raise


def local_launch_allowed(host: str, client: str) -> bool:
    return (host.lower() in {"localhost", "127.0.0.1", "::1"}
            and client in {"127.0.0.1", "::1"}
            and not any(os.getenv(key) for key in
                        ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "SPACE_ID", "INTERNSHIPS_PUBLIC_HTTPS")))


def _ready(port: int) -> bool:
    # Never send local readiness probes through a configured HTTP proxy.
    try:
        with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}/", timeout=1) as response:
            return response.status < 400
    except HTTPError as exc:
        return exc.code in {401, 403}  # The app may require its own login.
    except (URLError, OSError, TimeoutError):
        return False


def launch_app(kind: str, timeout: float = 60) -> dict:
    if kind not in APPS:
        raise ValueError("Application inconnue.")
    with _lock:
        saved = _children.get(kind)
        reused = bool(saved and saved[0].poll() is None)
        if reused:
            process, port = saved
        else:
            for port in range(7870, 7890):
                if any(saved_port == port and child.poll() is None for child, saved_port in _children.values()):
                    continue
                with socket.socket() as probe:
                    try:
                        probe.bind(("127.0.0.1", port))
                    except OSError:
                        continue
                    break
            else:
                raise RuntimeError("Aucun port local libre pour ouvrir le site.")
            env = os.environ.copy()
            env.update(MARKETDESK_APP_PORT=str(port), MARKETDESK_NO_BROWSER="1",
                       GRADIO_SERVER_NAME="127.0.0.1")
            # Fixed scripts only: no user-supplied commands, shell or arguments.
            process = subprocess.Popen([sys.executable, str(ROOT / APPS[kind])], cwd=ROOT, env=env,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            _children[kind] = (process, port)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Le site n’a pas démarré. Vérifie son environnement Python avec sa commande de lancement habituelle.")
        if _ready(port):
            return {"url": f"http://127.0.0.1:{port}/", "reused": reused}
        time.sleep(.3)
    raise RuntimeError("Le site démarre encore après 60 secondes. Réessaie : la même instance sera réutilisée.")
