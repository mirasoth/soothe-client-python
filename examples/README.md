# Examples

Runnable scripts that talk to a live **soothe-daemon**.

```bash
# from client/python
export SOOTHE_WS_URL=ws://127.0.0.1:8765   # optional
uv run python examples/01_hello.py

# Or run every live example:
make test-examples

# Examples default to fast text_completion. Full agent path:
#   SOOTHE_EXAMPLE_AGENT=1 uv run python examples/02_stream_turn.py
# Per-turn wait (seconds): SOOTHE_EXAMPLE_TIMEOUT=90
```

| Script | What it shows |
|--------|----------------|
| `01_hello.py` | Connect, create a loop, one prompt, print the reply |
| `02_stream_turn.py` | `DaemonSession` — stream chunks as they arrive |
| `03_text_completion.py` | Always uses `intent_hint=text_completion` |
| `04_multi_turn.py` | Follow-ups on the same loop |
| `05_pool_service.py` | `ConnectionPool` + `TurnRunner` (multi-session service style) |
| `06_jobs.py` | Create / status / cancel a background job |

Offline (no daemon) appkit demos remain under `examples/appkit/` (`make test-examples-offline`).
