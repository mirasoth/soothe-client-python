"""Single-flight query gate."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

SendCancelFn = Callable[[], Awaitable[None] | None]


class ErrQueryBusy(Exception):  # noqa: N818 — match Go/TS `ErrQueryBusy` name
    """Raised when a session already has an in-flight query."""

    def __init__(self) -> None:
        super().__init__("appkit: query already in progress for session")


class QueryGate:
    """Enforce single-flight query execution per session id.

    Cancel ordering: daemon cancel (detached timeout) runs before the local
    cancel callback, matching Go/TS appkit semantics.
    """

    def __init__(self, *, cancel_timeout_s: float = 10.0) -> None:
        self._lock = asyncio.Lock()
        self._cancels: dict[str, Callable[[], None]] = {}
        self._send_cancels: dict[str, SendCancelFn] = {}
        self._cancel_timeout_s = cancel_timeout_s

    async def acquire(
        self,
        session_id: str,
        cancel: Callable[[], None],
        send_cancel: SendCancelFn | None = None,
    ) -> None:
        """Reserve ``session_id`` for one agent turn.

        Args:
            session_id: Application session key (often the loop id).
            cancel: Local cancel callback (e.g. set an Event / cancel a task).
            send_cancel: Optional async daemon-cancel sender.

        Raises:
            ErrQueryBusy: A query is already in flight for ``session_id``.
        """
        async with self._lock:
            if session_id in self._cancels:
                raise ErrQueryBusy()
            self._cancels[session_id] = cancel
            if send_cancel is not None:
                self._send_cancels[session_id] = send_cancel

    async def cancel(self, session_id: str) -> None:
        """Stop an in-flight query: daemon cancel first, then local cancel."""
        async with self._lock:
            cancel = self._cancels.pop(session_id, None)
            send_cancel = self._send_cancels.pop(session_id, None)

        if cancel is None and send_cancel is None:
            return

        if send_cancel is not None:
            try:
                await asyncio.wait_for(
                    _await_maybe(send_cancel()),
                    timeout=self._cancel_timeout_s,
                )
            except Exception:  # noqa: BLE001 — proceed to local cancel
                pass

        if cancel is not None:
            cancel()

    async def release(self, session_id: str) -> None:
        """Clear the gate without sending a daemon cancel."""
        async with self._lock:
            self._cancels.pop(session_id, None)
            self._send_cancels.pop(session_id, None)

    async def is_active(self, session_id: str) -> bool:
        """Return whether a query is in flight for ``session_id``."""
        async with self._lock:
            return session_id in self._cancels


async def _await_maybe(result: Any) -> None:
    if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
        await result  # type: ignore[misc]


__all__ = ["ErrQueryBusy", "QueryGate"]
