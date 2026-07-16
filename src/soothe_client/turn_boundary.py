"""Turn / stream boundary helpers (IG-659).

``turn_id`` correlates a user turn across status, events, and terminals.
``seq`` is a daemon-assigned monotonic counter per loop for drop-stale filtering.
"""

from __future__ import annotations

from typing import Any


def format_turn_id(loop_id: str, generation: int) -> str:
    """Return wire ``turn_id`` for ``loop_id`` + admit generation."""
    lid = str(loop_id or "").strip()
    gen = int(generation)
    if not lid or gen <= 0:
        return ""
    return f"{lid}:{gen}"


def frame_turn_id(frame: dict[str, Any] | None) -> str | None:
    """Return ``turn_id`` from a status/event frame or nested custom data."""
    if not isinstance(frame, dict):
        return None
    tid = frame.get("turn_id")
    if isinstance(tid, str) and tid.strip():
        return tid.strip()
    data = frame.get("data")
    if isinstance(data, dict):
        inner = data.get("turn_id")
        if isinstance(inner, str) and inner.strip():
            return inner.strip()
    return None


def frame_seq(frame: dict[str, Any] | None) -> int | None:
    """Return non-negative ``seq`` from a wire frame, or None."""
    if not isinstance(frame, dict):
        return None
    raw = frame.get("seq")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int) and raw >= 0:
        return raw
    if isinstance(raw, float) and raw >= 0 and raw == int(raw):
        return int(raw)
    return None


__all__ = [
    "format_turn_id",
    "frame_seq",
    "frame_turn_id",
]
