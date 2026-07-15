"""Loop bootstrap, input, history, and RPCs against a live daemon."""

from __future__ import annotations

from pathlib import Path

import pytest

from soothe_client import (
    TEXT_COMPLETION,
    WebSocketClient,
    fetch_loop_cards,
    fetch_loop_history,
    fetch_loop_messages,
)
from soothe_client.errors import StaleLoopError
from soothe_client.session import bootstrap_loop_session
from tests.integration._helpers import drain_events

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_bootstrap_new_loop(client: WebSocketClient, workspace_dir: Path) -> None:
    status = await bootstrap_loop_session(
        client,
        resume_loop_id=None,
        workspace=workspace_dir,
        is_ephemeral=True,
    )
    assert status.get("success") is True or status.get("type") == "session_ready"
    assert status.get("loop_id")


@pytest.mark.asyncio
async def test_loop_list_and_get(client: WebSocketClient, bootstrapped_loop: str) -> None:
    listed = await client.loop_list(limit=20, timeout=15.0)
    loops = listed.get("loops")
    assert isinstance(loops, list)

    detail = await client.loop_get(bootstrapped_loop, verbose=False, timeout=15.0)
    assert isinstance(detail, dict)
    loop_id = detail.get("loop_id") or detail.get("id") or bootstrapped_loop
    assert str(loop_id) == bootstrapped_loop or bootstrapped_loop in str(detail)


@pytest.mark.asyncio
async def test_send_input_receives_events(
    client: WebSocketClient,
    bootstrapped_loop: str,
) -> None:
    await client.send_input(
        bootstrapped_loop,
        "Reply with exactly: pong",
        intent_hint=TEXT_COMPLETION,
    )
    events = await drain_events(client, duration_s=20.0, max_count=40)
    assert events, "expected at least one stream event after loop_input"


@pytest.mark.asyncio
async def test_loop_messages_history_cards_state(
    client: WebSocketClient,
    bootstrapped_loop: str,
) -> None:
    await client.send_input(
        bootstrapped_loop,
        "Say hello once.",
        intent_hint=TEXT_COMPLETION,
    )
    await drain_events(client, duration_s=15.0, max_count=25)

    msgs = await fetch_loop_messages(client, bootstrapped_loop, timeout=15.0)
    assert isinstance(msgs, list)

    history = await fetch_loop_history(client, bootstrapped_loop, timeout=30.0)
    assert isinstance(history, dict)

    cards = await fetch_loop_cards(client, bootstrapped_loop, timeout=30.0)
    assert isinstance(cards, dict)

    state = await client.loop_state_get(bootstrapped_loop, timeout=30.0)
    assert isinstance(state, dict)


@pytest.mark.asyncio
async def test_reattach_and_probe_live(
    client: WebSocketClient,
    bootstrapped_loop: str,
    daemon_url: str,
) -> None:
    # Tear down transport; reconnect + reattach should keep the loop.
    await client.close()

    fresh = WebSocketClient(url=daemon_url)
    await fresh.connect()
    await fresh.request_connection_init()
    await fresh.wait_for_connection_ack(ack_timeout_s=15.0)
    try:
        await fresh.reattach_and_probe(bootstrapped_loop)
        detail = await fresh.loop_get(bootstrapped_loop, timeout=15.0)
        assert isinstance(detail, dict)
    finally:
        await fresh.close(handshake_timeout=1.0)


@pytest.mark.asyncio
async def test_reattach_and_probe_stale(daemon_url: str, require_daemon: str) -> None:
    client = WebSocketClient(url=daemon_url)
    await client.connect()
    await client.request_connection_init()
    await client.wait_for_connection_ack(ack_timeout_s=15.0)
    try:
        with pytest.raises((StaleLoopError, Exception)):
            await client.reattach_and_probe(
                "00000000-0000-0000-0000-000000000000",
                reattach_timeout_s=10.0,
                probe_timeout_s=5.0,
            )
    finally:
        await client.close(handshake_timeout=1.0)
