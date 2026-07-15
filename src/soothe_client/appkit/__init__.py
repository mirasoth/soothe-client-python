"""Reusable application-architecture layer over Layer 0 (RFC-629).

appkit is product-agnostic. Deliverable phases, persistence, and UI copy stay
in the application (e.g. soothe-cli). Building blocks:

- ``unwrap_next`` / ``is_loop_scoped_event`` — protocol-1 stream helpers
- ``QueryGate`` — single-flight cancel-before-context gating
- ``TurnEventPipeline`` — reader / processor / applier concurrency
- ``DaemonSession`` — dual-socket loop session + ``iter_turn_chunks``
- ``EventClassifier`` / ``extract_thinking_step`` — deliverable terminal mapping
- ``SSEBroadcaster`` — drop-on-full SSE-style fan-out
- ``SessionStore`` — persistence seam (Protocol)

``ConnectionPool`` / ``TurnRunner`` product wiring follows in a later slice.
"""

from __future__ import annotations

from soothe_client.appkit.broadcaster import SSEBroadcaster, SSEEvent
from soothe_client.appkit.chunk_filter import should_drop_stream_chunk_early
from soothe_client.appkit.classifier import (
    EVENT_FINAL_REPORT,
    ChatEventResult,
    ChatEventTerminal,
    ClassifierConfig,
    EventClassifier,
)
from soothe_client.appkit.daemon_session import DEFAULT_POST_IDLE_DRAIN_S, DaemonSession
from soothe_client.appkit.events import is_loop_scoped_event, unwrap_next
from soothe_client.appkit.observability import TurnEventStats
from soothe_client.appkit.query_gate import ErrQueryBusy, QueryGate
from soothe_client.appkit.session_store import SessionEntry, SessionMessage, SessionStore
from soothe_client.appkit.thinking_step import (
    DEFAULT_THINKING_STEP_EVENTS,
    extract_thinking_step,
)
from soothe_client.appkit.turn import (
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_NORMAL,
    TurnApplyBatcher,
    TurnEventPipeline,
    run_turn_pipeline,
)

__all__ = [
    "DEFAULT_POST_IDLE_DRAIN_S",
    "DEFAULT_THINKING_STEP_EVENTS",
    "DaemonSession",
    "EVENT_FINAL_REPORT",
    "ErrQueryBusy",
    "ChatEventResult",
    "ChatEventTerminal",
    "ClassifierConfig",
    "EventClassifier",
    "PRIORITY_CRITICAL",
    "PRIORITY_HIGH",
    "PRIORITY_LOW",
    "PRIORITY_NORMAL",
    "QueryGate",
    "SSEBroadcaster",
    "SSEEvent",
    "SessionEntry",
    "SessionMessage",
    "SessionStore",
    "TurnApplyBatcher",
    "TurnEventPipeline",
    "TurnEventStats",
    "extract_thinking_step",
    "is_loop_scoped_event",
    "run_turn_pipeline",
    "should_drop_stream_chunk_early",
    "unwrap_next",
]
