"""Unit tests for WebSocketManagedClient flat→protocol-1 coercion."""

from __future__ import annotations

from typing import Any

import pytest

from soothe_client.appkit.managed_client import (
    WebSocketManagedClient,
    _coerce_appkit_wire_message,
)


class _FakeWS:
    def __init__(self) -> None:
        self._n = 0
        self.sent: list[dict[str, Any]] = []

    def _next_request_id(self) -> str:
        self._n += 1
        return f"req-{self._n}"

    async def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)


def test_coerce_loop_input_to_notification() -> None:
    fake = _FakeWS()
    wire = _coerce_appkit_wire_message(
        {
            "type": "loop_input",
            "loop_id": "L1",
            "content": "hi",
            "intent_hint": "text_completion",
        },
        fake,  # type: ignore[arg-type]
    )
    assert wire["proto"] == "1"
    assert wire["type"] == "notification"
    assert wire["method"] == "loop_input"
    assert wire["params"]["loop_id"] == "L1"
    assert wire["params"]["content"] == "hi"
    assert wire["params"]["intent_hint"] == "text_completion"
    assert "type" not in wire["params"]


def test_coerce_command_request_to_rpc_command() -> None:
    fake = _FakeWS()
    wire = _coerce_appkit_wire_message(
        {"type": "command_request", "command": "cancel", "loop_id": "L1"},
        fake,  # type: ignore[arg-type]
    )
    assert wire["type"] == "request"
    assert wire["method"] == "rpc_command"
    assert wire["params"]["command"] == "cancel"
    assert wire["params"]["loop_id"] == "L1"
    assert wire["id"]


def test_coerce_leaves_protocol1_untouched() -> None:
    fake = _FakeWS()
    original = {
        "proto": "1",
        "type": "notification",
        "method": "loop_input",
        "params": {"loop_id": "L1", "content": "x"},
    }
    assert _coerce_appkit_wire_message(original, fake) is original  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_managed_send_message_coerces() -> None:
    fake = _FakeWS()
    managed = WebSocketManagedClient(fake)  # type: ignore[arg-type]
    await managed.send_message({"type": "loop_input", "loop_id": "L1", "content": "yo"})
    assert len(fake.sent) == 1
    assert fake.sent[0]["type"] == "notification"
    assert fake.sent[0]["method"] == "loop_input"
