# soothe-client-python

WebSocket client in Python for [soothe-daemon](https://github.com/mirasoth/soothe).

Peer of [`soothe-client-go`](https://github.com/mirasoth/soothe-client-go) and
[`@mirasoth/soothe-client`](https://github.com/mirasoth/soothe-client-typescript).

## Install

```bash
pip install soothe-client-python
# or, in the soothe monorepo workspace:
uv sync --all-packages
```

## Quick start

```python
from soothe_client import WebSocketClient, bootstrap_loop_session, connect_websocket_with_retries

client = WebSocketClient(url="ws://127.0.0.1:8765")
await connect_websocket_with_retries(client)
loop_id = await bootstrap_loop_session(client, resume_loop_id=None)
```

## Layout (RFC-629 Layer 0)

| Module | Role |
|--------|------|
| `websocket` | Protocol-1 `WebSocketClient` |
| `session` | Connect retries + loop bootstrap |
| `helpers` | Daemon status / config / skills RPCs |
| `ws_command_client` | Sync/async command helpers |
| `protocol_params` | Client-side params models |
| `intent_hints` | Loop input intent-hint validation |

Shared wire codec and path constants remain in **soothe-sdk**
(`soothe_sdk.wire`, `soothe_sdk.paths`) so the daemon can use them without
depending on this client package.

## Development (monorepo)

```bash
# from soothe repo root
uv sync --all-packages
uv run pytest client/python/tests/unit -q
```
