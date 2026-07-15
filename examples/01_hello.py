#!/usr/bin/env python3
"""Minimal: one prompt, wait for the agent, print what it said."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from _common import StreamPrinter, daemon_url

from soothe_client.appkit import DaemonSession


async def main() -> None:
    workspace = Path(tempfile.mkdtemp(prefix="soothe-ex-hello-"))
    session = DaemonSession(daemon_url(), workspace=str(workspace))
    await session.connect()
    print(f"loop={session.loop_id}", flush=True)

    printer = StreamPrinter()
    await session.send_turn("Say hello in one short sentence.")
    async for namespace, mode, data in session.iter_turn_chunks():
        printer.feed(namespace, mode, data)
    printer.finish()

    if not printer.had_output:
        text = await session.fetch_goal_completion_text(session.loop_id or "")
        if text:
            print(text)
        else:
            for row in reversed(await session.fetch_conversation_log(session.loop_id or "")):
                content = row.get("content")
                if isinstance(content, str) and content.strip():
                    print(content)
                    break

    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
