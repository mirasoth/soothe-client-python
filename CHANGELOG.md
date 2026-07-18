# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-18

### Changed
- Mark the WebSocket client API as stable 1.0 (`DaemonSession` / `CommandClient` / `Client`, protocol-1)
- Require `soothe-sdk>=1.0.0,<2.0.0`; canonical `preferred_subagent` values (`explorer`, `deep_research`, …)

## [0.10.2] - 2026-07-18

### Changed
- Examples and tests use canonical `preferred_subagent` values `explorer` / `deep_research`

## [0.10.1] - 2026-07-17

### Changed
- Require `soothe-sdk>=1.0.0` (stable SDK; canonical package-level imports only)

## [0.10.0] - 2026-07-17

### Changed
- **Breaking:** command clients are `AsyncCommandClient` / `CommandClient` (module `soothe_client.command_client`); removed `WsCommandClient`, `SyncWsCommandClient`, and `*_ws_command_client_from_config` aliases
- **Breaking:** removed root-package re-export of `*Params` (including deprecated `__getattr__`); import from `soothe_client.protocol_params`

## [0.9.10] - 2026-07-16

### Added
- `autopilot_cancel_all` RPC helper to cancel every open (non-terminal) goal in one call
- Preferred aliases: `AsyncCommandClient`, `CommandClient`, `command_client_from_config`, `async_command_client_from_config`

### Changed
- Slimmed package and `appkit` public exports; wire `*Params` models live in `soothe_client.protocol_params` (root import still works with a deprecation warning)

## [0.9.9] - 2026-07-16

### Fixed
- Rebind `expected_turn_id` when a newer `status=running` arrives so a stale/early prior generation cannot drop the active turn

## [0.9.8] - 2026-07-16

### Added
- `turn_id` / `seq` boundary helpers; `DaemonSession` binds turn on `status=running` and drops mismatched or stale-seq frames

### Changed
- Prefer stamped turn boundaries over subscription `complete` for long-lived loop streams

## [0.9.7] - 2026-07-16

### Fixed
- Ignore stale turn-end frames (`complete` / `soothe.stream.end`) left over from a prior goal before the next query starts

### Changed
- Shared stream-terminal detection helpers; mypy is required in `make verify` and CI

## [0.9.6] - 2026-07-16

### Added
- `connected_websocket` / `protocol1_rpc` helpers for oneshot Typer / TUI RPCs
- Live-daemon `tests/integration/` suite and `make test-integration`
- Runnable agent examples (`examples/01`–`06`) with `make test-examples` (live) / `make test-examples-offline`
- `pillow` as a default dependency (removed optional `[image]` extra)

### Changed
- Require `soothe-sdk>=0.8.1` (canonical `soothe_sdk.wire` / `soothe_sdk.paths`)
- Public package docs/README are end-user facing
- Examples default to fast `text_completion` (`SOOTHE_EXAMPLE_AGENT=1` for full agent)

### Fixed
- `WebSocketManagedClient.send_message` coerces flat appkit payloads to protocol-1 envelopes
- `DaemonSession.iter_turn_chunks` ends on turn-scoped `soothe.stream.end` and supports `max_wait_s`
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
