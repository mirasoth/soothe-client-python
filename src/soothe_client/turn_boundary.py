"""Internal turn / stream boundary helpers.

Used by ``DaemonSession`` and ``WebSocketClient`` for ``turn_id`` / ``seq``
filtering. Not part of the community public API — import only if you are
extending stream handling.
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


def parse_turn_generation(turn_id: str | None) -> int | None:
    """Extract generation int from ``turn_id``, or None if malformed."""
    raw = str(turn_id or "").strip()
    if not raw or ":" not in raw:
        return None
    suffix = raw.rsplit(":", 1)[-1]
    try:
        gen = int(suffix)
    except ValueError:
        return None
    return gen if gen > 0 else None


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


def turn_ids_match(expected: str | None, candidate: str | None) -> bool:
    """True when both ids are non-empty and equal.

    Absent ids never match — callers must not treat missing ``turn_id`` as
    compatible with a bound turn (prior-goal terminals / idle can omit or
    carry a stale generation).
    """
    exp = str(expected or "").strip()
    cand = str(candidate or "").strip()
    return bool(exp) and bool(cand) and exp == cand


def is_turn_terminal_allowed(
    *,
    expected_turn_id: str | None,
    frame_turn_id: str | None,
    query_started: bool,
    turn_progress_seen: bool,
) -> bool:
    """Gate for turn-scoped ``stream.end`` / ``strange_loop.completed``.

    Requires an active query, real turn progress, a bound ``expected_turn_id``,
    and an exact ``frame_turn_id`` match. Absent ids are rejected.
    """
    if not query_started or not turn_progress_seen:
        return False
    return turn_ids_match(expected_turn_id, frame_turn_id)


def is_idle_terminal_allowed(
    *,
    expected_turn_id: str | None,
    frame_turn_id: str | None,
    query_started: bool,
    turn_progress_seen: bool,
    cancellation_seen: bool = False,
) -> bool:
    """Gate for ``status=idle`` soft-complete.

    Requires a bound turn. Matching ``turn_id`` needs progress or cancel.
    Absent idle ``turn_id`` is allowed only when cancellation was already seen
    (legacy cancel finalize); mismatched ids are always rejected.
    """
    if not query_started or not str(expected_turn_id or "").strip():
        return False
    cand = str(frame_turn_id or "").strip()
    if cand:
        if not turn_ids_match(expected_turn_id, cand):
            return False
        return bool(turn_progress_seen or cancellation_seen)
    # Absent idle turn_id: never end a healthy turn; cancel path only.
    return bool(cancellation_seen)


__all__ = [
    "format_turn_id",
    "frame_seq",
    "frame_turn_id",
    "is_idle_terminal_allowed",
    "is_turn_terminal_allowed",
    "parse_turn_generation",
    "turn_ids_match",
]
