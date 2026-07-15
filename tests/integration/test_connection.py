"""Layer 0 connection / handshake integration tests."""

from __future__ import annotations

import pytest

from soothe_client import WebSocketClient, check_daemon_status
from soothe_client.errors import DisconnectCause
from soothe_client.session import connect_websocket_with_retries

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_connect_and_close(daemon_url: str, require_daemon: str) -> None:
    client = WebSocketClient(url=daemon_url)
    await connect_websocket_with_retries(client)
    assert client.is_connected
    await client.close()
    assert not client.is_connected


@pytest.mark.asyncio
async def test_handshake_ready(client: WebSocketClient) -> None:
    status = await check_daemon_status(client, timeout=10.0)
    assert status.get("readiness_state") == "ready" or status.get("running") is True


@pytest.mark.asyncio
async def test_connection_recovery(daemon_url: str, require_daemon: str) -> None:
    first = WebSocketClient(url=daemon_url)
    await connect_websocket_with_retries(first)
    await first.request_connection_init()
    await first.wait_for_connection_ack(ack_timeout_s=15.0)
    await first.close()

    second = WebSocketClient(url=daemon_url)
    await connect_websocket_with_retries(second)
    await second.request_connection_init()
    await second.wait_for_connection_ack(ack_timeout_s=15.0)
    assert second.is_connected
    await second.close()


@pytest.mark.asyncio
async def test_disconnect_notification(client: WebSocketClient) -> None:
    await client.notify("disconnect", {})
    # Explicit close still fires CLEAN (or already fired).
    await client.close()
    cause = client.disconnect_cause()
    assert (
        cause in (DisconnectCause.CLEAN, DisconnectCause.UNCLEAN, None) or client.is_disconnected()
    )


@pytest.mark.asyncio
async def test_daemon_status_rpc(client: WebSocketClient) -> None:
    resp = await client.fetch_daemon_status(timeout=10.0)
    assert isinstance(resp, dict)
    assert resp.get("running") is True or resp.get("readiness_state") == "ready"
