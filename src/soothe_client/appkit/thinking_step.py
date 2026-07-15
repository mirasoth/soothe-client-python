"""Thinking-step extraction for appkit (RFC-629 Layer 1).

Maps an allowlisted progress event to one structured UI line. Free-form
streams (tokens, reports, reasoning) are excluded. Ported from Go/TS appkit.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

MAX_THINKING_STEP_RUNES = 280

DEFAULT_THINKING_STEP_EVENTS: frozenset[str] = frozenset(
    {
        "soothe.cognition.plan.step.started",
        "soothe.cognition.plan.step.completed",
        "soothe.cognition.plan.step.failed",
        "soothe.lifecycle.iteration.started",
        "soothe.agent.loop.step.started",
        "soothe.agent.loop.started",
        "soothe.cognition.plan.batch.started",
        "soothe.cognition.plan.created",
        "soothe.cognition.goal.created",
        "soothe.tool.execution.started",
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
        ``(line, True)`` for a recognized event; ``("", False)`` otherwise.
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
    if et == "soothe.cognition.plan.step.started":
        line = _format_plan_step_line(data, "")
    elif et == "soothe.cognition.plan.step.completed":
        line = _format_plan_step_line(data, "done")
    elif et == "soothe.cognition.plan.step.failed":
        step_id = _str_field(data, "step_id")
        err_msg = _str_field(data, "error")
        if step_id and err_msg:
            line = f"Step {step_id} failed: {err_msg}"
        elif step_id:
            line = f"Step {step_id} failed"
        elif err_msg:
            line = f"Step failed: {err_msg}"
    elif et == "soothe.agent.loop.step.started":
        line = _format_agent_step_line(data, "")
    elif et == "soothe.cognition.plan.batch.started":
        n = data.get("parallel_count")
        if isinstance(n, (int, float)) and n > 0:
            line = f"Running {int(n)} steps in parallel"
    elif et in ("soothe.cognition.plan.created", "soothe.agent.loop.started"):
        g = _str_field(data, "goal")
        if g:
            line = f"Goal: {g}"
    elif et == "soothe.cognition.goal.created":
        g = _str_field(data, "friendly_message", "description")
        if g:
            line = f"Goal: {g}"
    elif et == "soothe.lifecycle.iteration.started":
        g = _str_field(data, "goal_description")
        if g:
            line = f"Iteration: {g}"
    elif et == "soothe.tool.execution.started":
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


def _format_plan_step_line(data: Mapping[str, Any], suffix: str) -> str:
    step_id = _str_field(data, "step_id")
    desc = _str_field(data, "description")
    if step_id and suffix:
        return f"Step {step_id}: {suffix}"
    if step_id and desc:
        return f"Step {step_id}: {desc}"
    if step_id:
        return f"Step {step_id}"
    if desc and suffix:
        return f"Step: {suffix}"
    if desc:
        return f"Step: {desc}"
    if suffix:
        return f"Step: {suffix}"
    return ""


def _format_agent_step_line(data: Mapping[str, Any], suffix: str) -> str:
    step_id = _str_field(data, "step_id")
    desc = _str_field(data, "description")
    if step_id and desc:
        return f"Step {step_id}: {desc}"
    if desc:
        return f"Step: {suffix}" if suffix else f"Step: {desc}"
    if step_id:
        return f"Step {step_id}"
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
