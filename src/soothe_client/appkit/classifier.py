"""Event classifier for appkit.

Maps a stream of decoded daemon events into deliverable/streaming/terminal
outcomes, keyed on (namespace, mode, phase). Product apps pass their own
``deliverable_phases`` set; appkit stays product-agnostic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from soothe_client.appkit.thinking_step import extract_thinking_step
from soothe_client.errors import DaemonError

EVENT_FINAL_REPORT = "soothe.output.autonomous.final_report.reported"
EVENT_LOOP_HISTORY_REPLAYED = "soothe.lifecycle.loop.history.replayed"


class ChatEventTerminal(IntEnum):
    """How a processed event should end the query loop."""

    CONTINUE = 0
    DELIVERABLE_COMPLETE = 1
    FAILED_COMPLETE = 2


@dataclass(slots=True)
class ChatEventResult:
    """Structured outcome of classifying one daemon event."""

    terminal: ChatEventTerminal
    content: str | None = None
    thinking_step: str | None = None
    completion_event: str | None = None
    err: BaseException | None = None


@dataclass(frozen=True, slots=True)
class ClassifierConfig:
    """Product-specific decisions an ``EventClassifier`` needs.

    Attributes:
        deliverable_phases: Message ``phase`` values that may end a query with
            user-facing text. Required.
        min_deliverable_runes: Minimum trimmed rune count for a reply to be
            persisted as final (avoids finishing on stub ACKs). Defaults to 8.
        thinking_step_events: Optional override of the default thinking-step
            event allowlist.
        treat_status_idle_as_complete: Standalone ``classify`` only. Prefer
            ``TurnRunner`` + ``TurnBoundary`` for turn end (DaemonSession
            contract). Default false.
    """

    deliverable_phases: frozenset[str] | set[str]
    min_deliverable_runes: int = 8
    thinking_step_events: frozenset[str] | set[str] | None = None
    treat_status_idle_as_complete: bool = False


class EventClassifier:
    """Map decoded daemon events into deliverable/streaming/terminal outcomes."""

    def __init__(self, cfg: ClassifierConfig) -> None:
        if not cfg.deliverable_phases:
            raise ValueError("ClassifierConfig.deliverable_phases must not be empty")
        self._deliverable_phases = frozenset(cfg.deliverable_phases)
        self._min_deliverable_runes = (
            cfg.min_deliverable_runes if cfg.min_deliverable_runes > 0 else 8
        )
        self._thinking_step_events = (
            frozenset(cfg.thinking_step_events) if cfg.thinking_step_events is not None else None
        )
        self._treat_status_idle_as_complete = cfg.treat_status_idle_as_complete

    def classify(self, msg: Any, accumulated: str = "") -> ChatEventResult:
        """Inspect one decoded event and return its outcome."""
        return self._process_chat_event(msg, accumulated)

    def is_deliverable_completion_event(self, event_type: str) -> bool:
        """Report whether a persisted completion_event is user-facing."""
        if not event_type:
            return False
        if event_type in (
            "status.idle",
            "status.stopped",
            "soothe.stream.end",
            "idle_timeout",
            "query_timeout",
            "stream_closed",
        ):
            return True
        if event_type == EVENT_FINAL_REPORT:
            return True
        prefix = "soothe.protocol.message."
        if event_type.startswith(prefix):
            return self.is_deliverable_loop_phase(event_type[len(prefix) :])
        return "soothe.output" in event_type and "responded" in event_type

    def is_deliverable_loop_phase(self, phase: str) -> bool:
        """Return whether ``phase`` is in the configured deliverable set."""
        return phase in self._deliverable_phases

    def is_substantive_assistant_reply(self, content: str) -> bool:
        """Report whether trimmed assistant text is long enough to persist."""
        return len(list(content.strip())) >= self._min_deliverable_runes

    def resolve_deliverable_final_content(
        self,
        event_result: ChatEventResult,
        _accumulated: str = "",
    ) -> tuple[str, bool]:
        """Pick the user-visible reply for a completed query."""
        if event_result.terminal != ChatEventTerminal.DELIVERABLE_COMPLETE:
            return "", False
        if not self.is_deliverable_completion_event(event_result.completion_event or ""):
            return "", False
        final = (event_result.content or "").strip()
        if final:
            return final, True
        return "", False

    def _deliverable_result(self, content: str, completion_event: str) -> ChatEventResult:
        return ChatEventResult(
            terminal=ChatEventTerminal.DELIVERABLE_COMPLETE,
            content=content,
            completion_event=completion_event,
        )

    def _continue_result(self, content: str) -> ChatEventResult:
        return ChatEventResult(terminal=ChatEventTerminal.CONTINUE, content=content)

    def _failed_result(self, err: BaseException) -> ChatEventResult:
        return ChatEventResult(terminal=ChatEventTerminal.FAILED_COMPLETE, err=err)

    def _process_chat_event(self, msg: Any, accumulated: str) -> ChatEventResult:
        if not isinstance(msg, dict):
            return ChatEventResult(terminal=ChatEventTerminal.CONTINUE)

        typ = msg.get("type")
        if typ == "next":
            return self._classify_next_envelope(msg)

        if typ in ("response", "complete", "receipt_response", "connection_ack"):
            return ChatEventResult(terminal=ChatEventTerminal.CONTINUE)

        if typ == "status":
            state = str(msg.get("state") or "").strip().lower()
            if (
                self._treat_status_idle_as_complete
                and state == "idle"
                and self.is_substantive_assistant_reply(accumulated)
            ):
                return self._deliverable_result(accumulated.strip(), "status.idle")
            return ChatEventResult(terminal=ChatEventTerminal.CONTINUE)

        if typ == "error":
            raw_err = msg.get("error")
            err_obj: dict[str, Any] = raw_err if isinstance(raw_err, dict) else {}
            raw_code = err_obj.get("code")
            code = raw_code if isinstance(raw_code, int) else -32603
            raw_message = err_obj.get("message")
            message = raw_message if isinstance(raw_message, str) else "daemon error"
            return self._failed_result(DaemonError(code, message, err_obj.get("data")))

        if typ == "event":
            return self._classify_event_payload(
                msg.get("namespace"),
                str(msg.get("mode") or ""),
                msg.get("data"),
            )

        return ChatEventResult(terminal=ChatEventTerminal.CONTINUE)

    def _classify_next_envelope(self, env: dict[str, Any]) -> ChatEventResult:
        raw_payload = env.get("payload")
        payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
        raw_inner = payload.get("data")
        inner_data: dict[str, Any] | None = raw_inner if isinstance(raw_inner, dict) else None
        if inner_data is not None:
            inner_mode = str(inner_data.get("mode") or "")
            if inner_mode:
                return self._classify_event_payload(
                    inner_data.get("namespace", payload.get("namespace")),
                    inner_mode,
                    inner_data.get("data"),
                )
        mode = str(payload.get("mode") or "")
        if mode:
            return self._classify_event_payload(
                payload.get("namespace"),
                mode,
                payload.get("data"),
            )
        return ChatEventResult(terminal=ChatEventTerminal.CONTINUE)

    def _classify_event_payload(
        self,
        namespace: Any,
        mode: str,
        data: Any,
    ) -> ChatEventResult:
        ns = _namespace_to_string(namespace)
        data_map = _normalize_event_data(data)

        if data_map is not None:
            data_type = ns
            dt = data_map.get("type")
            if isinstance(dt, str) and dt:
                data_type = dt
            if data_type == EVENT_LOOP_HISTORY_REPLAYED:
                return ChatEventResult(terminal=ChatEventTerminal.CONTINUE)
            step, ok = extract_thinking_step(
                data_type,
                data_map,
                self._thinking_step_events,
            )
            if ok:
                return ChatEventResult(
                    terminal=ChatEventTerminal.CONTINUE,
                    thinking_step=step,
                )

        if mode == "messages":
            result = self._classify_messages_mode(data, ns)
            if result is not None:
                return result

        if data_map is None:
            return ChatEventResult(terminal=ChatEventTerminal.CONTINUE)

        data_type = ns
        dt = data_map.get("type")
        if isinstance(dt, str) and dt:
            data_type = dt
        completion_event = data_type or ns

        if _is_namespace_match(ns, data_type, "soothe.output") or _is_namespace_match(
            ns, data_type, "responded"
        ):
            content, ok = _extract_content_from_data(data_map)
            if ok:
                if self._is_final_output_event(data_type, ns):
                    return self._deliverable_result(content, completion_event)
                return self._continue_result(content)

        if (
            _is_namespace_match(ns, data_type, "agent_loop.completed")
            or _is_namespace_match(ns, data_type, "agent_loop.reasoned")
            or _is_namespace_match(ns, data_type, "loop.completed")
        ):
            content, ok = _extract_content_from_data(data_map)
            if ok:
                return self._continue_result(content)

        if _is_namespace_match(ns, data_type, "final_report"):
            content, ok = _extract_content_from_data(data_map)
            if ok:
                return self._deliverable_result(content, completion_event)

        if "soothe.error." in data_type or "soothe.error." in ns:
            err_type = data_type or ns
            msg = data_map.get("message")
            if isinstance(msg, str) and msg:
                return self._failed_result(RuntimeError(f"{err_type}: {msg}"))
            content, ok = _extract_content_from_data(data_map)
            if ok:
                return self._failed_result(RuntimeError(f"{err_type}: {content}"))
            return self._failed_result(RuntimeError(err_type))

        if (
            _is_namespace_match(ns, data_type, "stream")
            or _is_namespace_match(ns, data_type, "progress")
            or _is_namespace_match(ns, data_type, "tool_call_updates_batch")
            or _is_namespace_match(ns, data_type, "soothe.stream.tool_call.update")
        ):
            delta = data_map.get("delta")
            if isinstance(delta, str):
                return self._continue_result(delta)

        if (
            _is_namespace_match(ns, data_type, "heartbeat")
            or _is_namespace_match(ns, data_type, "system.daemon")
            or _is_namespace_match(ns, data_type, "agent_loop.started")
            or _is_namespace_match(ns, data_type, "intent.classified")
        ):
            return ChatEventResult(terminal=ChatEventTerminal.CONTINUE)

        return ChatEventResult(terminal=ChatEventTerminal.CONTINUE)

    def _classify_messages_mode(self, data: Any, _ns: str) -> ChatEventResult | None:
        if not isinstance(data, list) or not data:
            return None
        first = data[0]
        if not isinstance(first, dict):
            return None

        msg_type, raw_content, phase, has_payload = _first_message_payload(data)
        if has_payload and raw_content and _is_streaming_message_type(msg_type):
            return self._continue_result(raw_content)

        loop_msg = _loop_ai_message(data)
        if loop_msg is not None:
            content = loop_msg["content"]
            if content:
                if _is_streaming_message_type(loop_msg["type"]):
                    return self._continue_result(content)
                if self.is_deliverable_loop_phase(loop_msg["phase"]) and (
                    self.is_substantive_assistant_reply(content)
                ):
                    return self._deliverable_result(
                        content,
                        f"soothe.protocol.message.{loop_msg['phase']}",
                    )
                return self._continue_result(content)

        # Unphased terminal AI text is streamable narration only.
        unphased_content, unphased_ok = self._messages_mode_assistant_content(data)
        if unphased_ok:
            return self._continue_result(unphased_content)

        if has_payload and raw_content:
            if _is_terminal_message_type(msg_type) or msg_type == "":
                if self.is_deliverable_loop_phase(phase) and self.is_substantive_assistant_reply(
                    raw_content
                ):
                    return self._deliverable_result(
                        raw_content,
                        f"soothe.protocol.message.{phase}",
                    )
                return self._continue_result(raw_content)
            return self._continue_result(raw_content)
        return None

    def _messages_mode_assistant_content(self, data: Any) -> tuple[str, bool]:
        if not isinstance(data, list) or not data:
            return "", False
        msg_map = data[0]
        if not isinstance(msg_map, dict):
            return "", False
        phase = msg_map.get("phase")
        phase_s = phase.strip() if isinstance(phase, str) else ""
        if phase_s:
            return "", False
        msg_type = msg_map.get("type") if isinstance(msg_map.get("type"), str) else ""
        if msg_type and not _is_terminal_message_type(msg_type):
            return "", False
        content = _extract_content_from_message(msg_map).strip()
        if not content:
            return "", False
        return content, True

    def _is_final_output_event(self, data_type: str, ns: str) -> bool:
        combined = f"{data_type} {ns}"
        if "final_report" in combined:
            return True
        return any(phase in combined for phase in self._deliverable_phases)


def _is_streaming_message_type(msg_type: str) -> bool:
    return msg_type in ("AIMessageChunk", "ai_chunk", "message_chunk")


def _is_terminal_message_type(msg_type: str) -> bool:
    return msg_type in ("AIMessage", "ai", "assistant")


def _first_message_payload(data: Any) -> tuple[str, str, str, bool]:
    if not isinstance(data, list) or not data:
        return "", "", "", False
    msg_map = data[0]
    if not isinstance(msg_map, dict):
        return "", "", "", False
    type_raw = msg_map.get("type")
    msg_type = type_raw if isinstance(type_raw, str) else ""
    phase_raw = msg_map.get("phase")
    phase = phase_raw if isinstance(phase_raw, str) else ""
    content = _extract_content_from_message(msg_map)
    return msg_type, content, phase, True


def _loop_ai_message(data: Any) -> dict[str, str] | None:
    if not isinstance(data, list) or not data:
        return None
    msg_map = data[0]
    if not isinstance(msg_map, dict):
        return None
    phase_raw = msg_map.get("phase")
    phase = phase_raw.strip() if isinstance(phase_raw, str) else ""
    if not phase:
        return None
    type_raw = msg_map.get("type")
    msg_type = type_raw if isinstance(type_raw, str) else ""
    content = _extract_content_from_message(msg_map)
    return {"type": msg_type, "content": content, "phase": phase}


def _extract_content_from_message(msg_map: dict[str, Any]) -> str:
    c = msg_map.get("content")
    if isinstance(c, str) and c:
        return c
    if isinstance(c, list) and c:
        parts: list[str] = []
        for item in c:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    blocks = msg_map.get("content_blocks")
    if isinstance(blocks, list) and blocks:
        parts = []
        for blk in blocks:
            if isinstance(blk, dict):
                text = blk.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


_CONTENT_KEYS = (
    "final_stdout_message",
    "completion_summary",
    "content",
    "text",
    "response",
    "output",
    "message",
    "report",
)


def _extract_content_from_data(data: dict[str, Any]) -> tuple[str, bool]:
    if _is_subscription_metadata_map(data):
        return "", False
    for key in _CONTENT_KEYS:
        val = data.get(key)
        if isinstance(val, str) and val:
            return val, True
    nested = data.get("data")
    if isinstance(nested, dict):
        if _is_subscription_metadata_map(nested):
            return "", False
        for key in _CONTENT_KEYS:
            val = nested.get(key)
            if isinstance(val, str) and val:
                return val, True
    return "", False


def _is_subscription_metadata_map(data: dict[str, Any]) -> bool:
    """True for loop subscription / seq acks without assistant text fields."""
    if "loop_id" not in data or "latest_seq" not in data:
        return False
    for key in ("content", "text", "response", "output", "message", "report", "answer"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return False
    return True


def _is_namespace_match(ns: str, data_type: str, pattern: str) -> bool:
    return pattern in data_type or pattern in ns


def _namespace_to_string(namespace: Any) -> str:
    if isinstance(namespace, str):
        return namespace
    if isinstance(namespace, list):
        return ".".join(s for s in namespace if isinstance(s, str))
    return ""


def _normalize_event_data(data: Any) -> dict[str, Any] | None:
    if data is None:
        return None
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


__all__ = [
    "EVENT_FINAL_REPORT",
    "EVENT_LOOP_HISTORY_REPLAYED",
    "ChatEventTerminal",
    "ChatEventResult",
    "ClassifierConfig",
    "EventClassifier",
]
