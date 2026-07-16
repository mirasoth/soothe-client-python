# soothe-client-python

Talk to a running **soothe-daemon** over WebSocket — send prompts, stream agent
turns, run jobs.

```bash
pip install soothe-client-python
```

Requires a local daemon (default `ws://127.0.0.1:8765`).

## Quick start

```python
import asyncio
from soothe_client.appkit import DaemonSession

async def main() -> None:
    session = DaemonSession("ws://127.0.0.1:8765")
    await session.connect()
    await session.send_turn("Summarize this in one sentence: agents need tools.")
    async for _namespace, mode, data in session.iter_turn_chunks():
        if mode == "custom" and isinstance(data, dict):
            text = data.get("content") or data.get("text")
            if text:
                print(text, end="", flush=True)
    print()
    await session.close()

asyncio.run(main())
```

More patterns: [`examples/`](examples/) (hello → streaming → multi-turn → pool → jobs).

## What you get

| Need | Use |
|------|-----|
| One conversation, stream replies | `DaemonSession` (`soothe_client.appkit`) |
| Jobs / cron (async) | `AsyncCommandClient` (alias of `WsCommandClient`) |
| Jobs / cron (scripts / sync) | `CommandClient` (alias of `SyncWsCommandClient`) |
| Raw WebSocket / custom RPCs | `WebSocketClient` |
| Many users / HTTP backend | `ConnectionPool` + `TurnRunner` |

Wire request param models live in `soothe_client.protocol_params` (not at package root).

## Develop

```bash
make sync-dev
make check                 # lint + unit tests
make test-examples-offline # offline appkit examples
make test-examples         # live 01–06 (needs soothed)
make test-integration      # live integration suite (needs soothed)
```
