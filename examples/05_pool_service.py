#!/usr/bin/env python3
"""Service-style: ConnectionPool + TurnRunner for multiple sessions.

Simulates a small backend that fans answers to an SSE-like broadcaster.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from _common import daemon_url

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
    TimeoutPolicy,
    TurnConfig,
    TurnRunner,
)


class MemStore:
    """In-memory SessionStore for demos."""

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


async def run_session(
    runner: TurnRunner, broadcaster: SSEBroadcaster, sid: str, prompt: str
) -> None:
    it, _ = broadcaster.subscribe(sid)
    task = asyncio.create_task(
        runner.execute(
            sid,
            prompt,
            "demo-user",
            sid,  # workspace_id
            None,
            InputOpts(intent_hint=TEXT_COMPLETION),
        )
    )
    try:
        async with asyncio.timeout(90.0):
            async for ev in it:
                if ev.type == "delta" and ev.data:
                    print(f"[{sid}] {ev.data}", end="", flush=True)
                elif ev.type in {"complete", "query_error"}:
                    print(f"\n[{sid}] {ev.type}: {(ev.data or '')[:200]}")
                    break
    except TimeoutError:
        print(f"\n[{sid}] timeout waiting for SSE events")
    await task


async def main() -> None:
    workspace = Path(tempfile.mkdtemp(prefix="soothe-ex-pool-"))
    store = MemStore()
    pool = ConnectionPool(
        daemon_url(),
        store,
        PoolConfig(pool_size=2, query_timeout_s=120.0),
    )
    broadcaster = SSEBroadcaster()
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
        await asyncio.gather(
            run_session(runner, broadcaster, "s-a", "Reply with one word: alpha"),
            run_session(runner, broadcaster, "s-b", "Reply with one word: beta"),
        )
        print(
            "stored messages:",
            {k: [(m.role, m.content[:40]) for m in v] for k, v in store.msgs.items()},
        )
    finally:
        await pool.release("s-a")
        await pool.release("s-b")
        await pool.stop()
        broadcaster.close_all()
        print(f"workspace={workspace}")


if __name__ == "__main__":
    asyncio.run(main())
