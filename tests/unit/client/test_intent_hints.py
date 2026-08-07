"""Client-side ``loop_input.intent_hint`` send path."""

from __future__ import annotations

import pytest

from soothe_client.intent_hints import (
    EMBED,
    IMAGE_TO_TEXT,
    OCR,
    TEXT_COMPLETION,
)
from soothe_client.websocket import WebSocketClient


class _CapturingClient(WebSocketClient):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[dict] = []

    async def send(self, message: dict) -> None:  # type: ignore[override]
        self.sent.append(message)


@pytest.mark.asyncio
async def test_send_input_passes_daemon_and_pass_through_hints() -> None:
    client = _CapturingClient()
    for hint in (
        TEXT_COMPLETION,
        IMAGE_TO_TEXT,
        OCR,
        EMBED,
        "resume_clarification",
        "skill:search",
    ):
        client.sent.clear()
        await client.send_input("loop-1", "hello", intent_hint=hint)
        assert client.sent[-1]["params"]["intent_hint"] == hint


@pytest.mark.asyncio
async def test_send_input_passes_resume_clarification() -> None:
    client = _CapturingClient()
    await client.send_input(
        "loop-1",
        "answer",
        intent_hint="resume_clarification",
        clarification_answer=True,
    )
    params = client.sent[-1]["params"]
    assert params["intent_hint"] == "resume_clarification"
    assert params["clarification_answer"] is True
