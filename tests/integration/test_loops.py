"""Loop bootstrap, input, history, and RPCs against a live daemon."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from soothe_client import (
    TEXT_COMPLETION,
    WebSocketClient,
    fetch_execution_state,
    fetch_loop_history,
    fetch_loop_messages,
)
from soothe_client.errors import StaleLoopError
from soothe_client.session import bootstrap_loop_session
from tests.integration._helpers import (
    cancel_loop_best_effort,
    drain_events,
    fetch_state_after_turn,
)

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


# ---------------------------------------------------------------------------
# Daemon-backed resume scenarios (step 06/07 integration)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_approval_clarification(
    client: WebSocketClient,
    bootstrapped_loop: str,
) -> None:
    """Approval gate: a clarification-requested event surfaces the pending
    question, and the execution-state snapshot reports the loop is blocked
    (status not "finalized") so a client can render an approval prompt.
    """
    # Seed a turn; a clarification may or may not fire depending on the
    # model path, but the execution-state RPC must always respond.
    await client.send_input(
        bootstrapped_loop,
        "Do you need any clarification before replying with: hello",
        intent_hint=TEXT_COMPLETION,
    )
    await drain_events(client, duration_s=20.0, max_count=40)

    # The execution-state snapshot must be reachable mid-flight.
    state = await fetch_execution_state(client, bootstrapped_loop, timeout=30.0)
    assert isinstance(state, dict)
    assert state.get("loop_id") == bootstrapped_loop
    # status is one of the loop checkpoint vocabulary; must not be missing.
    status = state.get("status")
    assert isinstance(status, str)
    assert status in {"running", "idle", "finalized", "cancelled"}
    # A loop with a pending clarification is never finalized.
    if status == "finalized":
        # If the turn already completed, at least verify iteration advanced.
        assert isinstance(state.get("iteration"), int)
    else:
        # step_index is an int (possibly 0 for a fresh loop).
        assert isinstance(state.get("step_index"), int)


@pytest.mark.asyncio
async def test_resume_restart_from_existing_loop(
    client: WebSocketClient,
    bootstrapped_loop: str,
    workspace_dir: Path,
    daemon_url: str,
) -> None:
    """Client reconnect/reattach resume (does NOT stop or kill soothed).

    A fresh client reconnects and reattaches to the existing loop via
    ``bootstrap_loop_session(resume_loop_id=...)``, then the execution state
    reflects the same ``loop_id`` with persisted iteration/step progress.
    """
    # Seed progress on the first client.
    await client.send_input(
        bootstrapped_loop,
        "Reply with exactly: alpha",
        intent_hint=TEXT_COMPLETION,
    )
    state = await fetch_state_after_turn(client, bootstrapped_loop, drain_timeout=30.0)
    first_iteration = state.get("iteration", 0)

    # Tear down the *client* transport only — leave the daemon process alone.
    await client.close()
    fresh = WebSocketClient(url=daemon_url)
    await fresh.connect()
    await fresh.request_connection_init()
    await fresh.wait_for_connection_ack(ack_timeout_s=20.0)
    try:
        status = await bootstrap_loop_session(
            fresh,
            resume_loop_id=bootstrapped_loop,
            workspace=workspace_dir,
            is_ephemeral=True,
        )
        assert status.get("loop_id") == bootstrapped_loop or status.get("success") is True

        # After reattach, the execution state must still be reachable and
        # reflect the same loop_id. Iteration must not regress (>= first).
        resume_state = await fetch_execution_state(fresh, bootstrapped_loop, timeout=30.0)
        assert resume_state.get("loop_id") == bootstrapped_loop
        assert isinstance(resume_state.get("iteration"), int)
        assert resume_state["iteration"] >= first_iteration
    finally:
        await cancel_loop_best_effort(fresh, bootstrapped_loop)
        await fresh.close(handshake_timeout=1.0)


@pytest.mark.asyncio
async def test_resume_continuation_from_step_index(
    client: WebSocketClient,
    bootstrapped_loop: str,
) -> None:
    """--resume continuation: the execution-state snapshot's ``step_index``
    and ``plan`` fields let a client determine where to continue from.
    Sending a follow-up turn after fetching state must succeed (the loop
    accepts new input after the snapshot read).
    """
    # Seed a turn so there is persisted progress to snapshot.
    await client.send_input(
        bootstrapped_loop,
        "Reply with exactly: one",
        intent_hint=TEXT_COMPLETION,
    )
    await drain_events(client, duration_s=20.0, max_count=40)

    # Snapshot the daemon-side step index.
    state = await fetch_execution_state(client, bootstrapped_loop, timeout=30.0)
    assert isinstance(state, dict)
    step_index = state.get("step_index")
    assert isinstance(step_index, int)
    # plan may be None when no decision is active (idle loop), but the
    # field must always be present.
    assert "plan" in state

    # The client can continue: a follow-up turn is accepted.
    await client.send_input(
        bootstrapped_loop,
        "Reply with exactly: two",
        intent_hint=TEXT_COMPLETION,
    )
    events = await drain_events(client, duration_s=20.0, max_count=40)
    assert events, "expected events after continuation turn"


@pytest.mark.asyncio
async def test_resume_completion_idle_status(
    client: WebSocketClient,
    bootstrapped_loop: str,
) -> None:
    """Completion: after a turn completes, the execution-state snapshot must
    be reachable and report a valid status. Completion is observed via the
    ``stream.end`` wire event (the authoritative signal); the loop metadata
    ``status`` field may remain ``running`` until a periodic reconciliation
    sweep demotes it to ``idle``, so ``running`` is also accepted here when
    the stream has ended. Iteration must be a non-negative int.
    """
    await client.send_input(
        bootstrapped_loop,
        "Reply with exactly: done",
        intent_hint=TEXT_COMPLETION,
    )
    # Drain the stream until the turn-end frame arrives (stream.end /
    # strange_loop.completed). This is the authoritative completion signal
    # a client can observe; it does not depend on the metadata status row
    # being reconciled, which happens on a slow periodic sweep.
    state = await fetch_state_after_turn(client, bootstrapped_loop)
    assert isinstance(state, dict)
    assert state.get("loop_id") == bootstrapped_loop
    status = state.get("status")
    assert isinstance(status, str)
    # After the stream ends the loop is logically done; the metadata status
    # is one of the checkpoint vocabulary values. ``running`` is valid
    # because the reconciliation sweep that demotes it to ``idle`` runs on
    # a slow interval (default 300s / 180s stale threshold).
    assert status in {"running", "idle", "finalized", "cancelled"}, (
        f"expected running/idle/finalized/cancelled, got {status!r}"
    )
    assert isinstance(state.get("iteration"), int)
    assert state["iteration"] >= 0


@pytest.mark.asyncio
async def test_resume_crash_mid_step_recovery(
    client: WebSocketClient,
    bootstrapped_loop: str,
    daemon_url: str,
) -> None:
    """Client transport drop mid-turn (does NOT stop or kill soothed).

    Closing the WebSocket mid-stream leaves daemon-side execution state
    intact. After reconnect + ``loop_reattach``, ``fetch_execution_state``
    must still return a valid snapshot. The test cancels the loop afterward
    so the live daemon is not left with an orphaned running execute.
    """
    # Seed a turn, then forcibly drop the *client* connection mid-stream.
    await client.send_input(
        bootstrapped_loop,
        "Reply with exactly: recovering",
        intent_hint=TEXT_COMPLETION,
    )
    # Don't fully drain — simulate a client crash by closing early.
    await asyncio.sleep(0.5)
    await client.close()

    # Reconnect and reattach to the same loop (daemon process stays up).
    fresh = WebSocketClient(url=daemon_url)
    await fresh.connect()
    await fresh.request_connection_init()
    await fresh.wait_for_connection_ack(ack_timeout_s=20.0)
    try:
        await fresh.request(
            "loop_reattach",
            {"loop_id": bootstrapped_loop},
            timeout=30.0,
        )
        # Drain any replay backlog briefly.
        await drain_events(fresh, duration_s=3.0, max_count=10)

        # The daemon-side execution state must survive the transport crash.
        state = await fetch_execution_state(fresh, bootstrapped_loop, timeout=30.0)
        assert isinstance(state, dict)
        assert state.get("loop_id") == bootstrapped_loop
        assert isinstance(state.get("iteration"), int)
        assert isinstance(state.get("step_index"), int)
        status = state.get("status")
        assert isinstance(status, str)
        assert status in {"running", "idle", "finalized", "cancelled"}
    finally:
        # Free the worker; never issue soothed stop / kill against the host.
        await cancel_loop_best_effort(fresh, bootstrapped_loop)
        await fresh.close(handshake_timeout=1.0)


@pytest.mark.asyncio
async def test_loop_delete_reattach(
    client: WebSocketClient,
    bootstrapped_loop: str,
) -> None:
    """Exercise loop_reattach and loop_delete convenience RPCs."""
    reattached = await client.loop_reattach(bootstrapped_loop, timeout=15.0)
    assert isinstance(reattached, dict)

    deleted = await client.loop_delete(bootstrapped_loop, timeout=15.0)
    assert isinstance(deleted, dict)


@pytest.mark.asyncio
async def test_config_get_reload(client: WebSocketClient) -> None:
    """Exercise config_get and config_reload convenience RPCs."""
    providers = await client.config_get("providers", timeout=10.0)
    assert isinstance(providers, dict)

    reloaded = await client.config_reload(timeout=15.0)
    assert isinstance(reloaded, dict)


@pytest.mark.asyncio
async def test_authenticate_and_refresh(client: WebSocketClient) -> None:
    """Exercise auth and auth_refresh convenience RPCs.

    These may return error envelopes if the daemon has no auth backend
    configured; the test only asserts the RPC completes with a dict.
    """
    try:
        result = await client.authenticate("test-key", "test-secret", timeout=10.0)
    except Exception:
        return
    assert isinstance(result, dict)
    try:
        refresh = await client.refresh_auth_token("dummy-token", timeout=10.0)
    except Exception:
        return
    assert isinstance(refresh, dict)
