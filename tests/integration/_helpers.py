"""Shared helpers for live-daemon integration tests."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from soothe_client import WebSocketClient


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
