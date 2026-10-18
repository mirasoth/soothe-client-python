"""Thinking-step extraction for appkit.

Maps an allowlisted progress event to one structured UI line.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

MAX_THINKING_STEP_RUNES = 280

DEFAULT_THINKING_STEP_EVENTS: frozenset[str] = frozenset(
    {
        "soothe.cognition.strange_loop.step.started",
        "soothe.cognition.strange_loop.step.completed",
        "soothe.cognition.plan.created",
        "soothe.cognition.goal.created",
        "soothe.tool.invocation.started",
        "soothe.tool.invocation.completed",
    }
)


def extract_thinking_step(
    event_type: str,
    data: Mapping[str, Any] | None,
    allow: frozenset[str] | set[str] | None = None,
) -> tuple[str, bool]:
    """Map an allowlisted progress event to one structured UI line.

    Args:
        event_type: Wire event type string.
        data: Event payload map.
        allow: Optional override of the default thinking-step allowlist.

    Returns:
        `(line, True)` for a recognized event; `("", False)` otherwise.
    """
    if not event_type or data is None:
        return "", False
    et = event_type.strip()
    if not et:
        return "", False

    allowlist = allow if allow is not None else DEFAULT_THINKING_STEP_EVENTS
    if et not in allowlist:
        return "", False

    line = ""
    if et == "soothe.cognition.strange_loop.step.started":
        line = _format_step_line(data, _str_field(data, "description"))
    elif et == "soothe.cognition.strange_loop.step.completed":
        line = _format_step_line(data, _str_field(data, "summary"))
    elif et == "soothe.cognition.plan.created":
        g = _str_field(data, "goal")
        if g:
            line = f"Goal: {g}"
    elif et == "soothe.cognition.goal.created":
        g = _str_field(data, "friendly_message", "description")
        if g:
            line = f"Goal: {g}"
    elif et in ("soothe.tool.invocation.started", "soothe.tool.invocation.completed"):
        name = _str_field(data, "tool_name", "name")
        if name:
            line = f"Tool: {name}"
    else:
        return "", False

    line = line.strip()
    if not line:
        return "", False
    runes = list(line)
    if len(runes) > MAX_THINKING_STEP_RUNES:
        line = "".join(runes[:MAX_THINKING_STEP_RUNES]) + "…"
    return line, True


def _format_step_line(data: Mapping[str, Any], desc: str) -> str:
    step_id = _str_field(data, "step_id")
    if step_id and desc:
        return f"Step {step_id}: {desc}"
    if step_id:
        return f"Step {step_id}"
    if desc:
        return f"Step: {desc}"
    return ""


def _str_field(data: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        val = data.get(key)
        if isinstance(val, str):
            s = val.strip()
            if s:
                return s
    return ""


__all__ = [
    "DEFAULT_THINKING_STEP_EVENTS",
    "MAX_THINKING_STEP_RUNES",
    "extract_thinking_step",
]
