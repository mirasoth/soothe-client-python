"""Client-side ``loop_input.intake_scope`` send path."""

from __future__ import annotations

import pytest

from soothe_client.appkit.turn_runner import InputOpts, input_message_for_loop
from soothe_client.protocol_params import LoopInputParams
from soothe_client.websocket import WebSocketClient


class _CapturingClient(WebSocketClient):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[dict] = []

    async def send(self, message: dict) -> None:  # type: ignore[override]
        self.sent.append(message)


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["trivial", "simple", "complex"])
async def test_send_input_passes_intake_scope(scope: str) -> None:
    client = _CapturingClient()
    await client.send_input("loop-1", "fix the typo", intake_scope=scope)
    assert client.sent[-1]["params"]["intake_scope"] == scope


@pytest.mark.asyncio
async def test_send_input_omits_empty_intake_scope() -> None:
    client = _CapturingClient()
    await client.send_input("loop-1", "hello", intake_scope="")
    assert "intake_scope" not in client.sent[-1]["params"]


def test_input_message_for_loop_includes_intake_scope() -> None:
    msg = input_message_for_loop(
        "do it",
        "loop-1",
        opts=InputOpts(intake_scope=" Simple "),
    )
    assert msg["intake_scope"] == "Simple"


def test_loop_input_params_accepts_intake_scope() -> None:
    params = LoopInputParams(loop_id="abc", content="hi", intake_scope="complex")
    assert params.intake_scope == "complex"
