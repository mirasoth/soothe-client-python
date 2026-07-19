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

TURN_END_STREAM_END = STREAM_END
TURN_END_IDLE = "status.idle"
TURN_END_STOPPED = "status.stopped"


@dataclass
class TurnLifecycleGate:
    """Per-turn progress flags (DaemonSession parity; not shared across chats)."""

    saw_running: bool = False
    saw_stream_payload: bool = False
    saw_turn_progress: bool = False

    def observe(self, msg: Any) -> None:
        frame = _normalize_frame(msg)
        if frame is None:
            return
        typ = str(frame.get("type") or "")
        if typ == "status":
            if str(frame.get("state") or "").strip().lower() == "running":
                self.saw_running = True
            return
        if typ == "event":
            self.saw_stream_payload = True
            mode = str(frame.get("mode") or "")
            if is_turn_progress_chunk(mode, frame.get("data")):
                self.saw_turn_progress = True

    def allow_stream_end(self) -> bool:
        return self.saw_running and self.saw_turn_progress

    def allow_idle_complete(self) -> bool:
        return self.saw_running and self.saw_stream_payload


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
            if state == "stopped" and self.gate.saw_running:
                return self._mark(TURN_END_STOPPED)
            if state == "idle" and self.gate.allow_idle_complete():
                return self._mark(TURN_END_IDLE)
            return False, ""

        if typ == "event":
            mode = str(frame.get("mode") or "")
            data = frame.get("data")
            if mode == "custom" and is_turn_end_custom_data(data) and self.gate.allow_stream_end():
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
            return {
                "type": "event",
                "mode": inner.get("mode"),
                "data": inner.get("data"),
                "namespace": inner.get("namespace") or payload.get("namespace"),
            }
        mode = payload.get("mode")
        if mode:
            return {
                "type": "event",
                "mode": mode,
                "data": payload.get("data"),
                "namespace": payload.get("namespace"),
            }
        return None
    return msg
