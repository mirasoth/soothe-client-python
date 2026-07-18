"""Unit tests for intent_hints deliverable phase set."""

from __future__ import annotations

from soothe_client.intent_hints import DEFAULT_DELIVERABLE_PHASES


def test_default_deliverable_phases_excludes_plan_direct() -> None:
    assert "plan_direct" not in DEFAULT_DELIVERABLE_PHASES


def test_default_deliverable_phases_includes_direct_hints() -> None:
    for phase in (
        "quiz",
        "goal_completion",
        "chitchat",
        "text_completion",
        "image_to_text",
        "ocr",
        "embed",
    ):
        assert phase in DEFAULT_DELIVERABLE_PHASES
    assert "direct_model" not in DEFAULT_DELIVERABLE_PHASES
