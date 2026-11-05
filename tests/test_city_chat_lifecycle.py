"""Chat disconnects must close the producer before returning to the caller."""

import asyncio
from contextlib import asynccontextmanager, nullcontext
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from internships_project import city_chat, city_routes


@pytest.fixture
def chat(monkeypatch):
    messages = []
    store = SimpleNamespace(
        get_settings=lambda _: {"models": {}},
        chat_turns=lambda *args, **kwargs: [],
        chat_history=lambda *args: [],
        append_chat_message=lambda *args, **kwargs: messages.append(args),
        conversation_id=lambda *args: "test-conversation",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-sent")
    monkeypatch.setattr(city_chat, "llm_user", lambda *args: nullcontext())
    monkeypatch.setattr(city_chat, "generation_slot", lambda **kwargs: nullcontext())
    return store, messages


@pytest.mark.parametrize("after_delta", [False, True])
def test_closing_chat_waits_for_producer_cleanup(chat, monkeypatch, after_delta):
    store, messages = chat

    async def scenario():
        started = asyncio.Event()
        stopped = asyncio.Event()
        producers = []

        async def stream_text(**kwargs):
            yield "Partial answer"
            await asyncio.Event().wait()

        @asynccontextmanager
        async def run_stream(*args, **kwargs):
            producers.append(asyncio.current_task())
            started.set()
            try:
                yield SimpleNamespace(stream_text=stream_text)
            finally:
                stopped.set()

        monkeypatch.setattr(city_chat, "build_agent", lambda *args: SimpleNamespace(run_stream=run_stream))
        events = city_chat.stream_chat(store, "test-user", "desk_manager", "Hello")
        assert json.loads(await anext(events))["type"] == "status"
        await asyncio.wait_for(started.wait(), 1)
        if after_delta:
            assert json.loads(await anext(events))["type"] == "delta"
        try:
            await events.aclose()
            assert stopped.is_set(), "Closing the chat left its producer running"
            assert producers[0].done()
            assert [row[2] for row in messages] == ["user"]
        finally:
            # Also clean up on regression, before asyncio.run masks a leaked task.
            for task in producers:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


@pytest.mark.parametrize("after_delta", [False, True])
def test_chat_deadline_cancels_stalled_agent_and_reports_error(chat, monkeypatch, after_delta):
    store, messages = chat
    monkeypatch.setenv("MARKETDESK_CITY_CHAT_TIMEOUT", "15")
    real_timeout = asyncio.timeout

    def short_timeout(delay):
        assert delay == 15
        return real_timeout(0.02)

    monkeypatch.setattr(city_chat.asyncio, "timeout", short_timeout)

    async def scenario():
        stopped = asyncio.Event()
        producers = []

        async def stream_text(**kwargs):
            yield "Partial answer"
            await asyncio.Event().wait()

        @asynccontextmanager
        async def run_stream(*args, **kwargs):
            producers.append(asyncio.current_task())
            try:
                if not after_delta:
                    # A stalled tool may prevent the stream from even opening.
                    await asyncio.Event().wait()
                yield SimpleNamespace(stream_text=stream_text)
            finally:
                stopped.set()

        monkeypatch.setattr(city_chat, "build_agent", lambda *args: SimpleNamespace(run_stream=run_stream))

        async def collect():
            return [json.loads(event) async for event in
                    city_chat.stream_chat(store, "test-user", "desk_manager", "Hello")]

        events = await asyncio.wait_for(collect(), 1)
        assert [event["type"] for event in events] == (
            ["status", "delta", "error"] if after_delta else ["status", "error"])
        assert "15 secondes" in events[-1]["text"]
        assert stopped.is_set()
        assert producers[0].done()
        assert [row[2] for row in messages] == ["user"]

    asyncio.run(scenario())


@pytest.mark.parametrize("cancel_waiting", [False, True])
def test_http_stream_closes_inner_chat_on_disconnect(chat, monkeypatch, cancel_waiting):
    store, _ = chat

    async def scenario():
        closed = asyncio.Event()
        streams = []

        async def events(*args):
            try:
                yield '{"type":"status"}'
                await asyncio.Event().wait()
            finally:
                closed.set()

        def make_events(*args):
            stream = events(*args)
            streams.append(stream)
            return stream

        monkeypatch.setattr(city_chat, "stream_chat", make_events)
        monkeypatch.setattr(city_chat, "_budget_guard", lambda *args: None)
        app = FastAPI()
        city_routes.add_city_routes(app, lambda _: "test-user", store, SimpleNamespace())
        endpoint = next(route.endpoint for route in app.routes
                        if route.path == "/city/api/chat/{agent_id}" and "POST" in route.methods)

        async def receive():
            return {"type": "http.request", "body": b'{"message":"Hello"}', "more_body": False}

        request = Request({"type": "http", "method": "POST", "path": "/city/api/chat/desk_manager",
                           "headers": [(b"x-marketdesk-city", b"1")], "scheme": "http",
                           "server": ("testserver", 80), "query_string": b""}, receive)
        response = await endpoint("desk_manager", request)
        try:
            assert await anext(response.body_iterator) == 'data: {"type":"status"}\n\n'
            if cancel_waiting:
                waiting = asyncio.create_task(anext(response.body_iterator))
                await asyncio.sleep(0)
                waiting.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await waiting
            else:
                await response.body_iterator.aclose()
            assert closed.is_set(), "HTTP stream did not close its chat generator"
        finally:
            # Retain and explicitly close streams even when the assertion fails.
            for stream in streams:
                await stream.aclose()

    asyncio.run(scenario())
