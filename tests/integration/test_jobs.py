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
        rail_id="auto",
        workspace=str(workspace_dir),
    )
    # Loop-native submission: response carries loop_id + status=submitted.
    loop_id = created.get("loop_id") or created.get("job_id") or created.get("id")
    assert loop_id, f"job_create missing id: {created}"
    assert created.get("status") == "submitted"

    # job_status / job_cancel are legacy AutopilotService DAG RPCs, removed
    # on v1.2.0+ daemons (they return -32402 service-unavailable). Soft-fail
    # that case — the loop-native path is verified by job_create above.
    # (Mirrors the Rust/Go clients' soft-fail handling.)
    try:
        status = await client.job_status(str(loop_id))
    except RuntimeError as exc:
        if "-32402" not in str(exc) and "AutopilotService" not in str(exc):
            raise
    else:
        assert (
            status.get("job_id") == loop_id
            or status.get("id") == loop_id
            or "status" in status
        )

    try:
        cancelled = await client.job_cancel(str(loop_id))
    except RuntimeError as exc:
        if "-32402" not in str(exc) and "AutopilotService" not in str(exc):
            raise
    else:
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
