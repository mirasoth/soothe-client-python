#!/usr/bin/env python3
"""Stream a turn: print reply text as it arrives (no duplicate snapshots).

Defaults to fast ``text_completion``. Set ``SOOTHE_EXAMPLE_AGENT=1`` for the
full agent path.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from _common import StreamPrinter, daemon_url, send_and_consume

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
    await send_and_consume(session, prompt, printer)
    print("# done", flush=True)
    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
