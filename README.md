# soothe-client-python

WebSocket client in Python for [soothe-daemon](https://github.com/mirasoth/soothe).

Peer of [`soothe-client-go`](https://github.com/mirasoth/soothe-client-go) and
[`@mirasoth/soothe-client`](https://github.com/mirasoth/soothe-client-typescript).

## Install

```bash
pip install soothe-client-python
# optional image compaction:
pip install 'soothe-client-python[image]'
# or, in the soothe monorepo workspace:
uv sync --all-packages
```

## Quick start

```python
from soothe_client import WebSocketClient, bootstrap_loop_session, connect_websocket_with_retries

client = WebSocketClient(url="ws://127.0.0.1:8765")
await connect_websocket_with_retries(client)
status = await bootstrap_loop_session(client, resume_loop_id=None)
```

## Layout (RFC-629)

### Layer 0 (transport)

| Module | Role |
|--------|------|
| `websocket` | Protocol-1 `WebSocketClient` |
| `session` | Connect retries + loop bootstrap |
| `helpers` | Daemon status / config / skills RPCs |
| `ws_command_client` | Sync/async command helpers |
| `protocol_params` | Client-side params models |
| `intent_hints` | Intent-hint validation + `DEFAULT_DELIVERABLE_PHASES` |

### Layer 1 (`soothe_client.appkit`)

| Symbol | Role |
|--------|------|
| `DaemonSession` | Dual-socket loop session + `iter_turn_chunks` (CLI-grade) |
| `QueryGate` | Single-flight cancel-before-context gating |
| `EventClassifier` / `extract_thinking_step` | Deliverable / thinking-step mapping |
| `SSEBroadcaster` | Drop-on-full SSE-style fan-out |
| `ConnectionPool` / `TurnRunner` | Pooled multi-session turn execution |
| Idle / soft-complete / `compact_*` | Turn lifecycle + optional Pillow compaction |
| `SessionStore` | Persistence seam (Protocol) |

```python
from soothe_client.appkit import DaemonSession

session = DaemonSession("ws://127.0.0.1:8765")
await session.connect()
await session.send_turn("hello")
async for namespace, mode, data in session.iter_turn_chunks():
    ...
```

Shared wire codec and path constants remain in **soothe-sdk**
(`soothe_sdk.wire`, `soothe_sdk.paths`).

## Development

From this repository (or the `client/python` submodule):

```bash
make sync-dev      # uv sync --extra dev --extra image
make fix           # ruff --fix + format
make check         # format-check + lint + unit tests
make test          # unit + examples
make verify        # format-check + lint + test + build
make publish-dry   # inspect upload without publishing
make publish       # PyPI (trusted publisher in CI, or UV_PUBLISH_TOKEN locally)
```

| Target | Purpose |
|--------|---------|
| `format` / `format-check` | Ruff format |
| `lint` / `lint-fix` / `fix` | Ruff lint (+ auto-fix) |
| `test` / `test-unit` / `test-examples` | Pytest |
| `test-coverage` | Coverage HTML under `htmlcov/` |
| `build` | `uv build` → `dist/` |
| `verify` | Full pre-publish gate |
| `version-patch` / `-minor` / `-major` | Bump `VERSION` |

Examples live under `examples/appkit/` (run with `make test-examples`).

## Release

GitHub Actions:

- **CI** (`.github/workflows/ci.yml`) — format, lint, tests on Python 3.11–3.13
- **Release** (`.github/workflows/release.yml`) — on GitHub Release publish, builds and uploads to PyPI via trusted publishing (skips if the `VERSION` already exists)
