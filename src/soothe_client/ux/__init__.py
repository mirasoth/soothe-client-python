"""Display and UX concerns for event processing.

This package provides UX types, event classification logic,
loop-tagged assistant output helpers, and subagent helpers.
"""

from soothe_client.ux.classification import classify_event_to_tier
from soothe_client.ux.loop_stream import LOOP_ASSISTANT_OUTPUT_PHASES, assistant_output_phase
from soothe_client.ux.subagent_progress import get_subagent_name_from_event
from soothe_client.ux.subagent_wire_display import (
    SubagentWireRenderKind,
    classify_subagent_wire_render,
    subagent_wire_row_params,
)
from soothe_client.ux.types import ESSENTIAL_EVENT_TYPES

__all__ = [
    # Loop assistant output (``mode="messages"`` + ``phase``)
    "LOOP_ASSISTANT_OUTPUT_PHASES",
    "assistant_output_phase",
    # Classification
    "classify_event_to_tier",
    # Subagent helpers
    "get_subagent_name_from_event",
    "SubagentWireRenderKind",
    "classify_subagent_wire_render",
    "subagent_wire_row_params",
    # Essential types
    "ESSENTIAL_EVENT_TYPES",
]
