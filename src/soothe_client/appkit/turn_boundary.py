"""DaemonSession turn-end contract for the pool TurnRunner path.

TurnRunner owns one ``TurnBoundary`` per Execute. EventClassifier may
early-complete on deliverable phases for UX; it is not the sole terminator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from soothe_client.stream_terminal import (
    STREAM_END,
    is_turn_end_custom_data,
    is_turn_progress_chunk,
)
from soothe_client.turn_boundary import (
    frame_turn_id,
    is_idle_terminal_allowed,
    is_turn_terminal_allowed,
    parse_turn_generation,
    turn_ids_match,
)

TURN_END_STREAM_END = STREAM_END
TURN_END_IDLE = "status.idle"
TURN_END_STOPPED = "status.stopped"


@dataclass
class TurnLifecycleGate:
    """Per-turn progress flags (DaemonSession parity; not shared across chats)."""

    saw_running: bool = False
    saw_turn_progress: bool = False
    expected_turn_id: str | None = None
    cancellation_seen: bool = False

    def observe(self, msg: Any) -> None:
        frame = _normalize_frame(msg)
        if frame is None:
            return
        typ = str(frame.get("type") or "")
        if typ == "status":
            if str(frame.get("state") or "").strip().lower() == "running":
                self.saw_running = True
                status_turn = frame_turn_id(frame)
                if status_turn:
                    new_gen = parse_turn_generation(status_turn)
                    old_gen = parse_turn_generation(self.expected_turn_id)
                    if self.expected_turn_id is None or (
                        new_gen is not None and (old_gen is None or new_gen >= old_gen)
                    ):
                        if self.expected_turn_id and status_turn != self.expected_turn_id:
                            self.saw_turn_progress = False
                        self.expected_turn_id = status_turn
            return
        if typ == "event":
            mode = str(frame.get("mode") or "")
            if is_turn_progress_chunk(mode, frame.get("data")):
                self.saw_turn_progress = True

    def allow_stream_end(self, frame_turn: str | None) -> bool:
        return is_turn_terminal_allowed(
            expected_turn_id=self.expected_turn_id,
            frame_turn_id=frame_turn,
            query_started=self.saw_running,
            turn_progress_seen=self.saw_turn_progress,
        )

    def allow_idle_complete(self, frame_turn: str | None) -> bool:
        return is_idle_terminal_allowed(
            expected_turn_id=self.expected_turn_id,
            frame_turn_id=frame_turn,
            query_started=self.saw_running,
            turn_progress_seen=self.saw_turn_progress,
            cancellation_seen=self.cancellation_seen,
        )


@dataclass
class TurnBoundary:
    """Applies DaemonSession end rules to pool decoded frames."""

    gate: TurnLifecycleGate = field(default_factory=TurnLifecycleGate)
    ended: bool = False
    reason: str = ""

    def feed(self, msg: Any) -> tuple[bool, str]:
        if self.ended:
            return True, self.reason
        self.gate.observe(msg)
        frame = _normalize_frame(msg)
        if frame is None:
            return False, ""

        typ = str(frame.get("type") or "")
        if typ == "status":
            state = str(frame.get("state") or "").strip().lower()
            frame_turn = frame_turn_id(frame)
            if state == "stopped" and self.gate.saw_running:
                if self.gate.expected_turn_id and not turn_ids_match(
                    self.gate.expected_turn_id, frame_turn
                ):
                    return False, ""
                return self._mark(TURN_END_STOPPED)
            if state == "idle" and self.gate.allow_idle_complete(frame_turn):
                return self._mark(TURN_END_IDLE)
            return False, ""

        if typ == "event":
            mode = str(frame.get("mode") or "")
            data = frame.get("data")
            data_turn = frame_turn_id(data if isinstance(data, dict) else None) or frame_turn_id(
                frame
            )
            if (
                mode == "custom"
                and is_turn_end_custom_data(data)
                and self.gate.allow_stream_end(data_turn)
            ):
                return self._mark(TURN_END_STREAM_END)
        return False, ""

    def _mark(self, reason: str) -> tuple[bool, str]:
        self.ended = True
        self.reason = reason
        return True, reason


def is_daemon_turn_end_event(completion_event: str) -> bool:
    """True for TurnBoundary completion_event values (not phase deliverables)."""
    return (completion_event or "").strip() in {
        TURN_END_STREAM_END,
        TURN_END_IDLE,
        TURN_END_STOPPED,
    }


def _normalize_frame(msg: Any) -> dict[str, Any] | None:
    if not isinstance(msg, dict):
        return None
    typ = msg.get("type")
    if typ == "next":
        payload = msg.get("payload")
        if not isinstance(payload, dict):
            return None
        inner = payload.get("data")
        if isinstance(inner, dict) and inner.get("type") == "status":
            return inner
        if isinstance(inner, dict) and inner.get("mode"):
            out = {
                "type": "event",
                "mode": inner.get("mode"),
                "data": inner.get("data"),
                "namespace": inner.get("namespace") or payload.get("namespace"),
            }
            tid = inner.get("turn_id") or payload.get("turn_id") or msg.get("turn_id")
            if tid:
                out["turn_id"] = tid
            return out
        mode = payload.get("mode")
        if mode:
            out = {
                "type": "event",
                "mode": mode,
                "data": payload.get("data"),
                "namespace": payload.get("namespace"),
            }
            tid = payload.get("turn_id") or msg.get("turn_id")
            if tid:
                out["turn_id"] = tid
            return out
        return None
    return msg
