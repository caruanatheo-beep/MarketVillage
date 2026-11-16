"""One-time migration of the former single-user local tracker to an account.

Run only on the machine that holds user_state.json, before sharing the service.
"""

from __future__ import annotations

import argparse

from . import state_store


def migrate(username: str) -> tuple[int, int]:
    if not username.strip():
        raise ValueError("Indique le nom exact du compte destinataire")
    with state_store._state_lock:
        tracking, feedback, found = state_store._read_unlocked()
    if not found:
        return 0, 0
    for kind, source in (("tracking", tracking), ("feedback", feedback)):
        existing = state_store.load_user_data(username, kind)
        state_store.save_user_data(username, kind, {**source, **existing})
    return len(tracking), len(feedback)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrer le suivi local vers un compte")
    parser.add_argument("username", help="Nom exact du compte défini dans INTERNSHIPS_USERS_JSON")
    args = parser.parse_args()
    applications, feedback = migrate(args.username)
    print(f"Migration terminée : {applications} candidatures, {feedback} préférences.")
