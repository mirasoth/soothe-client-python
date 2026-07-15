"""Soothe WebSocket client for soothe-daemon.

Layer 0 transport and session helpers. Layer 1 application mechanics live in
``soothe_client.appkit``. Shared wire codec and path constants live in
soothe-sdk (`soothe_sdk.wire`, `soothe_sdk.paths`).
"""

from __future__ import annotations

import importlib.metadata

from soothe_sdk.core.types import VerbosityLevel
from soothe_sdk.wire.codec import ProtocolError

from soothe_client.helpers import (
    check_daemon_status,
    fetch_config_section,
    fetch_skills_catalog,
    is_daemon_live,
    request_daemon_config_reload,
    request_daemon_shutdown,
    websocket_url_from_config,
)
from soothe_client.intent_hints import (
    EMBED,
    IMAGE_TO_TEXT,
    OCR,
    TEXT_COMPLETION,
    validate_loop_input_intent_hint,
)
from soothe_client.protocol_params import (
    AuthParams,
    AuthRefreshParams,
    AutopilotSubscribeParams,
    ConfigGetParams,
    ConfigReloadParams,
    CronAddParams,
    CronCancelParams,
    CronListParams,
    CronShowParams,
    DaemonShutdownParams,
    DaemonStatusParams,
    DisconnectParams,
    InvokeSkillParams,
    JobCancelParams,
    JobCreateParams,
    JobDagParams,
    JobGuidanceParams,
    JobPauseParams,
    JobResumeParams,
    JobStatusParams,
    LoopCardsFetchParams,
    LoopDeleteParams,
    LoopDetachParams,
    LoopGetParams,
    LoopInputParams,
    LoopListParams,
    LoopMessagesParams,
    LoopNewParams,
    LoopPruneParams,
    LoopReattachParams,
    LoopStateGetParams,
    LoopStateUpdateParams,
    LoopTreeParams,
    McpStatusParams,
    ModelsListParams,
    RpcCommandParams,
    SkillsListParams,
    SlashCommandParams,
    SubscribeParams,
)
from soothe_client.session import (
    bootstrap_loop_session,
    connect_websocket_with_retries,
)
from soothe_client.websocket import WebSocketClient
from soothe_client.ws_command_client import (
    SyncWsCommandClient,
    WsCommandClient,
    async_ws_command_client_from_config,
    ws_command_client_from_config,
)

try:
    __version__ = importlib.metadata.version("soothe-client-python")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "__version__",
    "WebSocketClient",
    "VerbosityLevel",
    "ProtocolError",
    "WsCommandClient",
    "SyncWsCommandClient",
    "ws_command_client_from_config",
    "async_ws_command_client_from_config",
    "bootstrap_loop_session",
    "connect_websocket_with_retries",
    "websocket_url_from_config",
    "check_daemon_status",
    "is_daemon_live",
    "request_daemon_config_reload",
    "request_daemon_shutdown",
    "fetch_skills_catalog",
    "fetch_config_section",
    "TEXT_COMPLETION",
    "IMAGE_TO_TEXT",
    "OCR",
    "EMBED",
    "validate_loop_input_intent_hint",
    "LoopGetParams",
    "LoopListParams",
    "LoopTreeParams",
    "LoopPruneParams",
    "LoopDeleteParams",
    "LoopNewParams",
    "LoopReattachParams",
    "LoopInputParams",
    "LoopMessagesParams",
    "LoopStateGetParams",
    "LoopStateUpdateParams",
    "LoopCardsFetchParams",
    "LoopDetachParams",
    "SubscribeParams",
    "AutopilotSubscribeParams",
    "JobCreateParams",
    "JobStatusParams",
    "JobPauseParams",
    "JobResumeParams",
    "JobCancelParams",
    "JobDagParams",
    "JobGuidanceParams",
    "CronAddParams",
    "CronListParams",
    "CronShowParams",
    "CronCancelParams",
    "DaemonStatusParams",
    "DaemonShutdownParams",
    "ConfigGetParams",
    "ConfigReloadParams",
    "SkillsListParams",
    "ModelsListParams",
    "InvokeSkillParams",
    "McpStatusParams",
    "AuthParams",
    "AuthRefreshParams",
    "SlashCommandParams",
    "RpcCommandParams",
    "DisconnectParams",
]
