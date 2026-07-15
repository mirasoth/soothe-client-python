"""Client-facing error types for soothe-client-python."""

from __future__ import annotations

from enum import IntEnum
from typing import Any


class DisconnectCause(IntEnum):
    """Distinguishes clean vs unclean connection loss."""

    UNCLEAN = 0
    CLEAN = 1


def disconnect_cause_name(cause: DisconnectCause) -> str:
    """Human-readable cause name for logging."""
    return "clean" if cause == DisconnectCause.CLEAN else "unclean"


class DaemonError(Exception):
    """Error reported by the daemon (protocol-1 structured error object)."""

    def __init__(
        self,
        code: int,
        message: str,
        data: Any | None = None,
    ) -> None:
        super().__init__(f"daemon error [{code}]: {message}")
        self.code = code
        self.daemon_message = message
        self.data = data


class StaleLoopError(Exception):
    """Loop accepted reattach but failed the ``loop_get`` liveness probe."""

    def __init__(self, loop_id: str, cause: BaseException | None = None) -> None:
        detail = f": {cause}" if cause is not None else ""
        super().__init__(
            f"stale loop {loop_id}: reattach accepted but liveness probe failed{detail}"
        )
        self.loop_id = loop_id
        self.cause = cause


class ReconnectError(Exception):
    """Bounded reconnect attempts exhausted."""

    def __init__(self, url: str, attempts: int, cause: BaseException | None = None) -> None:
        detail = f": {cause}" if cause is not None else ""
        super().__init__(f"reconnect to {url} failed after {attempts} attempts{detail}")
        self.url = url
        self.attempts = attempts
        self.cause = cause


__all__ = [
    "DaemonError",
    "DisconnectCause",
    "ReconnectError",
    "StaleLoopError",
    "disconnect_cause_name",
]
