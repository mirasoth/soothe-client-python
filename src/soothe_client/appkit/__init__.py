"""Reusable application-architecture layer over Layer 0 (RFC-629).

appkit is product-agnostic. Deliverable phases, persistence, and UI copy stay
in the application (e.g. soothe-cli). Building blocks:

- ``unwrap_next`` / ``is_loop_scoped_event`` — protocol-1 stream helpers
- ``QueryGate`` — single-flight cancel-before-context gating
- ``TurnEventPipeline`` — reader / processor / applier concurrency
- ``DaemonSession`` — dual-socket loop session + ``iter_turn_chunks``
- ``SessionStore`` — persistence seam (Protocol)

Pool / TurnRunner / EventClassifier / SSEBroadcaster parity with Go/TS follows
in later slices.
"""

from __future__ import annotations

from soothe_client.appkit.chunk_filter import should_drop_stream_chunk_early
from soothe_client.appkit.daemon_session import DEFAULT_POST_IDLE_DRAIN_S, DaemonSession
from soothe_client.appkit.events import is_loop_scoped_event, unwrap_next
from soothe_client.appkit.observability import TurnEventStats
from soothe_client.appkit.query_gate import ErrQueryBusy, QueryGate
from soothe_client.appkit.session_store import SessionEntry, SessionMessage, SessionStore
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
    "DaemonSession",
    "ErrQueryBusy",
    "PRIORITY_CRITICAL",
    "PRIORITY_HIGH",
    "PRIORITY_LOW",
    "PRIORITY_NORMAL",
    "QueryGate",
    "SessionEntry",
    "SessionMessage",
    "SessionStore",
    "TurnApplyBatcher",
    "TurnEventPipeline",
    "TurnEventStats",
    "is_loop_scoped_event",
    "run_turn_pipeline",
    "should_drop_stream_chunk_early",
    "unwrap_next",
]
