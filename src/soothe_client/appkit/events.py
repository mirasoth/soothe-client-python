"""Protocol-1 streaming frame helpers for application loops."""

from __future__ import annotations

from typing import Any


def unwrap_next(event: dict[str, Any] | None) -> dict[str, Any] | None:
    """Unwrap a protocol-1 ``next`` envelope to its inner streaming frame.

    Under protocol-1 the daemon wraps free-form streaming frames
    (``event`` / ``command_response`` / card replay) in a
    ``{proto, type:"next", payload:{namespace, mode, data}}`` envelope. This
    helper returns the inner ``data`` dict (the legacy frame) so turn loops
    can branch on the same fields as before the migration.

    ``status`` / ``error`` / ``response`` / ``complete`` are sent raw and pass
    through unchanged.

    Args:
        event: A raw wire frame as returned by ``client.read_event()``.

    Returns:
        The inner ``payload.data`` dict for ``next`` envelopes, the original
        frame otherwise, or ``None`` if ``event`` is ``None``.
    """
    if not isinstance(event, dict):
        return event
    if event.get("type") != "next":
        return event
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return event
    data = payload.get("data")
    return data if isinstance(data, dict) else event


def is_loop_scoped_event(event: dict[str, Any], *, active_loop_id: str) -> bool:
    """Return whether a daemon frame belongs to the active StrangeLoop session.

    Unwraps protocol-1 ``next`` envelopes first, then checks ``loop_id`` on the
    inner streaming frame. Non-scoped types (``response``, ``error``,
    ``complete``, etc.) are always considered in-scope.

    Args:
        event: Raw or already-unwrapped wire frame.
        active_loop_id: Loop id for the in-flight session.

    Returns:
        True when the frame should be processed for ``active_loop_id``.
    """
    event_type = event.get("type", "")
    if event_type == "next":
        inner = unwrap_next(event)
        if isinstance(inner, dict):
            event_type = inner.get("type", "")
            return event_type not in {"status", "event"} or (inner.get("loop_id") == active_loop_id)
    if event_type not in {"status", "event"}:
        return True
    return event.get("loop_id") == active_loop_id


__all__ = ["is_loop_scoped_event", "unwrap_next"]
