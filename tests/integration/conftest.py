"""Live-daemon integration tests for soothe-client-python.

Requires a running soothed instance. By default tests are skipped when the
daemon is unreachable. Set ``SOOTHE_INTEGRATION=1`` to fail instead of skip.

Environment:

- ``SOOTHE_WS_URL`` — WebSocket URL (default ``ws://127.0.0.1:8765``)
- ``SOOTHE_INTEGRATION`` — ``1`` / ``true`` forces run (fail if daemon down);
  ``0`` / ``false`` forces skip
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest

from soothe_client import WebSocketClient, is_daemon_live
from soothe_client.session import (
    bootstrap_loop_session,
    connect_websocket_with_retries,
)

DEFAULT_WS_URL = "ws://127.0.0.1:8765"


def _env_flag(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    return raw.strip().lower()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: live soothe-daemon tests (skipped when daemon unreachable)",
    )


@pytest.fixture(scope="session")
def daemon_url() -> str:
    """Return the WebSocket URL for the live daemon under test."""
    return os.environ.get("SOOTHE_WS_URL", DEFAULT_WS_URL).strip() or DEFAULT_WS_URL


@pytest.fixture(scope="session")
def require_daemon(daemon_url: str) -> str:
    """Skip (or fail) the session when the daemon is not live."""
    force = _env_flag("SOOTHE_INTEGRATION")
    if force in {"0", "false", "no", "off"}:
        pytest.skip("SOOTHE_INTEGRATION disabled")

    probe_err: BaseException | None = None
    try:
        live = asyncio.run(
            is_daemon_live(
                daemon_url,
                timeout=2.0,
                wait_for_ready=True,
                ready_timeout=5.0,
            )
        )
    except Exception as exc:  # noqa: BLE001 — probe failures become skip/fail
        live = False
        probe_err = exc

    if live:
        return daemon_url

    msg = f"Soothe daemon not live at {daemon_url}"
    if probe_err is not None:
        msg = f"{msg}: {probe_err}"
    if force in {"1", "true", "yes", "on"}:
        pytest.fail(msg)
    pytest.skip(msg)


@pytest.fixture
async def client(daemon_url: str, require_daemon: str) -> AsyncIterator[WebSocketClient]:
    """Connected, handshaken WebSocketClient (closed after the test)."""
    c = WebSocketClient(url=daemon_url)
    await connect_websocket_with_retries(c)
    await c.request_connection_init()
    await c.wait_for_connection_ack(ack_timeout_s=20.0)
    try:
        yield c
    finally:
        await c.close(handshake_timeout=1.0)


@pytest.fixture
async def bootstrapped_loop(
    client: WebSocketClient,
    tmp_path: Path,
) -> AsyncIterator[str]:
    """Create a fresh loop and subscribe; yield the loop id."""
    status = await bootstrap_loop_session(
        client,
        resume_loop_id=None,
        workspace=tmp_path,
        is_ephemeral=True,
    )
    loop_id = str(status.get("loop_id") or "")
    assert loop_id, f"bootstrap missing loop_id: {status}"
    yield loop_id


@pytest.fixture
def workspace_dir(tmp_path: Path) -> Iterator[Path]:
    """Isolated workspace directory for loop_new."""
    yield tmp_path
