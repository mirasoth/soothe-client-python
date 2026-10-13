"""Client-side UX event processing helpers.

Classification, loop-tagged assistant output phases, task/execute namespaces,
and stream tool wire constants. (TUI-owned subagent render helpers moved to
`soothe_cli.ux` in 1.2.0.)
"""

from soothe_client.ux.classification import classify_event_to_tier
from soothe_client.ux.loop_stream import LOOP_ASSISTANT_OUTPUT_PHASES, assistant_output_phase
from soothe_client.ux.types import ESSENTIAL_EVENT_TYPES

__all__ = [
    # Loop assistant output (``mode="messages"`` + ``phase``)
    "LOOP_ASSISTANT_OUTPUT_PHASES",
    "assistant_output_phase",
    # Classification
    "classify_event_to_tier",
    # Essential types
    "ESSENTIAL_EVENT_TYPES",
]
