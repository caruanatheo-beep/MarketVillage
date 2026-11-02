from __future__ import annotations

import os
import socket

from src.config import settings
from src.ui import APP_THEME, CSS, build_app

app = build_app()


def available_local_port(preferred: int, attempts: int = 11) -> int:
    """Avoid serving a new build behind an older Gradio process."""
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise OSError(f"No free local port found between {preferred} and {preferred + attempts - 1}.")


def is_cloud_environment() -> bool:
    return bool(
        os.getenv("RAILWAY_ENVIRONMENT")
        or os.getenv("RAILWAY_PROJECT_ID")
        or os.getenv("SPACE_ID")
    )


def get_server_port(cloud_environment: bool) -> int:
    if cloud_environment:
        try:
            return int(os.getenv("PORT", str(settings.server_port)))
        except ValueError:
            return settings.server_port
    return available_local_port(settings.server_port)


if __name__ == "__main__":
    if os.getenv("APP_TEST_MODE") == "1":
        print("AI Sales Desk Assistant entry point: OK")
    else:
        cloud_environment = is_cloud_environment()
        port = int(os.environ["MARKETDESK_APP_PORT"]) if not cloud_environment and os.getenv("MARKETDESK_APP_PORT") else get_server_port(cloud_environment)
        server_name = "0.0.0.0" if cloud_environment else settings.server_name
        theme_name = "orange"
        print(f"AI Sales Desk Assistant is starting on {server_name}:{port} [{theme_name} theme]")
        app.queue(default_concurrency_limit=2, max_size=16).launch(
            server_name=server_name,
            server_port=port,
            show_error=False,
            inbrowser=not cloud_environment and os.getenv("MARKETDESK_NO_BROWSER") != "1",
            theme=APP_THEME,
            css=CSS,
            allowed_paths=app.allowed_paths,
        )
