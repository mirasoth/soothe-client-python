#!/usr/bin/env python3
"""Fast text-only completion via intent_hint=text_completion."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from _common import StreamPrinter, daemon_url, fallback_completion_text, send_and_consume

from soothe_client import TEXT_COMPLETION
from soothe_client.appkit import DaemonSession


async def main() -> None:
    prompt = " ".join(sys.argv[1:]) or "Reply with exactly one word: pong"
    workspace = Path(tempfile.mkdtemp(prefix="soothe-ex-tc-"))
    session = DaemonSession(daemon_url(), workspace=str(workspace))
    await session.connect()
    assert session.loop_id

    printer = StreamPrinter()
    await send_and_consume(session, prompt, printer, intent_hint=TEXT_COMPLETION)

    if not printer.had_output:
        text = await fallback_completion_text(session)
        if text:
            print(text)

    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
