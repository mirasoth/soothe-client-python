"""Public export surface for soothe-client-python."""

from __future__ import annotations

import pytest

import soothe_client as root
from soothe_client import appkit


def test_root_all_excludes_protocol_params_and_legacy_names() -> None:
    for name in (
        "LoopInputParams",
        "AutopilotCancelGoalParams",
        "VerbosityLevel",
        "WsCommandClient",
        "SyncWsCommandClient",
        "ws_command_client_from_config",
        "async_ws_command_client_from_config",
    ):
        assert name not in root.__all__
        assert not hasattr(root, name)


def test_root_all_includes_core_surface() -> None:
    for name in (
        "WebSocketClient",
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


def test_legacy_params_not_importable_from_root() -> None:
    with pytest.raises(ImportError):
        from soothe_client import LoopInputParams  # noqa: F401


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
