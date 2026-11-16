"""Chat disconnects must close the producer before returning to the caller."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from internships_project import city_chat, city_routes


def test_idle_http_chat_emits_comments_and_keeps_the_same_read_alive():
    async def scenario():
        release = asyncio.Event()
        closed = asyncio.Event()
        reads = []

        async def events():
            try:
                yield '{"type":"status"}'
                reads.append("waiting")
                await release.wait()
                yield '{"type":"delta","text":"Réponse"}'
                yield '{"type":"done"}'
            finally:
                closed.set()

        stream = city_routes._chat_sse(events(), heartbeat_seconds=0.001)
        try:
            assert await anext(stream) == 'data: {"type":"status"}\n\n'
            for _ in range(2):
                assert await asyncio.wait_for(anext(stream), 1) == ": keep-alive\n\n"
            assert reads == ["waiting"]
            assert not closed.is_set()
            release.set()
            remaining = [frame async for frame in stream]
            assert remaining == ['data: {"type":"delta","text":"Réponse"}\n\n',
                                 'data: {"type":"done"}\n\n']
            assert closed.is_set()
        finally:
            await stream.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("cancel_waiting", [False, True])
def test_disconnect_after_heartbeat_closes_pending_read(cancel_waiting):
    async def scenario():
        closed = asyncio.Event()
        producer = []

        async def events():
            producer.append(asyncio.current_task())
            try:
                await asyncio.Event().wait()
                yield "unreachable"
            finally:
                closed.set()

        stream = city_routes._chat_sse(events(), heartbeat_seconds=0.01)
        try:
            assert await asyncio.wait_for(anext(stream), 1) == ": keep-alive\n\n"
            if cancel_waiting:
                waiting = asyncio.create_task(anext(stream))
                await asyncio.sleep(0)
                waiting.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await waiting
            else:
                await stream.aclose()
            assert closed.is_set()
            assert producer[0].done()
        finally:
            await stream.aclose()

    asyncio.run(scenario())


def test_heartbeat_does_not_hide_producer_failure():
    async def scenario():
        release = asyncio.Event()
        closed = asyncio.Event()

        async def events():
            try:
                await release.wait()
                raise RuntimeError("synthetic stream failure")
                yield "unreachable"
            finally:
                closed.set()

        stream = city_routes._chat_sse(events(), heartbeat_seconds=0.001)
        try:
            assert await asyncio.wait_for(anext(stream), 1) == ": keep-alive\n\n"
            release.set()
            with pytest.raises(RuntimeError, match="synthetic stream failure"):
                await anext(stream)
            assert closed.is_set()
        finally:
            await stream.aclose()

    asyncio.run(scenario())


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
    return store, messages


@pytest.mark.parametrize("after_delta", [False, True])
@pytest.mark.parametrize("after_heartbeat", [False, True])
def test_closing_chat_waits_for_producer_cleanup(chat, monkeypatch, after_delta, after_heartbeat):
    store, messages = chat
    if after_heartbeat:
        monkeypatch.setattr(city_chat, "_CHAT_HEARTBEAT_SECONDS", 0.001)

    async def scenario():
        started = asyncio.Event()
        stopped = asyncio.Event()
        producers = []

        async def codex_turn(deps, message, queue, timeout):
            producers.append(asyncio.current_task())
            started.set()
            await queue.put({"type": "delta", "text": "Partial answer"})
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        monkeypatch.setattr(city_chat, "_run_codex_turn", codex_turn)
        events = city_chat.stream_chat(store, "test-user", "desk_manager", "Hello")
        assert json.loads(await anext(events))["type"] == "status"
        await asyncio.wait_for(started.wait(), 1)
        if after_delta:
            assert json.loads(await anext(events))["type"] == "delta"
        if after_heartbeat:
            event = json.loads(await asyncio.wait_for(anext(events), 1))
            # The producer may already have delivered its first text chunk.
            if event["type"] == "delta":
                event = json.loads(await asyncio.wait_for(anext(events), 1))
            assert event["type"] == "heartbeat"
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
@pytest.mark.parametrize("heartbeat_seconds", [10, 0.001])
def test_chat_deadline_cancels_stalled_agent_and_reports_error(chat, monkeypatch, after_delta, heartbeat_seconds):
    store, messages = chat
    monkeypatch.setenv("MARKETDESK_CITY_CHAT_TIMEOUT", "15")
    monkeypatch.setattr(city_chat, "_CHAT_HEARTBEAT_SECONDS", heartbeat_seconds)
    real_timeout = asyncio.timeout

    def short_timeout(delay):
        assert delay == 15
        return real_timeout(0.02)

    monkeypatch.setattr(city_chat.asyncio, "timeout", short_timeout)

    async def scenario():
        stopped = asyncio.Event()
        producers = []

        async def codex_turn(deps, message, queue, timeout):
            producers.append(asyncio.current_task())
            try:
                if after_delta:
                    await queue.put({"type": "delta", "text": "Partial answer"})
                await asyncio.Event().wait()
            finally:
                stopped.set()

        monkeypatch.setattr(city_chat, "_run_codex_turn", codex_turn)

        async def collect():
            return [json.loads(event) async for event in
                    city_chat.stream_chat(store, "test-user", "desk_manager", "Hello")]

        events = await asyncio.wait_for(collect(), 1)
        if heartbeat_seconds < 1:
            assert any(event["type"] == "heartbeat" for event in events)
        assert [event["type"] for event in events if event["type"] != "heartbeat"] == (
            ["status", "delta", "error"] if after_delta else ["status", "error"])
        assert "15 secondes" in events[-1]["text"]
        assert stopped.is_set()
        assert producers[0].done()
        assert [row[2] for row in messages] == ["user"]

    asyncio.run(scenario())


@pytest.mark.parametrize("finalization", ["completed", "failed", "stalled"])
def test_chat_waits_for_stream_finalization_before_saving_success(chat, monkeypatch, finalization):
    store, messages = chat
    store.save_chat_turn = lambda *args: None
    monkeypatch.setenv("MARKETDESK_CITY_CHAT_TIMEOUT", "15")
    real_timeout = asyncio.timeout
    monkeypatch.setattr(city_chat.asyncio, "timeout", lambda _: real_timeout(0.05))

    async def scenario():
        finalizing = asyncio.Event()
        release = asyncio.Event()
        closed = asyncio.Event()

        async def codex_turn(deps, message, queue, timeout):
            await queue.put({"type": "delta", "text": "Complete answer"})
            finalizing.set()
            await release.wait()
            if finalization == "failed":
                raise RuntimeError("synthetic stream finalization failure")
            return "Complete answer"

        monkeypatch.setattr(city_chat, "_run_codex_turn", codex_turn)
        events = city_chat.stream_chat(store, "test-user", "desk_manager", "Hello")
        try:
            assert json.loads(await anext(events))["type"] == "status"
            assert json.loads(await anext(events))["type"] == "delta"
            await asyncio.wait_for(finalizing.wait(), 1)
            assert [row[2] for row in messages] == ["user"]
            if finalization != "stalled":
                release.set()

            async def collect():
                return [json.loads(event) async for event in events]

            remaining = await asyncio.wait_for(collect(), 1)
            if finalization == "completed":
                assert [event["type"] for event in remaining] == ["done"]
                assert [row[2] for row in messages] == ["user", "assistant"]
                assert messages[-1][3] == "Complete answer"
            else:
                assert [event["type"] for event in remaining] == ["error"]
                assert [row[2] for row in messages] == ["user"]
                if finalization == "stalled":
                    assert "15 secondes" in remaining[0]["text"]
                else:
                    assert "synthetic stream" not in remaining[0]["text"]
        finally:
            await events.aclose()

    asyncio.run(scenario())


def test_chat_uses_codex_without_openai_api_key_and_persists_answer(chat, monkeypatch):
    store, messages = chat
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    async def scenario():
        async def codex_turn(deps, message, queue, timeout):
            assert deps.username == "test-user"
            assert message == "Hello"
            await queue.put({"type": "delta", "text": "Réponse complète"})
            return "Réponse complète"

        monkeypatch.setattr(city_chat, "_run_codex_turn", codex_turn)
        events = [json.loads(item) async for item in
                  city_chat.stream_chat(store, "test-user", "desk_manager", "Hello")]
        assert [item["type"] for item in events] == ["status", "delta", "done"]
        assert events[-1]["model"] == "gpt-6-luna · Codex"
        assert [row[2] for row in messages] == ["user", "assistant"]
        assert messages[-1][4] == "gpt-6-luna · Codex"

    asyncio.run(scenario())


@pytest.mark.parametrize("silence_before_stream", [False, True])
def test_http_chat_heartbeat_keeps_silent_tool_alive_then_streams_answer(chat, monkeypatch, silence_before_stream):
    store, messages = chat
    monkeypatch.setattr(city_chat, "_CHAT_HEARTBEAT_SECONDS", 0.001)
    monkeypatch.setattr(city_chat, "codex_chat_available", lambda: True)

    async def scenario():
        release_tool = asyncio.Event()
        stopped = asyncio.Event()

        async def codex_turn(deps, message, queue, timeout):
            try:
                if silence_before_stream:
                    await release_tool.wait()
                await queue.put({
                    "type": "tool", "name": "test_lookup", "status": "running",
                })
                await release_tool.wait()
                await queue.put({"type": "delta", "text": "Réponse complète"})
                return "Réponse complète"
            finally:
                stopped.set()

        monkeypatch.setattr(city_chat, "_run_codex_turn", codex_turn)
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
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-accel-buffering"] == "no"
        async with city_routes.aclosing(response.body_iterator) as events:
            assert json.loads((await anext(events))[6:])["type"] == "status"
            if not silence_before_stream:
                async def next_content_event():
                    async for event in events:
                        payload = json.loads(event[6:])
                        if payload["type"] != "heartbeat":
                            return payload

                assert (await asyncio.wait_for(next_content_event(), 1))["type"] == "tool"
            for _ in range(2):
                heartbeat = await asyncio.wait_for(anext(events), 1)
                assert heartbeat == 'data: {"type": "heartbeat"}\n\n'
                assert not stopped.is_set()
                assert [row[2] for row in messages] == ["user"]
            release_tool.set()
            remaining = [json.loads(event[6:]) async for event in events]
        assert [event["type"] for event in remaining if event["type"] != "heartbeat"] == (
            ["tool", "delta", "done"] if silence_before_stream else ["delta", "done"])
        assert stopped.is_set()
        assert [row[2] for row in messages] == ["user", "assistant"]
        assert messages[-1][3] == "Réponse complète"

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
        monkeypatch.setattr(city_chat, "codex_chat_available", lambda: True)
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
