"""Three daily collections, independent of visits and without AI or email."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from . import internships

_worker: threading.Thread | None = None
HOURS = (8, 13, 18)


def due_slot(now: datetime, previous: str) -> str | None:
    local = now.astimezone(ZoneInfo("Europe/Paris"))
    hours = [hour for hour in HOURS if hour <= local.hour]
    if not hours:
        return None
    slot = f"{local.date().isoformat()}T{hours[-1]:02d}"
    return slot if slot > previous else None


def collect_if_due(now: datetime) -> bool:
    marker = internships.CACHE_PATH.with_name("offers_schedule.txt")
    try:
        previous = marker.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        previous = ""
    slot = due_slot(now, previous)
    if slot is None:
        return False
    internships.refresh_opportunities(notify_email=False, fail_if_busy=True)
    marker.parent.mkdir(parents=True, exist_ok=True)
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(slot, encoding="utf-8")
    temporary.replace(marker)
    return True


def start_scheduled_refresh() -> None:
    global _worker
    if _worker and _worker.is_alive():
        return

    def run():
        while True:
            delay = 60
            try:
                collect_if_due(datetime.now(ZoneInfo("Europe/Paris")))
            except internships.CollectionBusyError:
                pass
            except Exception as exc:
                logging.warning("Scheduled collection failed (%s); retry in 15 minutes.", type(exc).__name__)
                delay = 900
            threading.Event().wait(delay)

    _worker = threading.Thread(target=run, daemon=True, name="offers-schedule")
    _worker.start()
