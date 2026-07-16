"""Soothe WebSocket client for talking to a running soothe-daemon.

Public surface (community apps)::

    from soothe_client import WebSocketClient, is_daemon_live
    from soothe_client.appkit import DaemonSession
    from soothe_client import AsyncCommandClient, CommandClient  # preferred aliases

Advanced wire validation lives in ``soothe_client.protocol_params``.
Higher-level session / multi-user helpers live in ``soothe_client.appkit``.
"""

from __future__ import annotations

import importlib.metadata
import warnings
from typing import Any

from soothe_sdk.wire.codec import ProtocolError

from soothe_client.errors import (
    DaemonError,
    DisconnectCause,
    ReconnectError,
    StaleLoopError,
    disconnect_cause_name,
)
from soothe_client.helpers import (
    check_daemon_status,
    connected_websocket,
    fetch_config_section,
    fetch_loop_cards,
    fetch_loop_history,
    fetch_loop_messages,
    fetch_skills_catalog,
    is_daemon_live,
    protocol1_rpc,
    request_daemon_config_reload,
    request_daemon_shutdown,
    websocket_url_from_config,
)
from soothe_client.intent_hints import (
    DEFAULT_DELIVERABLE_PHASES,
    EMBED,
    IMAGE_TO_TEXT,
    OCR,
    TEXT_COMPLETION,
    validate_loop_input_intent_hint,
)
from soothe_client.session import (
    bootstrap_loop_session,
    connect_websocket_with_retries,
)
from soothe_client.websocket import WebSocketClient
from soothe_client.ws_command_client import (
    AsyncCommandClient,
    CommandClient,
    SyncWsCommandClient,
    WsCommandClient,
    async_command_client_from_config,
    async_ws_command_client_from_config,
    command_client_from_config,
    ws_command_client_from_config,
)

try:
    __version__ = importlib.metadata.version("soothe-client-python")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"

# Legacy ``*Params`` names formerly re-exported at package root.
_LEGACY_PARAM_NAMES = frozenset(
    {
        "AuthParams",
        "AuthRefreshParams",
        "AutopilotCancelAllParams",
        "AutopilotCancelGoalParams",
        "AutopilotDreamParams",
        "AutopilotGetGoalParams",
        "AutopilotGetJobParams",
        "AutopilotListGoalsParams",
        "AutopilotListJobsParams",
        "AutopilotResumeParams",
        "AutopilotStatusParams",
        "AutopilotSubmitParams",
        "AutopilotSubscribeParams",
        "AutopilotWakeParams",
        "ConfigGetParams",
        "ConfigReloadParams",
        "CronAddParams",
        "CronCancelParams",
        "CronListParams",
        "CronShowParams",
        "DaemonShutdownParams",
        "DaemonStatusParams",
        "DisconnectParams",
        "InvokeSkillParams",
        "JobCancelParams",
        "JobCreateParams",
        "JobDagParams",
        "JobGuidanceParams",
        "JobPauseParams",
        "JobResumeParams",
        "JobStatusParams",
        "LoopCardsFetchParams",
        "LoopDeleteParams",
        "LoopDetachParams",
        "LoopGetParams",
        "LoopInputParams",
        "LoopListParams",
        "LoopMessagesParams",
        "LoopNewParams",
        "LoopPruneParams",
        "LoopReattachParams",
        "LoopStateGetParams",
        "LoopStateUpdateParams",
        "LoopTreeParams",
        "McpStatusParams",
        "ModelsListParams",
        "RpcCommandParams",
        "SkillsListParams",
        "SlashCommandParams",
        "SubscribeParams",
    }
)

__all__ = [
    "__version__",
    # Transport
    "WebSocketClient",
    "ProtocolError",
    # Errors
    "DaemonError",
    "DisconnectCause",
    "ReconnectError",
    "StaleLoopError",
    "disconnect_cause_name",
    # Command clients (canonical + preferred aliases)
    "WsCommandClient",
    "SyncWsCommandClient",
    "AsyncCommandClient",
    "CommandClient",
    "ws_command_client_from_config",
    "async_ws_command_client_from_config",
    "command_client_from_config",
    "async_command_client_from_config",
    # Session bootstrap
    "bootstrap_loop_session",
    "connect_websocket_with_retries",
    # Helpers
    "websocket_url_from_config",
    "connected_websocket",
    "protocol1_rpc",
    "check_daemon_status",
    "is_daemon_live",
    "request_daemon_config_reload",
    "request_daemon_shutdown",
    "fetch_skills_catalog",
    "fetch_config_section",
    "fetch_loop_history",
    "fetch_loop_cards",
    "fetch_loop_messages",
    # Intent hints
    "TEXT_COMPLETION",
    "IMAGE_TO_TEXT",
    "OCR",
    "EMBED",
    "DEFAULT_DELIVERABLE_PHASES",
    "validate_loop_input_intent_hint",
]


def __getattr__(name: str) -> Any:
    """Lazy-load legacy ``*Params`` with a deprecation warning.

    Prefer ``from soothe_client.protocol_params import LoopInputParams``.
    """
    if name in _LEGACY_PARAM_NAMES:
        warnings.warn(
            f"Importing {name!r} from soothe_client is deprecated; "
            f"use soothe_client.protocol_params.{name} instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from soothe_client import protocol_params as _params

        return getattr(_params, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
