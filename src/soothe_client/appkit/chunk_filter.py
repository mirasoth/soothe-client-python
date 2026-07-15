"""Early filters for daemon stream chunks (wire / dict-shaped payloads).

CLI callers that also see LangChain message objects should pass a richer filter
callback (e.g. ``soothe_cli.runtime.wire.chunk_filter.should_drop_stream_chunk_early``).
"""

from __future__ import annotations

from typing import Any

_MSG_PAIR_LEN = 2


def updates_chunk_is_noop(data: Any) -> bool:
    """True when an ``updates`` chunk carries no LangGraph interrupt."""
    if not isinstance(data, dict):
        return True
    return "__interrupt__" not in data


def _wire_body(msg: dict[str, Any]) -> dict[str, Any]:
    for key in ("kwargs", "data"):
        nested = msg.get(key)
        if isinstance(nested, dict):
            return nested
    return msg


def _dict_has_tool_invocation(msg: dict[str, Any]) -> bool:
    body = _wire_body(msg)
    if body.get("tool_calls") or body.get("tool_call_chunks"):
        return True
    for key in ("content", "content_blocks"):
        raw = body.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("type") in {
                    "tool_call",
                    "tool_call_chunk",
                    "tool_use",
                }:
                    return True
    return False


def _plain_text(msg: dict[str, Any]) -> str:
    body = _wire_body(msg)
    content = body.get("content", msg.get("content"))
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def message_chunk_is_non_actionable(data: Any) -> bool:
    """True when a wire ``messages`` pair has no tool, text, or loop phase payload."""
    if not isinstance(data, (list, tuple)) or len(data) != _MSG_PAIR_LEN:
        return False
    msg = data[0]
    if msg is None:
        return True
    if not isinstance(msg, dict):
        # Non-dict messages (e.g. LangChain objects) are not filtered here.
        return False
    body = _wire_body(msg)
    raw = str(body.get("type") or msg.get("type") or "")
    if raw in ("tool", "ToolMessage") or raw.endswith("ToolMessage"):
        return False
    if _dict_has_tool_invocation(msg):
        return False
    if body.get("phase") or msg.get("phase"):
        return False
    return not _plain_text(msg).strip()


def should_drop_stream_chunk_early(namespace: tuple[Any, ...], mode: str, data: Any) -> bool:
    """Return True when the chunk can be skipped before the turn pipeline."""
    del namespace  # reserved for product filters
    if mode == "updates":
        return updates_chunk_is_noop(data)
    if mode == "messages":
        return message_chunk_is_non_actionable(data)
    return False


__all__ = [
    "message_chunk_is_non_actionable",
    "should_drop_stream_chunk_early",
    "updates_chunk_is_noop",
]
