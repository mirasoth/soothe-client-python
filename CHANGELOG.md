# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.17] - 2026-08-20

### Changed
- Require `soothe-sdk>=1.0.9,<2.0.0` to pick up the Langfuse callback-manager flattening fix and the `TraceBody` import-path compatibility shim.

## [1.0.16] - 2026-08-20

### Added
- `interaction_mode` parameter on `WebSocketClient.loop_input`, `invoke_skill`, and `DaemonSession` turn/skill helpers — forwards the CoreAgent interaction mode (`"agent"` / `"ask"`) for a turn. `None` lets the daemon fall back to its configured default.

## [1.0.15] - 2026-08-10

### Fixed
- `AsyncCommandClient` / `CommandClient` now set `max_size=10 MiB` on their short-lived WebSocket RPC connections, matching the daemon's `transport.websocket.max_frame_size` default. Previously they omitted `max_size`, so the `websockets` library fell back to its 1 MiB default and the daemon closed the connection with code 1009 (message too big) on large replies such as `autopilot_list_goals`.

## [1.0.13] - 2026-08-08

### Fixed
- Turn reader no longer binds leftover prior-gen `status=running` or ends on premature `status=stopped` without progress
- Peel pending `status=idle|stopped` at turn start; continue reading when a successor `status=running` arrives during post-idle drain

## [1.0.12] - 2026-08-07

### Changed
- Fix version bump for dependency sync

## [1.0.11] - 2026-08-06

### Changed
- `autopilot_submit` RPC wait timeout raised from the client default (30s) to 120s so placement analysis can complete

## [1.0.10] - 2026-08-05

### Added
- `autopilot_top(include_terminal=...)` — optional terminal-goal forest for CLI `top`
- `AutopilotTopParams.include_terminal` (default `false`)
- Optional `rail_id` on `autopilot_submit` (prior unreleased)

## [1.0.9] - 2026-07-31

### Changed
- Display card wire types renamed to `soothe.card.*` (`created` / `updated` / `finalized` / `replay.begin` / `replay.end`)

### Added
- `CardProjection` / `parseCardCustomPayload` for applying live card frames
- `EventCardUpdated` / `EventCardFinalized`; card frames count as turn progress

## [1.0.8] - 2026-07-30

### Added
- `DaemonSession.aupdate_loop_state` — merge partial StrangeLoop state via daemon `loop_state_update` (TUI interrupt cleanup / token persistence)
- `STREAM_END_CANCEL_REASONS` / `is_stream_end_cancel_reason()` for shared cancel-reason classification

### Fixed
- `DaemonSession` marks `last_turn_cancellation_seen` from `soothe.stream.end` cancel reasons (`cancelled` / `canceled` / `user_cancelled` / `client_disconnect`) and records `last_turn_stream_end_reason`

## [1.0.3] - 2026-07-19

### Added
- Offline example `test_example_turn_boundary`; unit coverage for stream.end gates, stopped, empty-content fail, phase early-complete

## [1.0.2] - 2026-07-19

### Changed
- `TurnRunner` always ends turns via `TurnBoundary` (DaemonSession contract: gated `soothe.stream.end` / `status.idle` / `status.stopped`). `EventClassifier` is content + optional phase early-complete only

### Added
- `TurnBoundary`, `TurnLifecycleGate`, `is_daemon_turn_end_event`

## [1.0.1] - 2026-07-19

### Removed
- Legacy `intent_hint` values `direct_llm`, `quiz`, and `direct_model` (rejected before send)
- Legacy loop phase `direct_model` from `DEFAULT_DELIVERABLE_PHASES`
- Unphased `mode=messages` AI text no longer auto-completes a turn

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
- Turn lifecycle (Go IG-608 parity): idle silence watchdog (`ErrIdleTimeout`), soft-complete policies, stream-close soft-complete, attachment compaction helpers
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
- Layer 0 loop RPCs on `WebSocketClient`: `loop_list`, `loop_get`, `loop_history_fetch`, `loop_messages`, `loop_state_get`, `loop_state_update`
- Helpers `fetch_loop_history`, `fetch_loop_messages`
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
