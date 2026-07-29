"""Shared helpers for live-daemon integration tests."""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

from soothe_client import WebSocketClient, fetch_execution_state

# Wire event type emitted when a turn's stream ends (soothe_sdk.core.events).
# A client observes turn completion through this frame, not through the loop
# metadata ``status`` field, which is reconciled to ``idle`` only on a slow
# periodic sweep (see ``LoopStatusReconciliationConfig``).
_STREAM_END = "soothe.stream.end"
_STRANGE_LOOP_COMPLETED = "soothe.cognition.strange_loop.completed"


async def drain_events(
    client: WebSocketClient,
    *,
    duration_s: float = 5.0,
    max_count: int = 30,
) -> list[dict[str, Any]]:
    """Collect inbound events for up to ``duration_s`` or ``max_count`` frames."""
    events: list[dict[str, Any]] = []
    deadline = time.monotonic() + duration_s
    while time.monotonic() < deadline and len(events) < max_count:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            event = await asyncio.wait_for(client.read_event(), timeout=min(1.0, remaining))
        except TimeoutError:
            continue
        if event is None:
            break
        events.append(event)
    return events


async def drain_until_turn_end(
    client: WebSocketClient,
    *,
    duration_s: float = 45.0,
    max_count: int = 80,
) -> list[dict[str, Any]]:
    """Drain the event stream until a turn-terminating frame arrives.

    A turn is considered terminated when the daemon emits a ``stream.end``
    or ``strange_loop.completed`` custom frame. This is the authoritative
    completion signal a client should observe — the loop metadata
    ``status`` field may remain ``running`` until a periodic reconciliation
    sweep demotes it to ``idle``.

    Args:
        client: Connected, handshaken WebSocketClient.
        duration_s: Maximum seconds to wait for the turn to end.
        max_count: Maximum number of frames to collect.

    Returns:
        All frames collected up to and including the terminating frame.
    """
    events: list[dict[str, Any]] = []
    deadline = time.monotonic() + duration_s
    while time.monotonic() < deadline and len(events) < max_count:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            event = await asyncio.wait_for(client.read_event(), timeout=min(1.5, remaining))
        except TimeoutError:
            continue
        if event is None:
            break
        events.append(event)
        if _is_turn_end(event):
            break
    return events


def _is_turn_end(event: dict[str, Any]) -> bool:
    """Return True when an event frame signals turn termination."""
    evt_type = event.get("type")
    if isinstance(evt_type, str) and evt_type in (_STREAM_END, _STRANGE_LOOP_COMPLETED):
        return True
    # Custom/turn-end frames carry the type in ``data.type``.
    data = event.get("data")
    if isinstance(data, dict):
        data_type = data.get("type")
        if isinstance(data_type, str) and data_type in (_STREAM_END, _STRANGE_LOOP_COMPLETED):
            return True
    return False


async def fetch_state_after_turn(
    client: WebSocketClient,
    loop_id: str,
    *,
    drain_timeout: float = 45.0,
) -> dict[str, Any]:
    """Drain the stream until the turn ends, then fetch the execution state.

    Completion is observed through the ``stream.end`` wire event (the
    authoritative signal), not by polling the loop metadata ``status``
    field — which stays ``running`` until a slow periodic reconciliation
    sweep demotes it to ``idle``.

    Args:
        client: Connected, handshaken WebSocketClient.
        loop_id: Target loop.
        drain_timeout: Maximum seconds to wait for the turn-end frame.

    Returns:
        The execution-state snapshot dict read after turn completion.
    """
    await drain_until_turn_end(client, duration_s=drain_timeout)
    return await fetch_execution_state(client, loop_id, timeout=30.0)


async def cancel_loop_best_effort(client: WebSocketClient, loop_id: str) -> None:
    """Best-effort cancel so crash/reattach tests do not leave a busy worker.

    Transport-drop tests deliberately close the client mid-turn. Cancel the
    loop afterward so the live daemon is not left running an orphaned execute.
    Never stops or kills the daemon process itself.
    """
    lid = (loop_id or "").strip()
    if not lid or not client.is_connected:
        return
    with contextlib.suppress(Exception):
        await client.send(
            {"type": "command_request", "command": "cancel", "loop_id": lid}
        )
