# soothe-client-python

Talk to a running **soothe-daemon** over WebSocket — send prompts, stream agent
turns, run jobs.

```bash
pip install soothe-client-python
# optional: image compaction
pip install 'soothe-client-python[image]'
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
| One conversation, stream replies | `DaemonSession` |
| Raw WebSocket / custom RPCs | `WebSocketClient` |
| Many users / HTTP backend | `ConnectionPool` + `TurnRunner` |
| Jobs / autopilot / cron | `WsCommandClient` |

## Develop

```bash
make sync-dev
make check          # lint + unit tests
make test-examples  # offline appkit examples
make test-integration  # needs soothed
```
