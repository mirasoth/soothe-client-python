#!/usr/bin/env python3
"""Stream a turn: print agent text as it arrives (no duplicate snapshots)."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from _common import StreamPrinter, daemon_url

from soothe_client.appkit import DaemonSession


async def main() -> None:
    prompt = (
        " ".join(sys.argv[1:])
        or "List three practical tips for writing clearer code. Keep it under 120 words."
    )
    workspace = Path(tempfile.mkdtemp(prefix="soothe-ex-stream-"))
    session = DaemonSession(daemon_url(), workspace=str(workspace))
    await session.connect()
    print(f"# connected loop={session.loop_id}\n", flush=True)

    printer = StreamPrinter()
    await session.send_turn(prompt)
    async for namespace, mode, data in session.iter_turn_chunks():
        printer.feed(namespace, mode, data)
    printer.finish()
    print("# done", flush=True)
    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
