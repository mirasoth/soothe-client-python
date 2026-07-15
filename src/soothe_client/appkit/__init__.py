"""Reusable application-architecture layer over Layer 0 (RFC-629).

appkit is product-agnostic. Deliverable phases, persistence, and UI copy stay
in the application (e.g. soothe-cli). Typical first building blocks:

- ``unwrap_next`` / ``is_loop_scoped_event`` — protocol-1 stream helpers
- ``QueryGate`` — single-flight cancel-before-context gating
- ``TurnEventPipeline`` — reader / processor / applier concurrency
- ``SessionStore`` — persistence seam (Protocol)

Pool / TurnRunner / EventClassifier parity with Go/TS follows in later slices.
"""

from __future__ import annotations

from soothe_client.appkit.events import is_loop_scoped_event, unwrap_next
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
    "is_loop_scoped_event",
    "run_turn_pipeline",
    "unwrap_next",
]
