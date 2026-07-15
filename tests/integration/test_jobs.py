"""Job IPC integration tests via WsCommandClient (RFC-228)."""

from __future__ import annotations

from pathlib import Path

import pytest

from soothe_client.ws_command_client import WsCommandClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_job_create_status_cancel(
    daemon_url: str,
    require_daemon: str,
    workspace_dir: Path,
) -> None:
    client = WsCommandClient(ws_url=daemon_url)
    try:
        created = await client.job_create(
            "echo integration-smoke",
            workspace=str(workspace_dir),
            autonomous=False,
            max_iterations=1,
        )
        job_id = created.get("job_id") or created.get("id")
        assert job_id, f"job_create missing id: {created}"

        status = await client.job_status(str(job_id))
        assert status.get("job_id") == job_id or status.get("id") == job_id or "status" in status

        cancelled = await client.job_cancel(str(job_id))
        assert isinstance(cancelled, dict)
    finally:
        # WsCommandClient methods open short-lived sockets; nothing to close.
        pass


@pytest.mark.asyncio
async def test_autopilot_status_optional(daemon_url: str, require_daemon: str) -> None:
    """Autopilot status is not a protocol-1 request method on current daemons.

    Skip when the daemon rejects the RPC; keep the client call covered when
    a future daemon registers ``autopilot_status``.
    """
    client = WsCommandClient(ws_url=daemon_url)
    try:
        status = await client.autopilot_status()
    except RuntimeError as exc:
        msg = str(exc)
        if "Unknown method" in msg or "Invalid params" in msg or "-32602" in msg:
            pytest.skip(f"daemon does not expose autopilot_status over request RPC: {exc}")
        raise
    assert isinstance(status, dict)
