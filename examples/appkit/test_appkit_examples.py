"""Appkit offline examples (no live daemon).

Demonstrates SSEBroadcaster, QueryGate, EventClassifier, ConnectionPool, and
TurnRunner wiring with fakes.
"""

from __future__ import annotations

from typing import Any

import pytest

from soothe_client import DEFAULT_DELIVERABLE_PHASES, TEXT_COMPLETION
from soothe_client.appkit import (
    ChatEventTerminal,
    ClassifierConfig,
    ConnectionPool,
    ErrQueryBusy,
    EventClassifier,
    InputOpts,
    PoolConfig,
    QueryGate,
    SessionEntry,
    SessionMessage,
    SSEBroadcaster,
    SSEEvent,
    TurnConfig,
    TurnRunner,
    default_pool_config,
    extract_thinking_step,
    input_message_for_loop,
)


class _MemStore:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionEntry] = {}
        self.msgs: dict[str, list[SessionMessage]] = {}

    async def get_session(self, session_id: str) -> SessionEntry | None:
        return self.sessions.get(session_id)

    async def create_session(
        self,
        workspace_id: str,
        session_id: str,
        loop_id: str,
        session_type: str,
    ) -> None:
        self.sessions[session_id] = SessionEntry(
            workspace_id=workspace_id,
            session_id=session_id,
            loop_id=loop_id,
            session_type=session_type,
        )

    async def update_last_used(self, session_id: str) -> None:
        return None

    async def increment_reset_count(self, session_id: str) -> None:
        return None

    async def get_loop_id_for_session(self, session_id: str) -> tuple[str, bool]:
        entry = self.sessions.get(session_id)
        if entry and entry.loop_id:
            return entry.loop_id, True
        return "", False

    async def append_message(self, session_id: str, message: SessionMessage) -> None:
        self.msgs.setdefault(session_id, []).append(message)


@pytest.mark.asyncio
async def test_example_sse_broadcaster() -> None:
    b = SSEBroadcaster()
    it1, id1 = b.subscribe("session-1")
    it2, _id2 = b.subscribe("session-1")

    b.broadcast("session-1", SSEEvent(type="delta", data="hello"))
    a1, a2 = it1.__aiter__(), it2.__aiter__()
    ev1 = await a1.__anext__()
    ev2 = await a2.__anext__()
    assert ev1 == SSEEvent(type="delta", data="hello")
    assert ev2 == SSEEvent(type="delta", data="hello")

    b.unsubscribe("session-1", id1)
    b.broadcast("session-1", SSEEvent(type="complete", data="done"))
    ev2b = await a2.__anext__()
    assert ev2b.type == "complete"

    b.close("session-1")
    with pytest.raises(StopAsyncIteration):
        await a2.__anext__()


@pytest.mark.asyncio
async def test_example_query_gate() -> None:
    gate = QueryGate()
    cancelled: list[str] = []

    async def send_cancel() -> None:
        cancelled.append("daemon")

    def local_cancel() -> None:
        cancelled.append("local")

    await gate.acquire("session-1", local_cancel, send_cancel)
    assert await gate.is_active("session-1")

    with pytest.raises(ErrQueryBusy):
        await gate.acquire("session-1", local_cancel, send_cancel)

    await gate.cancel("session-1")
    assert cancelled == ["daemon", "local"]
    assert not await gate.is_active("session-1")


def test_example_event_classifier() -> None:
    cl = EventClassifier(ClassifierConfig(deliverable_phases=DEFAULT_DELIVERABLE_PHASES))
    msg = {
        "type": "next",
        "payload": {
            "mode": "messages",
            "data": [
                {
                    "type": "AIMessage",
                    "phase": "text_completion",
                    "content": "Here is the final answer to your question.",
                }
            ],
        },
    }
    result = cl.classify(msg, "")
    assert result.terminal == ChatEventTerminal.DELIVERABLE_COMPLETE
    assert result.content and "final answer" in result.content
    assert result.completion_event is not None
    assert cl.is_deliverable_completion_event(result.completion_event)
    final, ok = cl.resolve_deliverable_final_content(result, "")
    assert ok and final.startswith("Here is the final")
    assert not cl.is_substantive_assistant_reply("hi")
    assert cl.is_substantive_assistant_reply("A full reply here.")
    assert "plan_direct" not in DEFAULT_DELIVERABLE_PHASES


def test_example_thinking_step() -> None:
    line, ok = extract_thinking_step(
        "soothe.tool.execution.started",
        {"tool_name": "search"},
    )
    assert ok
    assert line == "Tool: search"


def test_example_input_message_for_loop() -> None:
    msg = input_message_for_loop("What is 2+2?", "loop-123")
    assert msg["type"] == "loop_input"
    assert msg["loop_id"] == "loop-123"

    msg2 = input_message_for_loop(
        "Analyze this image",
        "loop-456",
        [{"mime_type": "image/png", "data": "base64data"}],
        InputOpts(intent_hint="image_to_text", preferred_subagent="explore"),
    )
    assert msg2["intent_hint"] == "image_to_text"
    assert msg2["attachments"]

    msg3 = input_message_for_loop(
        "Extract data",
        "loop-789",
        None,
        InputOpts(
            intent_hint=TEXT_COMPLETION,
            response_schema={"type": "object"},
            response_schema_name="my_schema",
            response_schema_strict=True,
        ),
    )
    assert msg3["response_schema_name"] == "my_schema"
    assert msg3["response_schema_strict"] is True


def test_example_pool_config() -> None:
    cfg = default_pool_config()
    assert cfg.pool_size == 1000
    assert cfg.query_timeout_s == 30 * 60
    assert cfg.connection_timeout_s == 30.0


@pytest.mark.asyncio
async def test_example_connection_pool_construction() -> None:
    store = _MemStore()

    class _DeadClient:
        async def connect(self) -> None:
            raise RuntimeError("demo: no live daemon")

        async def reconnect(self) -> None:
            return None

        async def reattach_and_probe(self, loop_id: str) -> None:  # noqa: ARG002
            return None

        async def send_message(self, msg: Any) -> None:  # noqa: ARG002
            return None

        async def receive_messages(self, *, cancel_event: Any = None):  # noqa: ARG002
            if False:
                yield {}
            return

        def is_disconnected(self) -> bool:
            return False

        def disconnect_cause(self) -> None:
            return None

        def is_connected(self) -> bool:
            return False

        async def close(self) -> None:
            return None

    async def _bootstrap(_client: Any, _workspace_id: str, _user_id: str) -> str:
        raise RuntimeError("demo: no live daemon")

    pool = ConnectionPool(
        "ws://localhost:8765",
        store,
        PoolConfig(pool_size=2, query_timeout_s=300.0),
        factory=lambda _url: _DeadClient(),
    )
    pool.with_bootstrap(_bootstrap)
    stats = pool.stats()
    assert stats == {"active": 0, "idle": 2}
    await pool.stop()


@pytest.mark.asyncio
async def test_example_turn_runner_construction() -> None:
    store = _MemStore()

    class _DeadClient:
        async def connect(self) -> None:
            return None

        async def reconnect(self) -> None:
            return None

        async def reattach_and_probe(self, loop_id: str) -> None:  # noqa: ARG002
            return None

        async def send_message(self, msg: Any) -> None:  # noqa: ARG002
            return None

        async def receive_messages(self, *, cancel_event: Any = None):  # noqa: ARG002
            if False:
                yield {}
            return

        def is_disconnected(self) -> bool:
            return False

        def disconnect_cause(self) -> None:
            return None

        def is_connected(self) -> bool:
            return True

        async def close(self) -> None:
            return None

    async def _bootstrap(_client: Any, _workspace_id: str, _user_id: str) -> str:
        return "loop-demo"

    pool = ConnectionPool(
        "ws://localhost:8765",
        store,
        PoolConfig(pool_size=1),
        factory=lambda _url: _DeadClient(),
    )
    pool.with_bootstrap(_bootstrap)

    gate = QueryGate()
    cl = EventClassifier(ClassifierConfig(deliverable_phases=DEFAULT_DELIVERABLE_PHASES))
    broadcaster = SSEBroadcaster()
    runner = TurnRunner(
        pool,
        gate,
        cl,
        store,
        broadcaster,
        TurnConfig(query_timeout_s=600.0),
    )
    runner.with_on_complete(lambda *_a: None).with_on_error(lambda *_a: None)
    runner.with_input_builder(
        lambda text, loop_id, attachments, opts: {
            **input_message_for_loop(text, loop_id, attachments, opts),
            "custom_field": "injected",
        }
    )
    assert runner is not None
    await pool.stop()
