"""The chat's character allowance must survive UTF-8 and JSON encoding."""

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from internships_project import city_chat, city_routes


@pytest.fixture
def chat_client(monkeypatch):
    received = []

    async def stream(store, username, agent_id, message, selection):
        received.append((username, agent_id, message, selection))
        yield json.dumps({"type": "done"})

    # Exercise the HTTP boundary without any provider request or stored data.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-sent")
    monkeypatch.setattr(city_chat, "_budget_guard", lambda *args: None)
    monkeypatch.setattr(city_chat, "stream_chat", stream)
    app = FastAPI()
    city_routes.add_city_routes(app, lambda _: "synthetic-user",
                               SimpleNamespace(get_settings=lambda _: {}), None)
    with TestClient(app) as client:
        yield client, received


def send(client, payload, ensure_ascii=False):
    return client.post(
        "/city/api/chat/desk_manager",
        content=json.dumps(payload, ensure_ascii=ensure_ascii).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-MarketDesk-City": "1"},
    )


@pytest.mark.parametrize("character", ["a", "é", "界", "😀"])
@pytest.mark.parametrize("ensure_ascii", [False, True])
def test_full_length_unicode_message_reaches_chat_unchanged(chat_client, character, ensure_ascii):
    client, received = chat_client
    message = character * 3000
    selection = {f"item{i}": "😀" * 100 for i in range(4)}
    response = send(client, {"message": message, "selection": selection}, ensure_ascii)
    assert response.status_code == 200
    assert '"type": "done"' in response.text
    assert received == [("synthetic-user", "desk_manager", message, selection)]


@pytest.mark.parametrize("payload", [
    {"message": "é" * 3001},
    {"message": "😀" * 3001},
    {"message": "Bonjour", "selection": {"item": "😀" * 101}},
    {"message": "Bonjour", "selection": {str(i): "a" for i in range(5)}},
    {"message": " " * 3000},
    {"message": "Bonjour", "padding": "a" * 50000},
])
def test_invalid_or_oversized_requests_never_start_chat(chat_client, payload):
    client, received = chat_client
    assert send(client, payload).status_code == 400
    assert received == []
