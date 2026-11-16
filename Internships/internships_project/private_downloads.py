"""Short lived, account-bound PDF download links for shared deployments."""

from __future__ import annotations

import secrets
import threading
import time
from pathlib import Path

_items: dict[str, tuple[str, Path, float]] = {}
_lock = threading.Lock()


def register_download(username: str, path: str, ttl: int = 3600) -> str:
    token = secrets.token_urlsafe(32)
    with _lock:
        now = time.monotonic()
        for old, (_, old_path, expiry) in list(_items.items()):
            if expiry <= now:
                _items.pop(old, None)
                try:
                    old_path.unlink(missing_ok=True)
                    old_path.parent.rmdir()
                except OSError:
                    pass
        _items[token] = (username, Path(path), now + ttl)
    timer = threading.Timer(ttl, _expire_file, args=(token,))
    timer.daemon = True
    timer.start()
    return token


def latest_download(username: str) -> Path | None:
    now = time.monotonic()
    with _lock:
        matches = [(item[2], item[1]) for item in _items.values()
                   if item[0] == username and item[2] > now and item[1].is_file()]
        return max(matches, default=(0, None), key=lambda item: item[0])[1]


def _expire_file(token: str) -> None:
    with _lock:
        item = _items.pop(token, None)
    if item:
        try:
            item[1].unlink(missing_ok=True)
            item[1].parent.rmdir()
        except OSError:
            pass


def remove_user_downloads(username: str) -> None:
    with _lock:
        tokens = [token for token, item in _items.items() if item[0] == username]
    for token in tokens:
        _expire_file(token)


def get_download(token: str, username: str) -> Path | None:
    with _lock:
        item = _items.get(token)
        if not item:
            return None
        owner, path, expiry = item
        if expiry <= time.monotonic() or owner != username or not path.is_file():
            return None
        return path

