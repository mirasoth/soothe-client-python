"""Persistence seam for appkit."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class SessionEntry:
    """Persisted mapping between an application session id and a daemon loop id."""

    __slots__ = (
        "workspace_id",
        "session_id",
        "loop_id",
        "session_type",
        "purpose",
        "is_active",
        "reset_count",
        "last_used_at",
    )

    def __init__(
        self,
        *,
        workspace_id: str,
        session_id: str,
        loop_id: str,
        session_type: str,
        purpose: str | None = None,
        is_active: bool = True,
        reset_count: int = 0,
        last_used_at: float = 0.0,
    ) -> None:
        self.workspace_id = workspace_id
        self.session_id = session_id
        self.loop_id = loop_id
        self.session_type = session_type
        self.purpose = purpose
        self.is_active = is_active
        self.reset_count = reset_count
        self.last_used_at = last_used_at


class SessionMessage:
    """A persisted message row (assistant reply or error)."""

    __slots__ = ("id", "role", "content", "context", "metadata")

    def __init__(
        self,
        *,
        role: str,
        content: str,
        id: str | None = None,  # noqa: A002
        context: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.id = id
        self.role = role
        self.content = content
        self.context = context
        self.metadata = metadata


@runtime_checkable
class SessionStore(Protocol):
    """Persistence seam between appkit and the application's storage backend."""

    async def get_session(self, session_id: str) -> SessionEntry | None:
        """Return the persisted entry for ``session_id``, or None."""
        ...

    async def create_session(
        self,
        workspace_id: str,
        session_id: str,
        loop_id: str,
        session_type: str,
    ) -> None:
        """Persist a new session↔loop mapping."""
        ...

    async def update_last_used(self, session_id: str) -> None:
        """Stamp the session's last-used timestamp."""
        ...

    async def increment_reset_count(self, session_id: str) -> None:
        """Bump the reset counter (fresh bootstrap vs reattach)."""
        ...

    async def get_loop_id_for_session(self, session_id: str) -> tuple[str, bool]:
        """Return ``(loop_id, ok)``; ``ok is False`` triggers fresh ``loop_new``."""
        ...

    async def append_message(self, session_id: str, message: SessionMessage) -> None:
        """Write a message row for the session."""
        ...


__all__ = ["SessionEntry", "SessionMessage", "SessionStore"]
