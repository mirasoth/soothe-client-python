#!/usr/bin/env python3
"""Multi-turn chat on one loop — follow-ups keep prior context.

Defaults to fast ``text_completion``. Set ``SOOTHE_EXAMPLE_AGENT=1`` for the
full agent path.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from _common import StreamPrinter, daemon_url, fallback_completion_text, send_and_consume

from soothe_client.appkit import DaemonSession

TURNS = [
    "My project is a weather API. Remember that fact for later turns.",
    "What did I just tell you my project is? One short sentence.",
    "Suggest one HTTP endpoint path for current conditions. Reply with only the path.",
]


async def run_one(session: DaemonSession, prompt: str) -> None:
    print(f"\n> {prompt}", flush=True)
    printer = StreamPrinter()
    await send_and_consume(session, prompt, printer)
    if not printer.had_output:
        text = await fallback_completion_text(session)
        if text:
            print(text)
        else:
            print("(no text received)", flush=True)


async def main() -> None:
    workspace = Path(tempfile.mkdtemp(prefix="soothe-ex-chat-"))
    session = DaemonSession(daemon_url(), workspace=str(workspace))
    await session.connect()
    print(f"loop={session.loop_id}", flush=True)
    for prompt in TURNS:
        await run_one(session, prompt)
    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
