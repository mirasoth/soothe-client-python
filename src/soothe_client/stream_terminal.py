"""Shared stream/turn terminal frame helpers for WebSocket and DaemonSession.

Keeps peel-at-turn-start and turn-end detection on one vocabulary so leftover
prior-goal terminals cannot blank the next TUI query.
"""

from __future__ import annotations

from typing import Any, TypeGuard

from soothe_sdk.core.events import (
    PLAN_CREATED,
    STRANGE_LOOP_COMPLETED,
    STRANGE_LOOP_STEP_COMPLETED,
    STRANGE_LOOP_STEP_QUEUED,
    STRANGE_LOOP_STEP_STARTED,
    STREAM_END,
)

TURN_END_CUSTOM_TYPES = frozenset({STREAM_END, STRANGE_LOOP_COMPLETED})

# Customs that prove this turn has real work (not mere intake plan.phase).
# Intake-only phases must not unlock turn-end — prior-goal stream.end can still
# arrive after status=running (loop 3e43).
_TURN_PROGRESS_CUSTOM_TYPES = frozenset(
    {
        PLAN_CREATED,
        STRANGE_LOOP_STEP_STARTED,
        STRANGE_LOOP_STEP_QUEUED,
        STRANGE_LOOP_STEP_COMPLETED,
    }
)

# Handshake / card-replay / subscription leftovers safe to drop at turn start.
STALE_TURN_PENDING_TYPES = frozenset(
    {
        "connection_ack",
        "card.replay_begin",
        "card.replay_end",
        "card.created",
        "complete",
    }
)


def is_turn_end_custom_data(data: Any) -> TypeGuard[dict[str, Any]]:
    """True when ``data`` is a turn-scoped terminal custom payload."""
    if not isinstance(data, dict):
        return False
    custom_type = str(data.get("type", "")).strip()
    if custom_type not in TURN_END_CUSTOM_TYPES:
        return False
    if custom_type == STREAM_END:
        scope = str(data.get("scope") or "turn").strip().lower()
        return scope in {"", "turn"}
    return True


def is_turn_progress_chunk(mode: str, data: Any) -> bool:
    """True when a chunk proves the active turn has non-intake progress.

    Used so late prior-goal ``stream.end`` cannot close a turn that has only
    seen intake lifecycle (e.g. plan.phase "Interpreting goal").
    """
    if mode in {"messages", "updates"}:
        return True
    if mode != "custom" or not isinstance(data, dict):
        return False
    if is_turn_end_custom_data(data):
        return False
    custom_type = str(data.get("type", "")).strip()
    if custom_type in _TURN_PROGRESS_CUSTOM_TYPES:
        return True
    if custom_type.startswith("soothe.cognition.strange_loop.step"):
        return True
    return False


def stale_pending_frame_label(event: dict[str, Any]) -> str | None:
    """Return a peel label when ``event`` is safe to drop at turn start."""
    event_type = str(event.get("type") or "")
    if event_type in STALE_TURN_PENDING_TYPES:
        return event_type

    if event_type == "next":
        payload = event.get("payload")
        if not isinstance(payload, dict):
            return None
        stale_mode = str(payload.get("mode") or "")
        if stale_mode in STALE_TURN_PENDING_TYPES:
            return stale_mode
        inner = payload.get("data")
        if isinstance(inner, dict):
            return stale_pending_frame_label(inner)
        return None

    if event_type == "event":
        mode = str(event.get("mode") or "")
        data = event.get("data")
        if mode == "custom" and is_turn_end_custom_data(data):
            return str(data.get("type") or "").strip()
    return None


__all__ = [
    "STALE_TURN_PENDING_TYPES",
    "STREAM_END",
    "STRANGE_LOOP_COMPLETED",
    "TURN_END_CUSTOM_TYPES",
    "is_turn_end_custom_data",
    "is_turn_progress_chunk",
    "stale_pending_frame_label",
]
