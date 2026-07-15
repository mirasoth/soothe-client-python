# Integration tests (live soothe-daemon)

## Prerequisites

`soothed` listening on `SOOTHE_WS_URL` (default `ws://127.0.0.1:8765`).

## Run

```bash
make test-integration
# or:
SOOTHE_INTEGRATION=1 uv run pytest tests/integration -v
```

## Skip forcing

```bash
SOOTHE_INTEGRATION=0 make test-integration
```

## Behaviour

- Daemon unreachable → tests are **skipped** (unless `SOOTHE_INTEGRATION=1`, then **fail**)
- Not part of default `make test` / CI (unit + examples only)
