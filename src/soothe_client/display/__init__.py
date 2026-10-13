"""Client-side display-layer contract parsing.

This package hosts the wire-protocol parse side shared by the transport,
appkit, and any Python front end:

* ``transcript_types`` — ``MessageData`` / ``MessageType`` / ``ToolStatus``
  dataclasses travelling on the wire.
* ``card_ledger`` — pure-Python ``CardMutation`` + ``InMemoryCardLedger``
  primitives backing the ``soothe.card.*`` wire schema.
* ``card_wire`` — parse/apply helpers for live ``soothe.card.*`` frames.
* ``snapshot_types`` — goal display snapshot wire payload types.
* ``message_processing`` / ``tool_result`` / ``tool_message_format`` —
  stream-to-text parse helpers.

(TUI-owned ``card_binder`` / ``text_extract`` / ``snapshot_collapser`` moved
to `soothe_cli.display` / the host `soothe.display` in 1.2.0.)
"""

from __future__ import annotations

from soothe_client.display.card_ledger import (
    CARD_SCHEMA_VERSION,
    CardMutation,
    CardOp,
    InMemoryCardLedger,
    align_cards_preserving_ids,
    build_header_mutation,
    card_from_wire_dict,
    card_to_wire_dict,
    cards_to_mutations,
    diff_card_snapshots,
    utc_now_iso,
)
from soothe_client.display.card_wire import (
    CardProjection,
    parse_card_custom_payload,
)
from soothe_client.display.snapshot_types import (
    GOAL_DISPLAY_SNAPSHOT_SCHEMA_VERSION,
    GoalDisplaySnapshot,
    snapshot_from_dataclass_dict,
)
from soothe_client.display.transcript_types import (
    UPDATABLE_FIELDS,
    MessageData,
    MessageType,
    ToolStatus,
)

__all__ = [
    # Types
    "MessageData",
    "MessageType",
    "ToolStatus",
    "UPDATABLE_FIELDS",
    # Ledger
    "CARD_SCHEMA_VERSION",
    "CardMutation",
    "CardOp",
    "InMemoryCardLedger",
    "build_header_mutation",
    "card_from_wire_dict",
    "card_to_wire_dict",
    "cards_to_mutations",
    "diff_card_snapshots",
    "align_cards_preserving_ids",
    "utc_now_iso",
    # Card wire
    "CardProjection",
    "parse_card_custom_payload",
    # Goal display snapshots
    "GOAL_DISPLAY_SNAPSHOT_SCHEMA_VERSION",
    "GoalDisplaySnapshot",
    "snapshot_from_dataclass_dict",
]
