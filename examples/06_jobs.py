#!/usr/bin/env python3
"""Background jobs: create → status → cancel (+ autopilot status when available)."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from _common import daemon_url

from soothe_client.ws_command_client import WsCommandClient


async def main() -> None:
    workspace = Path(tempfile.mkdtemp(prefix="soothe-ex-job-"))
    client = WsCommandClient(ws_url=daemon_url(), timeout=30.0)

    try:
        status = await client.autopilot_status()
        print(
            "autopilot:",
            {k: status.get(k) for k in ("state", "running", "dreaming") if k in status},
        )
    except RuntimeError as exc:
        print(
            "autopilot_status skipped (daemon needs a restart with protocol-1 autopilot handlers):",
            exc,
        )

    created = await client.job_create(
        "Echo: integration job smoke",
        workspace=str(workspace),
        autonomous=False,
        max_iterations=1,
    )
    job_id = created.get("job_id") or created.get("id")
    print("created:", created)
    if not job_id:
        raise SystemExit("job_create returned no id")

    print("status:", await client.job_status(str(job_id)))
    print("cancel:", await client.job_cancel(str(job_id)))


if __name__ == "__main__":
    asyncio.run(main())
