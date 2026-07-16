"""Job IPC integration tests via AsyncCommandClient (RFC-228)."""

from __future__ import annotations

from pathlib import Path

import pytest

from soothe_client.command_client import AsyncCommandClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_job_create_status_cancel(
    daemon_url: str,
    require_daemon: str,
    workspace_dir: Path,
) -> None:
    client = AsyncCommandClient(ws_url=daemon_url)
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


@pytest.mark.asyncio
async def test_autopilot_status(daemon_url: str, require_daemon: str) -> None:
    client = AsyncCommandClient(ws_url=daemon_url)
    try:
        status = await client.autopilot_status()
    except RuntimeError as exc:
        # Running processes may predate protocol-1 autopilot_* registration.
        if "Unknown method" in str(exc) or "-32602" in str(exc):
            pytest.skip(f"restart soothed for protocol-1 autopilot_* RPCs: {exc}")
        raise
    assert isinstance(status, dict)
    assert "running" in status or "state" in status or "dreaming" in status
