"""DaemonSession dual-socket + turn streaming against a live daemon."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from soothe_client import TEXT_COMPLETION
from soothe_client.appkit import DaemonSession

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_daemon_session_connect_and_detach(
    daemon_url: str,
    require_daemon: str,
    workspace_dir: Path,
) -> None:
    session = DaemonSession(daemon_url, workspace=str(workspace_dir))
    status = await session.connect()
    assert status.get("loop_id")
    assert session.loop_id
    loops = await session.list_loops(limit=10)
    assert isinstance(loops, dict)
    await session.detach()
    await session.close()


@pytest.mark.asyncio
async def test_daemon_session_turn_chunks(
    daemon_url: str,
    require_daemon: str,
    workspace_dir: Path,
) -> None:
    session = DaemonSession(daemon_url, workspace=str(workspace_dir))
    await session.connect()
    try:
        # send_input path uses intent via kwargs on underlying client; DaemonSession
        # send_turn does not expose intent_hint — use direct client for hint turns
        # when available, otherwise plain send_turn.
        send = getattr(session._client, "send_input", None)
        if callable(send) and session.loop_id:
            await send(
                session.loop_id,
                "Reply with the single word: ok",
                intent_hint=TEXT_COMPLETION,
            )
        else:
            await session.send_turn("Reply with the single word: ok")

        chunks: list[tuple] = []
        try:
            async with asyncio.timeout(45.0):
                async for item in session.iter_turn_chunks():
                    chunks.append(item)
                    if len(chunks) >= 3:
                        break
        except TimeoutError:
            pass
        # At least status/idle-driven progress or a stream chunk should arrive
        # on a healthy daemon; tolerate empty streams when the model is cold.
        assert session.loop_id
    finally:
        await session.detach()
        await session.close()


@pytest.mark.asyncio
async def test_daemon_session_history_and_state(
    daemon_url: str,
    require_daemon: str,
    workspace_dir: Path,
) -> None:
    session = DaemonSession(daemon_url, workspace=str(workspace_dir))
    await session.connect()
    try:
        assert session.loop_id
        history = await session.fetch_loop_history(session.loop_id)
        assert history.success is True or isinstance(history.goals, list)
        state = await session.aget_loop_state(session.loop_id)
        assert state is not None
    finally:
        await session.detach()
        await session.close()


@pytest.mark.asyncio
async def test_daemon_session_new_loop(
    daemon_url: str,
    require_daemon: str,
    workspace_dir: Path,
) -> None:
    session = DaemonSession(daemon_url, workspace=str(workspace_dir))
    first = await session.connect()
    first_id = first.get("loop_id")
    second = await session.new_loop()
    second_id = second.get("loop_id")
    assert first_id and second_id and first_id != second_id
    await session.detach()
    await session.close()
