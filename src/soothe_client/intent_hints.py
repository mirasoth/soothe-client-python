"""``loop_input.intent_hint`` constants."""

from __future__ import annotations

from typing import Final

TEXT_COMPLETION: Final = "text_completion"
IMAGE_TO_TEXT: Final = "image_to_text"
OCR: Final = "ocr"
EMBED: Final = "embed"

# Default deliverable phases for turn-ending replies (excludes plan_direct narration).
DEFAULT_DELIVERABLE_PHASES: frozenset[str] = frozenset(
    {
        "quiz",
        "goal_completion",
        "chitchat",
        "text_completion",
        "image_to_text",
        "ocr",
        "embed",
    }
)
