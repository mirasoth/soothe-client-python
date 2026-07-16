"""Application helpers built on WebSocketClient.

Primary building blocks for agent UIs and backends:

- ``DaemonSession`` — dual-socket loop session + streamed turns
- ``ConnectionPool`` / ``TurnRunner`` — multi-session turn execution
- ``QueryGate`` — one-in-flight query per session
- ``EventClassifier`` — stream → deliverable mapping
- ``SSEBroadcaster`` — drop-on-full fan-out to subscribers
- ``SessionStore`` — persistence seam (Protocol)

Advanced stream/pipeline plumbing lives in submodules
(``events``, ``chunk_filter``, ``turn``, ``managed_client``).
"""

from __future__ import annotations

from soothe_client.appkit.attachments import (
    CompactImageOptions,
    compact_attachments,
    compact_image_attachment,
)
from soothe_client.appkit.broadcaster import SSEBroadcaster, SSEEvent
from soothe_client.appkit.classifier import (
    EVENT_FINAL_REPORT,
    ChatEventResult,
    ChatEventTerminal,
    ClassifierConfig,
    EventClassifier,
)
from soothe_client.appkit.daemon_session import DaemonSession
from soothe_client.appkit.pool import (
    ConnectionPool,
    ErrPoolExhausted,
    PoolConfig,
    PooledConn,
    default_pool_config,
)
from soothe_client.appkit.query_gate import ErrQueryBusy, QueryGate
from soothe_client.appkit.session_store import SessionEntry, SessionMessage, SessionStore
from soothe_client.appkit.thinking_step import (
    DEFAULT_THINKING_STEP_EVENTS,
    extract_thinking_step,
)
from soothe_client.appkit.turn_runner import (
    STREAM_CLOSE_FAIL,
    STREAM_CLOSE_SOFT_COMPLETE,
    Attachment,
    ErrIdleTimeout,
    ErrQueryTimeout,
    InputOpts,
    OnComplete,
    OnError,
    StreamClosePolicy,
    TimeoutPolicy,
    TurnConfig,
    TurnRunner,
    idle_timeout_for_turn,
    input_message_for_loop,
)

__all__ = [
    "DEFAULT_THINKING_STEP_EVENTS",
    "STREAM_CLOSE_FAIL",
    "STREAM_CLOSE_SOFT_COMPLETE",
    "Attachment",
    "ChatEventResult",
    "ChatEventTerminal",
    "ClassifierConfig",
    "CompactImageOptions",
    "ConnectionPool",
    "DaemonSession",
    "EVENT_FINAL_REPORT",
    "ErrIdleTimeout",
    "ErrPoolExhausted",
    "ErrQueryBusy",
    "ErrQueryTimeout",
    "EventClassifier",
    "InputOpts",
    "OnComplete",
    "OnError",
    "PoolConfig",
    "PooledConn",
    "QueryGate",
    "SSEBroadcaster",
    "SSEEvent",
    "SessionEntry",
    "SessionMessage",
    "SessionStore",
    "StreamClosePolicy",
    "TimeoutPolicy",
    "TurnConfig",
    "TurnRunner",
    "compact_attachments",
    "compact_image_attachment",
    "default_pool_config",
    "extract_thinking_step",
    "idle_timeout_for_turn",
    "input_message_for_loop",
]
