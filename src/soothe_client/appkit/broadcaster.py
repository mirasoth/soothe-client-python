"""SSE-style pub/sub fan-out for appkit (RFC-629 Layer 1).

Generic, string-keyed pub/sub for SSE-style event delivery. Slow consumers do
not stall the broadcaster: each subscriber has a bounded queue and overflowing
events are dropped (drop-on-full).
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

SUBSCRIBER_QUEUE_CAP = 100


@dataclass(frozen=True, slots=True)
class SSEEvent:
    """One Server-Sent Event payload. The ``type`` vocabulary is app-defined."""

    type: str
    data: Any = None


@dataclass
class _Subscriber:
    queue: asyncio.Queue[SSEEvent | None] = field(
        default_factory=lambda: asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_CAP)
    )
    closed: bool = False


class SSEBroadcaster:
    """Fan events out to all subscribers for a session id (non-blocking)."""

    def __init__(self) -> None:
        self._subscribers: dict[str, dict[str, _Subscriber]] = {}

    def subscribe(self, session_id: str) -> tuple[AsyncIterator[SSEEvent], str]:
        """Register a subscriber and return ``(async iterator, subscription id)``.

        Unsubscribe via ``unsubscribe`` or ``close``.
        """
        sub_id = str(uuid4())
        sub = _Subscriber()
        subs = self._subscribers.get(session_id)
        if subs is None:
            subs = {}
            self._subscribers[session_id] = subs
        subs[sub_id] = sub
        return _iterate(sub), sub_id

    def unsubscribe(self, session_id: str, sub_id: str) -> None:
        """Remove a subscriber by id and close its iterator. Safe if unknown."""
        subs = self._subscribers.get(session_id)
        if not subs:
            return
        sub = subs.pop(sub_id, None)
        if sub is None:
            return
        self._close_sub(sub)
        if not subs:
            del self._subscribers[session_id]

    def broadcast(self, session_id: str, event: SSEEvent) -> None:
        """Send an event to all subscribers (drop-on-full, non-blocking)."""
        subs = self._subscribers.get(session_id)
        if not subs:
            return
        for sub in subs.values():
            if sub.closed:
                continue
            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # drop-on-full

    def close(self, session_id: str) -> None:
        """Close all subscribers for a session id and remove the entry."""
        subs = self._subscribers.pop(session_id, None)
        if not subs:
            return
        for sub in subs.values():
            self._close_sub(sub)

    def close_all(self) -> None:
        """Close every subscriber channel across all sessions."""
        for session_id in list(self._subscribers):
            self.close(session_id)

    @staticmethod
    def _close_sub(sub: _Subscriber) -> None:
        if sub.closed:
            return
        sub.closed = True
        try:
            sub.queue.put_nowait(None)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                sub.queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                sub.queue.put_nowait(None)


async def _iterate(sub: _Subscriber) -> AsyncIterator[SSEEvent]:
    while True:
        item = await sub.queue.get()
        if item is None:
            return
        yield item


__all__ = ["SSEEvent", "SSEBroadcaster", "SUBSCRIBER_QUEUE_CAP"]
