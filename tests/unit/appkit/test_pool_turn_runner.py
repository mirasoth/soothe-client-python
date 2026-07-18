"""Unit tests for ConnectionPool and TurnRunner."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from soothe_client.appkit import (
    ClassifierConfig,
    ConnectionPool,
    ErrPoolExhausted,
    ErrQueryTimeout,
    EventClassifier,
    InputOpts,
    PoolConfig,
    QueryGate,
    SessionEntry,
    SessionMessage,
    SSEBroadcaster,
    TurnConfig,
    TurnRunner,
    input_message_for_loop,
)
from soothe_client.errors import DisconnectCause

TRIARCH_PHASES = frozenset(
    {
        "quiz",
        "goal_completion",
        "goal_completion",
        "text_completion",
        "image_to_text",
        "ocr",
        "embed",
    }
)


class MemStore:
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

    def messages(self, session_id: str) -> list[SessionMessage]:
        return list(self.msgs.get(session_id, []))


class FakeClient:
    def __init__(self, events: list[Any] | None = None) -> None:
        self.connected = False
        self.closed = False
        self._disconn_fired = False
        self._cause: DisconnectCause | None = None
        self._scripted = list(events or [])
        self.send_capture: list[dict[str, Any]] = []
        self.reattach_err: BaseException | None = None
        self.connect_err: BaseException | None = None

    async def connect(self) -> None:
        self.connected = True
        if self.connect_err is not None:
            raise self.connect_err

    async def reconnect(self) -> None:
        self.connected = True

    async def reattach_and_probe(self, loop_id: str) -> None:  # noqa: ARG002
        if self.reattach_err is not None:
            raise self.reattach_err

    async def send_message(self, msg: Any) -> None:
        if isinstance(msg, dict):
            self.send_capture.append(msg)

    async def receive_messages(
        self,
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        for ev in self._scripted:
            if cancel_event is not None and cancel_event.is_set():
                return
            yield ev  # type: ignore[misc]
        while cancel_event is None or not cancel_event.is_set():
            await asyncio.sleep(0.05)

    def is_disconnected(self) -> bool:
        return self._disconn_fired

    def disconnect_cause(self) -> DisconnectCause | None:
        return self._cause

    def is_connected(self) -> bool:
        return self.connected and not self.closed

    async def close(self) -> None:
        self.closed = True
        self.connected = False


def _deliverable_next(phase: str, content: str) -> dict[str, Any]:
    return {
        "proto": "1",
        "type": "next",
        "id": "sub-1",
        "payload": {
            "namespace": ["soothe", "protocol", "message"],
            "mode": "messages",
            "data": [{"type": "AIMessage", "phase": phase, "content": content}],
            "loop_id": "loop-1",
        },
    }


async def _async_bootstrap(_client: Any, _workspace_id: str, _user_id: str) -> str:
    return "loop-fresh"


def _new_test_pool(store: MemStore, fake: FakeClient) -> ConnectionPool:
    pool = ConnectionPool(
        "ws://localhost:0",
        store,
        PoolConfig(
            pool_size=4,
            query_timeout_s=5.0,
            connection_timeout_s=1.0,
            max_idle_time_s=1.0,
            health_check_interval_s=1.0,
        ),
        factory=lambda _url: fake,
    )
    pool.with_bootstrap(_async_bootstrap)
    return pool


def _triarch() -> EventClassifier:
    return EventClassifier(ClassifierConfig(deliverable_phases=TRIARCH_PHASES))


@pytest.mark.asyncio
async def test_pool_bootstrap_new_session() -> None:
    store = MemStore()
    fake = FakeClient()
    pool = _new_test_pool(store, fake)
    conn = await pool.acquire("s1", "ws-1", "user-1")
    assert conn.get_loop_id() == "loop-fresh"
    entry = await store.get_session("s1")
    assert entry is not None
    assert entry.loop_id == "loop-fresh"
    await pool.release("s1")


@pytest.mark.asyncio
async def test_pool_reuse_active_connection() -> None:
    store = MemStore()
    fake = FakeClient()
    pool = _new_test_pool(store, fake)
    conn1 = await pool.acquire("s1", "ws-1", "user-1")
    conn2 = await pool.acquire("s1", "ws-1", "user-1")
    assert conn2 is conn1
    await pool.release("s1")


@pytest.mark.asyncio
async def test_pool_exhausted() -> None:
    store = MemStore()
    fake = FakeClient()
    pool = ConnectionPool(
        "ws://localhost:0",
        store,
        PoolConfig(pool_size=1),
        factory=lambda _url: fake,
    )
    pool.with_bootstrap(_async_bootstrap)
    await pool.acquire("s1", "ws-1", "user-1")
    with pytest.raises(ErrPoolExhausted):
        await pool.acquire("s2", "ws-1", "user-1")
    await pool.release("s1")


@pytest.mark.asyncio
async def test_turn_runner_deliverable_end_to_end() -> None:
    store = MemStore()
    deliverable = _deliverable_next("text_completion", "This is a substantive final answer.")
    fake = FakeClient([deliverable])
    pool = _new_test_pool(store, fake)
    broadcaster = SSEBroadcaster()
    tr = TurnRunner(
        pool,
        QueryGate(),
        _triarch(),
        store,
        broadcaster,
        TurnConfig(query_timeout_s=2.0),
    )
    it, _ = broadcaster.subscribe("s1")
    opts = InputOpts(intent_hint="text_completion")
    await tr.execute("s1", "what is 2+2", "user-1", "ws-1", None, opts)

    agen = it.__aiter__()
    ev = None
    for _ in range(5):
        ev = await agen.__anext__()
        if ev.type == "complete":
            break
    assert ev is not None
    assert ev.type == "complete"
    msgs = store.messages("s1")
    assert msgs and msgs[0].role == "assistant"
    assert fake.send_capture
    assert fake.send_capture[0]["type"] == "loop_input"
    assert fake.send_capture[0]["intent_hint"] == "text_completion"


@pytest.mark.asyncio
async def test_turn_runner_timeout() -> None:
    store = MemStore()
    fake = FakeClient([])
    pool = _new_test_pool(store, fake)
    tr = TurnRunner(
        pool,
        QueryGate(),
        _triarch(),
        store,
        SSEBroadcaster(),
        TurnConfig(query_timeout_s=0.1),
    )
    with pytest.raises(ErrQueryTimeout):
        await tr.execute("s1", "stalled", "user-1", "ws-1", None, None)
    msgs = store.messages("s1")
    assert msgs and msgs[0].role == "error"


def test_input_message_for_loop_opts() -> None:
    msg = input_message_for_loop(
        "hi",
        "loop-1",
        None,
        InputOpts(intent_hint="text_completion", preferred_subagent="explorer"),
    )
    assert msg["type"] == "loop_input"
    assert msg["content"] == "hi"
    assert msg["loop_id"] == "loop-1"
    assert msg["intent_hint"] == "text_completion"
    assert msg["preferred_subagent"] == "explorer"


def test_input_message_for_loop_attachments() -> None:
    atts = [{"mime_type": "image/png", "data": "BASE64"}]
    msg = input_message_for_loop("hi", "loop-1", atts)
    assert msg["attachments"] == atts
