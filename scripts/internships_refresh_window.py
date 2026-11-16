"""Keep scheduled collections inside the combined Paris / New York day."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen


def collection_window_open(now: datetime) -> bool:
    paris = now.astimezone(ZoneInfo("Europe/Paris"))
    new_york = now.astimezone(ZoneInfo("America/New_York"))
    return paris.hour >= 8 or (new_york.date() < paris.date() and new_york.hour <= 22)


def snapshot_recent(now: datetime, updated: str) -> bool:
    """Only a recent, timezone-aware publication may suppress a retry."""
    try:
        published = datetime.fromisoformat(updated)
        return published.tzinfo is not None and 0 <= (now - published).total_seconds() < 55 * 60
    except (ValueError, TypeError):
        return False


def main(now: datetime) -> None:
    scheduled = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    active = not scheduled or collection_window_open(now)
    reason = "Collection window: open" if active else "Collection window: closed"
    if scheduled and active:
        try:
            request = Request(os.environ["PUBLIC_OFFERS_URL"], headers={"Cache-Control": "no-cache"})
            with urlopen(request, timeout=12) as response:
                updated = json.load(response).get("updated", "")
            if snapshot_recent(now, updated):
                active = False
                reason = "Recent public snapshot: collection skipped (less than 55 minutes)"
        except (URLError, OSError, ValueError, KeyError, AttributeError):
            # A missing site or unreadable timestamp must never block recovery.
            reason = "Public freshness unavailable: collection allowed"
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"active={str(active).lower()}\n")
    print(reason)


if __name__ == "__main__":
    main(datetime.now(timezone.utc))
