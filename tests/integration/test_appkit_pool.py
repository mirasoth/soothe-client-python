"""ConnectionPool + TurnRunner against a live daemon."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from soothe_client import DEFAULT_DELIVERABLE_PHASES, TEXT_COMPLETION
from soothe_client.appkit import (
    ClassifierConfig,
    ConnectionPool,
    EventClassifier,
    InputOpts,
    PoolConfig,
    QueryGate,
    SessionEntry,
    SessionMessage,
    SSEBroadcaster,
    SSEEvent,
    TimeoutPolicy,
    TurnConfig,
    TurnRunner,
)

pytestmark = pytest.mark.integration


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
async def test_pool_acquire_release(
    daemon_url: str,
    require_daemon: str,
    workspace_dir: Path,
) -> None:
    store = _MemStore()
    pool = ConnectionPool(
        daemon_url,
        store,
        PoolConfig(pool_size=2, connection_timeout_s=30.0),
    )
    try:
        conn = await pool.acquire("integ-s1", str(workspace_dir), "integ-user")
        assert conn.get_loop_id()
        entry = await store.get_session("integ-s1")
        assert entry is not None
        assert entry.loop_id == conn.get_loop_id()

        again = await pool.acquire("integ-s1", str(workspace_dir), "integ-user")
        assert again is conn
    finally:
        await pool.release("integ-s1")
        await pool.stop()


@pytest.mark.asyncio
async def test_turn_runner_text_completion(
    daemon_url: str,
    require_daemon: str,
    workspace_dir: Path,
) -> None:
    store = _MemStore()
    pool = ConnectionPool(
        daemon_url,
        store,
        PoolConfig(pool_size=2, query_timeout_s=120.0),
    )
    broadcaster = SSEBroadcaster()
    it, _ = broadcaster.subscribe("integ-turn")
    runner = TurnRunner(
        pool,
        QueryGate(),
        EventClassifier(
            ClassifierConfig(
                deliverable_phases=DEFAULT_DELIVERABLE_PHASES,
                treat_status_idle_as_complete=True,
            )
        ),
        store,
        broadcaster,
        TurnConfig(
            query_timeout_s=90.0,
            idle_timeout_s=45.0,
            on_idle_timeout=TimeoutPolicy.SOFT_COMPLETE,
            on_stream_close=TimeoutPolicy.SOFT_COMPLETE,
        ),
    )
    try:
        await runner.execute(
            "integ-turn",
            "Reply with exactly one word: hello",
            "integ-user",
            str(workspace_dir),
            None,
            InputOpts(intent_hint=TEXT_COMPLETION),
        )
        msgs = store.msgs.get("integ-turn") or []
        assert msgs, "expected TurnRunner to persist a message row"
        assert msgs[0].role in {"assistant", "error"}

        agen: AsyncIterator[SSEEvent] = it
        for _ in range(5):
            try:
                ev = await asyncio.wait_for(agen.__anext__(), timeout=2.0)
            except (TimeoutError, StopAsyncIteration):
                break
            if ev.type in {"complete", "query_error"}:
                break
    finally:
        await pool.release("integ-turn")
        await pool.stop()
        broadcaster.close_all()
