"""Soothe WebSocket client for talking to a running soothe-daemon.

Public surface::

    from soothe_client import WebSocketClient, is_daemon_live
    from soothe_client import AsyncCommandClient, CommandClient
    from soothe_client.appkit import DaemonSession

Wire request param models: ``soothe_client.protocol_params``.
Session / multi-user helpers: ``soothe_client.appkit``.
"""

from __future__ import annotations

import importlib.metadata

from soothe_sdk.wire.codec import ProtocolError

from soothe_client.command_client import (
    AsyncCommandClient,
    CommandClient,
    async_command_client_from_config,
    command_client_from_config,
)
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

try:
    __version__ = importlib.metadata.version("soothe-client-python")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"

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
    # Command clients
    "AsyncCommandClient",
    "CommandClient",
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
