"""Tests for oneshot WebSocket helpers."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from soothe_sdk.wire.codec import ProtocolError

from soothe_client.helpers import protocol1_rpc


class _FakeClient:
    def __init__(self, *, result: Any = None, exc: Exception | None = None) -> None:
        self._result = result
        self._exc = exc
        self.request_calls: list[tuple[str, dict[str, Any]]] = []
        self._handshake_complete = False

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def request_connection_init(self) -> None:
        return None

    async def wait_for_connection_ack(self, ack_timeout_s: float = 10.0) -> dict[str, Any]:
        del ack_timeout_s
        return {"type": "connection_ack", "result": {"readiness_state": "ready"}}

    async def request(
        self, method: str, params: dict[str, Any] | None = None, *, timeout: float = 5.0
    ) -> dict[str, Any]:
        del timeout
        self.request_calls.append((method, params or {}))
        if self._exc:
            raise self._exc
        return self._result  # type: ignore[return-value]

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        del method, params
        if self._exc:
            raise self._exc

    async def subscribe(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 5.0,
    ) -> str:
        del method, params, timeout
        if self._exc:
            raise self._exc
        return "sub-1"


@pytest.mark.asyncio
async def test_protocol1_rpc_request_ok() -> None:
    fake = _FakeClient(result={"ok": True})
    with patch("soothe_client.helpers.WebSocketClient", return_value=fake):
        out = await protocol1_rpc("ws://t", "loop_list", {"limit": 1})
    assert out == {"ok": True}
    assert fake.request_calls == [("loop_list", {"limit": 1})]


@pytest.mark.asyncio
async def test_protocol1_rpc_maps_protocol_error() -> None:
    fake = _FakeClient(exc=ProtocolError(code=-32000, message="nope"))
    with patch("soothe_client.helpers.WebSocketClient", return_value=fake):
        out = await protocol1_rpc("ws://t", "loop_list", {})
    assert "nope" in out["error"]
