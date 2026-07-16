"""Public export surface for soothe-client-python."""

from __future__ import annotations

import warnings

import soothe_client as root
from soothe_client import appkit


def test_root_all_excludes_protocol_params() -> None:
    assert "LoopInputParams" not in root.__all__
    assert "AutopilotCancelGoalParams" not in root.__all__
    assert "VerbosityLevel" not in root.__all__


def test_root_all_includes_core_surface() -> None:
    for name in (
        "WebSocketClient",
        "WsCommandClient",
        "SyncWsCommandClient",
        "AsyncCommandClient",
        "CommandClient",
        "command_client_from_config",
        "async_command_client_from_config",
        "DaemonError",
        "is_daemon_live",
        "TEXT_COMPLETION",
    ):
        assert name in root.__all__
        assert getattr(root, name) is not None


def test_command_client_aliases() -> None:
    assert root.AsyncCommandClient is root.WsCommandClient
    assert root.CommandClient is root.SyncWsCommandClient
    assert root.command_client_from_config is root.ws_command_client_from_config
    assert root.async_command_client_from_config is root.async_ws_command_client_from_config


def test_legacy_params_via_getattr_warn() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cls = root.LoopInputParams
    assert cls.__name__ == "LoopInputParams"
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_appkit_all_is_slim() -> None:
    demoted = {
        "should_drop_stream_chunk_early",
        "unwrap_next",
        "is_loop_scoped_event",
        "DEFAULT_POST_IDLE_DRAIN_S",
        "TurnEventPipeline",
        "TurnApplyBatcher",
        "run_turn_pipeline",
        "ManagedClient",
        "WebSocketManagedClient",
        "PRIORITY_HIGH",
    }
    for name in demoted:
        assert name not in appkit.__all__

    for name in ("DaemonSession", "ConnectionPool", "TurnRunner", "QueryGate"):
        assert name in appkit.__all__
        assert getattr(appkit, name) is not None
