# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.6] - 2026-07-16

### Added
- `connected_websocket` / `protocol1_rpc` helpers for oneshot Typer / TUI RPCs

## [0.9.5] - 2026-07-15

### Added
- Live-daemon `tests/integration/` suite (connection, helpers, loops, DaemonSession, pool/TurnRunner, jobs)
- `make test-integration` with skip-if-daemon-down / `SOOTHE_INTEGRATION=1` force-fail
- Runnable agent examples under `examples/01_*.py` … `06_*.py` (hello → pool → jobs)

### Changed
- Require `soothe-sdk>=0.8.1` (canonical `soothe_sdk.wire` / `soothe_sdk.paths`)
- Public package docs/README are end-user facing (no internal design-doc identifiers)
- `pillow` is a default dependency (removed optional `[image]` extra)

### Fixed
- `WebSocketManagedClient.send_message` coerces flat appkit payloads (`loop_input`, `command_request`) to protocol-1 envelopes so TurnRunner works against envelope-only daemons
- `DaemonSession.iter_turn_chunks` ends on turn-scoped `soothe.stream.end` and supports absolute `max_wait_s` timeouts
- Clearer handshake errors when the daemon is `stopped`, `error`, or `degraded`

## [0.9.4] - 2026-07-15

### Added
- `Makefile` with lint/format/fix/test/build/verify/publish and version bump targets
- GitHub Actions CI (3.11–3.13) and Release (PyPI trusted publishing)
- Appkit examples under `examples/appkit/`
- `DEFAULT_DELIVERABLE_PHASES` (excludes `plan_direct`)

## [0.9.3] - 2026-07-15

### Added
- Turn lifecycle (Go IG-651 parity): idle silence watchdog (`ErrIdleTimeout`), soft-complete policies, stream-close soft-complete, attachment compaction helpers
- Classifier `treat_status_idle_as_complete` and subscription metadata map skip

## [0.9.2] - 2026-07-15

### Added
- Appkit `ConnectionPool` / `PooledConn` / `ManagedClient` (session-scoped dial + reattach)
- Appkit `TurnRunner` with `input_message_for_loop`, `ErrQueryTimeout`, and SSE completion fan-out

## [0.9.1] - 2026-07-15

### Added
- Layer 0 disconnect signal: `DisconnectCause`, `wait_disconnected`, `set_disconnected_callback`, `reconnect`, `reattach_and_probe` (`StaleLoopError` / `ReconnectError`)
- `DaemonSession.ensure_connected` prefers reconnect + reattach probe (bootstrap fallback on stale loop)
- Appkit `EventClassifier` / `extract_thinking_step` / `SSEBroadcaster` (Go/TS parity)

## [0.9.0] - 2026-07-15

### Added
- Layer 0 loop RPCs on `WebSocketClient`: `loop_list`, `loop_get`, `loop_history_fetch`, `loop_cards_fetch`, `loop_messages`, `loop_state_get`, `loop_state_update`
- Helpers `fetch_loop_history`, `fetch_loop_cards`, `fetch_loop_messages`
- `soothe_client.appkit.DaemonSession` — dual-socket session with `iter_turn_chunks`, post-idle drain, reconnect, history/cards/state RPCs (promoted from soothe-cli)
- Appkit stream early-drop filter and `TurnEventStats`

### Changed
- Version bump to `0.9.0` for the production-facing daemon-session surface

## [0.8.2] - 2026-07-15

### Added
- Initial `soothe_client.appkit` package: `unwrap_next`, `QueryGate`, `TurnEventPipeline`, `SessionStore`

## [0.8.1] - 2026-07-15

### Added
- Initial Layer 0 extract from soothe-sdk (`WebSocketClient`, session bootstrap, helpers)
