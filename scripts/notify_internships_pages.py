"""Send a digest after deployment; keep only public-offer hashes in durable state."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import requests
from internships_project import email_alerts
from internships_project.public_safety import assert_public, validate_snapshot

REPOSITORY = "caruanatheo-beep/Internships-Offres"
BRANCH = "notification-state"


def public_offers(snapshot: dict) -> dict[str, object]:
    validate_snapshot(snapshot)
    offers = []
    for record in snapshot["offers"]:
        source = "JobTeaser · sitemap" if urlsplit(record["url"]).hostname in {"www.jobteaser.com", "jobteaser.com"} else "Site employeur"
        offers.append(SimpleNamespace(**{**record, "location": record.get("location_source", record["location"]),
                                        "start_period": record["start"], "source": source,
                                        "published_inferred": record["date_label"].startswith("Détectée")}))
    return {hashlib.sha256(key.encode()).hexdigest(): job
            for key, job in email_alerts._eligible_offers(offers).items()}


class Ledger:
    def __init__(self):
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            raise ValueError("Missing temporary GitHub token")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": "Bearer " + token,
                                     "Accept": "application/vnd.github+json"})
        self.url = f"https://api.github.com/repos/{REPOSITORY}/contents/seen.json"
        self.sha = None

    def read(self) -> dict | None:
        response = self.session.get(self.url, params={"ref": BRANCH}, timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        blob = response.json()
        self.sha = blob["sha"]
        document = json.loads(base64.b64decode(blob["content"]))
        if (set(document) != {"version", "seen", "updated"} or document["version"] != 1
                or not isinstance(document["seen"], list)
                or any(not isinstance(key, str) or not re.fullmatch(r"[a-f0-9]{64}", key) for key in document["seen"])):
            raise ValueError("Invalid alert ledger; sending refused")
        return document

    def write(self, seen: set[str]) -> None:
        payload = json.dumps({"version": 1, "seen": sorted(seen),
                              "updated": datetime.now(timezone.utc).isoformat()}).encode()
        assert_public(payload, "notification ledger")
        body = {"message": "Record public offer notification identities", "branch": BRANCH,
                "author": {"name": "MarketDesk", "email": "314312316+caruanatheo-beep@users.noreply.github.com"},
                "content": base64.b64encode(payload).decode()}
        if self.sha:
            body["sha"] = self.sha
        response = self.session.put(self.url, json=body, timeout=30)
        response.raise_for_status()
        self.sha = response.json()["content"]["sha"]


def notify(snapshot: dict, ledger: Ledger, *, send=email_alerts._send_message) -> int:
    config = email_alerts._configuration()
    if config is None:
        return 0
    current = public_offers(snapshot)
    previous = ledger.read()
    if previous is None:
        ledger.write(set(current))
        print("Email baseline initialized; existing offers were not sent")
        return 0
    seen = set(previous["seen"])
    fresh = {key: job for key, job in current.items() if key not in seen}
    if not fresh:
        print("No newly detected direct-source offer; no email")
        return 0
    message = email_alerts._message(list(fresh.values()), config.recipient, config.sender)
    send(config, message)
    # Never mark an offer as notified before SMTP accepts the message.
    ledger.write(seen | set(fresh))
    return len(fresh)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=Path("public-snapshot/offers.json"))
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    try:
        if args.test:
            email_alerts.send_test_email()
            print("SMTP test message accepted by provider")
        else:
            payload = args.snapshot.read_bytes()
            assert_public(payload, "notification snapshot")
            print(f"Notification digest sent: {notify(json.loads(payload), Ledger())} new offers")
    except Exception as exc:
        # SMTP/provider errors can contain addresses or credentials. Do not print them.
        print(f"::warning::Email notification failed ({type(exc).__name__}); offers remain published")
        raise SystemExit(1)
