#!/usr/bin/env python3
"""Background jobs: create → status → cancel via the preferred job_* API.

On v1.2.0+ daemons the legacy AutopilotService DAG RPCs (`job_status`,
`job_cancel`, `job_pause`, …) are removed and return -32402
service-unavailable. Job status is loop-native: query the loop returned by
`job_create` via `loop_get`, and purge it with `loop_delete`. The legacy
`job_*` calls are soft-failed below to document that transition (mirrors
the Rust/Go clients' integration tests).
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from _common import daemon_url

from soothe_client import AsyncCommandClient, WebSocketClient
from soothe_client.session import connect_websocket_with_retries


def _is_legacy_unavailable(exc: BaseException) -> bool:
    """True when the daemon reports the legacy AutopilotService path is gone."""
    text = str(exc)
    return "-32402" in text or "AutopilotService" in text


async def main() -> None:
    workspace = Path(tempfile.mkdtemp(prefix="soothe-ex-job-"))
    client = AsyncCommandClient(ws_url=daemon_url(), timeout=30.0)

    try:
        status = await client.autopilot_status()
        print(
            "autopilot:",
            {k: status.get(k) for k in ("state", "running", "dreaming") if k in status},
        )
    except RuntimeError as exc:
        print(
            "autopilot_status skipped (daemon needs protocol-1 autopilot handlers):",
            exc,
        )

    created = await client.job_create(
        "Echo: integration job smoke",
        rail_id="auto",
        workspace=str(workspace),
    )
    loop_id = created.get("loop_id") or created.get("job_id") or created.get("id")
    print("created:", created)
    if not loop_id:
        raise SystemExit("job_create returned no id")

    # Job status is loop-native: query the loop returned by job_create.
    # WebSocketClient exposes loop_get / loop_delete; AsyncCommandClient does
    # not wrap them, so connect a streaming client for the loop-native reads.
    ws = WebSocketClient(url=daemon_url())
    await connect_websocket_with_retries(ws)
    await ws.request_connection_init()
    await ws.wait_for_connection_ack(ack_timeout_s=20.0)
    try:
        loop = await ws.loop_get(str(loop_id))
        loop_obj = loop.get("loop") if isinstance(loop.get("loop"), dict) else loop
        print("loop_get:", {k: loop_obj.get(k) for k in ("loop_id", "status")})
        # Legacy job_status / job_cancel are service-unavailable stubs on
        # v1.2.0+ daemons; soft-fail that case (loop-native path above).
        try:
            print("job_status:", await client.job_status(str(loop_id)))
        except RuntimeError as exc:
            if not _is_legacy_unavailable(exc):
                raise
            print("job_status soft-fail (expected on v1.2.0):", exc)
    finally:
        # Cancel: purge the loop created by this example (loop-native path).
        await ws.loop_delete(str(loop_id))
        await ws.close(handshake_timeout=1.0)


if __name__ == "__main__":
    asyncio.run(main())
