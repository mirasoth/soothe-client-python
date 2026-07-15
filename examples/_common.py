"""Shared helpers for runnable agent examples."""

from __future__ import annotations

import os
from typing import Any


def daemon_url() -> str:
    """WebSocket URL from ``SOOTHE_WS_URL`` or the local default."""
    return os.environ.get("SOOTHE_WS_URL", "ws://127.0.0.1:8765").strip() or ("ws://127.0.0.1:8765")


def text_from_chunk(_namespace: tuple[Any, ...], mode: str, data: Any) -> str:
    """Best-effort assistant text from a stream chunk.

    Ignores tool-status noise and non-message frames.
    """
    if mode not in {"messages", "updates"}:
        return ""
    msg: Any = data
    if isinstance(data, (tuple, list)) and data:
        msg = data[0]
    if not isinstance(msg, dict):
        return ""

    # Skip pure tool / status payloads that aren't assistant prose.
    msg_type = str(msg.get("type") or "").lower()
    if msg_type in {"tool", "tool_result", "function", "human", "system"}:
        return ""

    for key in ("content", "text", "delta"):
        value = msg.get(key)
        if isinstance(value, str) and value.strip():
            # Tool chatter often lands as plain short status strings.
            if value.strip() in {"No files found", "No files found."}:
                return ""
            return value
    return ""


class StreamPrinter:
    """Print streamed text without repeating cumulative snapshots."""

    def __init__(self) -> None:
        self._last = ""

    def feed(self, namespace: tuple[Any, ...], mode: str, data: Any) -> str:
        """Return the new printable delta (also writes to stdout)."""
        piece = text_from_chunk(namespace, mode, data)
        if not piece:
            return ""
        if piece == self._last:
            return ""
        if self._last and piece.startswith(self._last):
            delta = piece[len(self._last) :]
            self._last = piece
            if delta:
                print(delta, end="", flush=True)
            return delta
        # New independent chunk (or overlapping rewrite) — print a separator
        # only when switching away from an existing blob.
        if self._last and not piece.startswith(self._last) and not self._last.startswith(piece):
            print("\n", end="", flush=True)
        self._last = piece
        print(piece, end="", flush=True)
        return piece

    def finish(self) -> None:
        """End the current line if anything was printed."""
        if self._last:
            print(flush=True)

    @property
    def had_output(self) -> bool:
        """Whether any assistant text was printed this turn."""
        return bool(self._last)

    def reset(self) -> None:
        """Clear cumulative state before a new turn."""
        self._last = ""
