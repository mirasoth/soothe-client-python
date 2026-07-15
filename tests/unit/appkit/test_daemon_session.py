"""Tests for Layer 0 loop RPC helpers and appkit DaemonSession."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from soothe_client.appkit import DaemonSession, should_drop_stream_chunk_early
from soothe_client.helpers import fetch_loop_cards, fetch_loop_history, fetch_loop_messages


@pytest.mark.asyncio
async def test_fetch_loop_history_requires_loop_id() -> None:
    client = MagicMock()
    with pytest.raises(ValueError, match="loop_id"):
        await fetch_loop_history(client, "")


@pytest.mark.asyncio
async def test_fetch_loop_history_calls_client() -> None:
    client = MagicMock()
    client._handshake_complete = True
    client.loop_history_fetch = AsyncMock(return_value={"goals": [{"goal_id": "g1"}]})
    result = await fetch_loop_history(client, "loop-1", timeout=5.0)
    assert result["goals"][0]["goal_id"] == "g1"
    client.loop_history_fetch.assert_awaited_once_with("loop-1", timeout=5.0)


@pytest.mark.asyncio
async def test_fetch_loop_messages_empty_without_id() -> None:
    assert await fetch_loop_messages(MagicMock(), "") == []


@pytest.mark.asyncio
async def test_fetch_loop_cards_requires_loop_id() -> None:
    with pytest.raises(ValueError, match="loop_id"):
        await fetch_loop_cards(MagicMock(), "  ")


def test_should_drop_noop_updates() -> None:
    assert should_drop_stream_chunk_early((), "updates", {"model": {}}) is True
    assert should_drop_stream_chunk_early((), "updates", {"__interrupt__": []}) is False


def test_should_drop_empty_wire_messages() -> None:
    empty = ({"type": "ai", "content": ""}, {})
    assert should_drop_stream_chunk_early((), "messages", empty) is True
    phased = ({"type": "ai", "content": "", "phase": "goal_completion"}, {})
    # phase lives on body or top-level — our wire helper checks both
    assert should_drop_stream_chunk_early((), "messages", phased) is False


@pytest.mark.asyncio
async def test_daemon_session_list_loops_uses_rpc_client(monkeypatch: pytest.MonkeyPatch) -> None:
    session = DaemonSession("ws://127.0.0.1:9")
    session._rpc_connected = True
    session._rpc_client.request = AsyncMock(return_value={"loops": []})

    result = await session.list_loops(limit=5)
    assert result == {"loops": []}
    session._rpc_client.request.assert_awaited_once_with("loop_list", {"limit": 5}, timeout=15.0)


@pytest.mark.asyncio
async def test_ensure_connected_uses_reattach_and_probe() -> None:
    session = DaemonSession("ws://127.0.0.1:9")
    session._loop_id = "loop-alive"
    session._client.is_connection_alive = MagicMock(return_value=False)
    session._client.is_disconnected = MagicMock(return_value=True)
    session._client.reconnect = AsyncMock()
    session._client.reattach_and_probe = AsyncMock()
    session._rpc_connected = True
    session._rpc_client.close = AsyncMock()

    await session.ensure_connected()

    session._client.reconnect.assert_awaited_once()
    session._client.reattach_and_probe.assert_awaited_once()
    assert session._loop_id == "loop-alive"
    assert session._rpc_connected is False


@pytest.mark.asyncio
async def test_ensure_connected_stale_falls_back_to_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from soothe_client.errors import StaleLoopError

    session = DaemonSession("ws://127.0.0.1:9")
    session._loop_id = "loop-stale"
    session._client.is_connection_alive = MagicMock(return_value=False)
    session._client.is_disconnected = MagicMock(return_value=True)
    session._client.reconnect = AsyncMock()
    session._client.reattach_and_probe = AsyncMock(side_effect=StaleLoopError("loop-stale"))
    boot = AsyncMock(return_value={"type": "status", "loop_id": "loop-fresh"})
    monkeypatch.setattr(session, "_bootstrap_loop", boot)

    await session.ensure_connected()

    boot.assert_awaited_once_with(resume_loop_id=None)


@pytest.mark.asyncio
async def test_daemon_session_fetch_loop_history_maps_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = DaemonSession("ws://127.0.0.1:9")
    session._rpc_connected = True
    session._rpc_client.request = AsyncMock(
        return_value={
            "goals": [{"goal_id": "g1"}],
            "live_cards": [],
            "live_goal_index": 0,
            "context_tokens": 12,
            "success": True,
        }
    )
    history = await session.fetch_loop_history("loop-abc")
    assert isinstance(history, SimpleNamespace)
    assert history.goals[0]["goal_id"] == "g1"
    assert history.context_tokens == 12
    assert history.success is True


@pytest.mark.asyncio
async def test_iter_turn_chunks_ends_on_idle_after_payload() -> None:
    session = DaemonSession("ws://127.0.0.1:9", post_idle_drain_deadline=0.0)
    session._loop_id = "L1"

    events = [
        {"type": "status", "state": "running", "loop_id": "L1"},
        {
            "type": "event",
            "loop_id": "L1",
            "namespace": ["n"],
            "mode": "custom",
            "data": {"type": "soothe.test"},
        },
        {"type": "status", "state": "idle", "loop_id": "L1"},
        None,
    ]
    stub = SimpleNamespace(
        read_event=AsyncMock(side_effect=events),
        peel_stale_pending_control_events=MagicMock(return_value=[]),
        inbound_dropped=0,
        is_connection_alive=MagicMock(return_value=True),
    )
    session._client = stub  # type: ignore[assignment]

    chunks = [c async for c in session.iter_turn_chunks()]
    assert chunks == [(("n",), "custom", {"type": "soothe.test"})]
    assert session.last_turn_end_state == "idle"
