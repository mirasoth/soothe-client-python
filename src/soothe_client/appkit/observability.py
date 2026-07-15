"""Per-turn observability counters for daemon stream consumption."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TurnEventStats:
    """Event counts accumulated over a single daemon turn.

    Apps may subclass or replace this via ``DaemonSession``'s stats factory.
    """

    total: int = 0
    messages: int = 0
    updates: int = 0
    custom: int = 0
    skipped: int = 0
    filtered_early: int = 0
    tool_calls: int = 0
    tool_results: int = 0
    text_chunks: int = 0
    heartbeats_dropped: int = 0
    post_idle_drained: int = 0
    inbound_dropped: int = 0


__all__ = ["TurnEventStats"]
