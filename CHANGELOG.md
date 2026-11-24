# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.2] - 2026-11-24

### Added

- Step retry/recovery meta on `STEP_PROGRESS` (`display.transcript_types.MessageData`): optional `step_retry_attempt` / `step_retry_max` / `step_recovered` / `step_prior_tool_calls` / `step_prior_duration_ms` (in-execution same-thread recovery), wired into the updatable-field set and the retry event binding branch.
- Wire-golden fixture refreshed with the host step-retry contract (pin updated).

[Compare with previous version]: https://github.com/mirasoth/soothe-client-python/compare/v1.2.1...v1.2.2

## [1.2.1] - 2026-11-16

### Changed

- Raised the `pillow` upper bound from `<12.0.0` to `<13.0.0` so the client is compatible with `soothe-nano` 2.0.9 (which pulls `browser-use>=1.0.0` → `pillow==12.3.0`).
- Aligned the tools registry with soothe-nano 2.0: category `execution` → `shell`, dropped stale `data` / `image` / `academic_research` entries, added the `placement` field; added a twin-drift unit test pinning the client registry to the nano one (`tests/unit/test_tools_twin.py`).
- Fixed `interaction_mode` docstrings on `stream_turn` / `invoke_skill` to enumerate all modes (`agent` / `ask` / `plan` / `bypass`).
- Event/phase parity fixes for the retained client-side copies:
  - `intent_hints.DEFAULT_DELIVERABLE_PHASES`: dropped `quiz` (no host producer), added `goal_interrupted`.
  - `appkit.thinking_step`: replaced dead progress events (`soothe.cognition.plan.step.*`, `soothe.lifecycle.iteration.started`, `soothe.agent.loop.*`, `soothe.cognition.plan.batch.started`, `soothe.tool.execution.*`) with live ones (`soothe.cognition.strange_loop.step.started/completed`, `soothe.tool.invocation.started/completed`).
  - WebSocket priority-drop check now matches the bare wire type `tool_call_updates_batch` (nano 2.0 `wire/stream_tool_wire.py`) instead of the removed `soothe.ux.stream_tool_wire.` prefix.

[Compare with previous version]: https://github.com/mirasoth/soothe-client-python/compare/v1.2.0...v1.2.1

## [1.2.0] - 2026-10-13

### Changed
- **Slim the display/ux surface to transport + wire-parse concerns** (placement review follow-up):
  - Removed `display.card_binder` (30 KB TUI transcript binder) and `display.text_extract` — the only consumer is the soothe TUI; both now live in `soothe_cli.display` (soothe-cli ships them itself and declares `langchain-core` directly).
  - Removed `ux.subagent_progress` / `ux.subagent_wire_display` — pure TUI rendering helpers, moved to `soothe_cli.ux`.
  - Removed `display.snapshot_collapser` — server-side goal-snapshot folding logic with no client-side consumer (the host copy in `soothe.display` is canonical).
  - `display.__init__` / `ux.__init__` barrels re-export only the retained wire-parse helpers; imports map: `from soothe_client.display.card_binder import X` → `from soothe_cli.display.card_binder import X`, `from soothe_client.ux.subagent_wire_display import X` → `from soothe_cli.ux.subagent_wire_display import X`.
- Kept (wire-protocol parse side, shared by transport + appkit): `card_wire`, `card_ledger`, `transcript_types`, `snapshot_types`, `message_processing`, `tool_result`, `tool_message_format`, `ux.classification`, `ux.loop_stream`, `ux.task_namespace`, `ux.execute_namespace`, `ux.stream_tool_wire`.

[Compare with previous version]: https://github.com/mirasoth/soothe-client-python/compare/v1.1.0...v1.2.0

## [1.1.0] - 2026-10-13

### Added
- Absorb the client-side shared contracts formerly provided by the `soothe-sdk` dependency (the SDK is being dissolved; `soothe-client-python` is the canonical home for the client-side copies, mirroring how the Go and Rust clients already ship their own codec):
  - `soothe_client.wire` — Protocol-1 codec (`WireEnvelope`, `ConnectionInit*`, `Batch*`, `ProtocolError`, encode/decode helpers) and `wire.protocol` (`decode_websocket_text` / `encode_websocket_text` / `WorkspaceMapping` / `preview_first`).
  - `soothe_client.core` — wire event type constants and models (`events`), verbosity tiers (`verbosity`), subagent wire helpers (`subagent_wire`).
  - `soothe_client.display` — card binder / ledger / wire parse helpers, transcript types (`MessageData`), message processing, tool result formatting, goal snapshot types.
  - `soothe_client.ux` — event classification, loop stream phases, task/execute namespaces, stream tool wire, subagent progress/display helpers.
  - `soothe_client.tools` — tool display metadata registry.
  - `soothe_client.utils` — formatting, CLI logging helpers (`GlobalInputHistory`, `resolve_cli_log_level`, `setup_logging`), parsing, serde.
  - `soothe_client.paths` — `SOOTHE_HOME` / `SOOTHE_DATA_DIR` constants and SQLite path resolvers.

### Changed
- Drop the `soothe-sdk` dependency; `langchain-core` is now a direct dependency (wire codec message serde). Internal imports switch from `soothe_sdk.*` to `soothe_client.*` one-to-one; the client version in the `connection_init` handshake is now read from this package instead of the SDK.

[Compare with previous version]: https://github.com/mirasoth/soothe-client-python/compare/v1.0.24...v1.1.0

## [1.0.24] - 2026-09-27

### Fixed
- `LoopInputParams.interaction_mode` and `InvokeSkillParams.interaction_mode` patterns now accept `plan` and `bypass` in addition to `agent` and `ask`, matching the daemon's accepted CoreAgent interaction modes.

## [1.0.23] - 2026-09-13

### Added
- `autopilot_rail_id` parameter on `DaemonSession.send_turn` and `WebSocketClient.send_input` — when set, the daemon binds a `LoopRailInterpreter` for this goal via `run_with_progress(autopilot_rail_id=…)`. Wire param `autopilot_rail_id` is emitted on `loop_input` when truthy.

## [1.0.22] - 2026-09-08

### Changed
- `DaemonSession.set_clarification_mode` accepts an optional `interaction_mode` (`"bypass"` to swap the running goal's CoreAgent graph to the bypass variant; `None` keeps the default graph). The RPC payload omits the field when `None`.

## [1.0.21] - 2026-09-01

### Fixed
- `ReconnectError` now subclasses `ConnectionError` instead of bare `Exception`, so callers that catch `ConnectionError` (the standard Python pattern for network failures) also catch reconnect exhaustion.

## [1.0.20] - 2026-08-27

### Changed
- Removed `loop_tree` and `loop_prune` convenience RPCs from `WebSocketClient` and their corresponding parameter classes — the daemon no longer exposes these endpoints, keeping the client API aligned with the daemon surface.

## [1.0.19] - 2026-08-26

### Added
- `DaemonSession.set_clarification_mode(mode)` — hot-swap the clarification mode on a running goal (RFC-622). Sends `loop_set_clarification_mode` on the RPC socket; returns `True` when the swap landed on a live goal, `False` when no goal is currently running.

## [1.0.18] - 2026-08-23

### Added
- `WebSocketClient` convenience methods for `loop_tree`, `loop_prune`, `loop_delete`, `loop_reattach`, `config_get`, `config_reload`, `daemon_shutdown`, `authenticate`, and `refresh_auth_token` — these previously existed only via `helpers.py` or the generic `request()` call; now they have first-class methods for parity with TypeScript and Rust clients.
- Integration tests for loop tree/prune/delete/reattach, config get/reload, and auth/refresh flows.
