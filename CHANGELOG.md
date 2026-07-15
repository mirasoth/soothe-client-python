# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
