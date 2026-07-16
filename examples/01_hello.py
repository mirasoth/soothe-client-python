#!/usr/bin/env python3
"""Minimal: one prompt, wait for the reply, print what it said.

Defaults to fast ``text_completion``. Set ``SOOTHE_EXAMPLE_AGENT=1`` for the
full agent path.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from _common import StreamPrinter, daemon_url, fallback_completion_text, send_and_consume

from soothe_client.appkit import DaemonSession


async def main() -> None:
    workspace = Path(tempfile.mkdtemp(prefix="soothe-ex-hello-"))
    session = DaemonSession(daemon_url(), workspace=str(workspace))
    await session.connect()
    print(f"loop={session.loop_id}", flush=True)

    printer = StreamPrinter()
    await send_and_consume(session, "Say hello in one short sentence.", printer)

    if not printer.had_output:
        text = await fallback_completion_text(session)
        if text:
            print(text)

    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
