"""Unit tests for shared stream/turn terminal helpers."""

from soothe_sdk.core.events import CARD_CREATED, CARD_FINALIZED, CARD_UPDATED

from soothe_client.appkit import CardProjection
from soothe_client.stream_terminal import (
    STRANGE_LOOP_COMPLETED,
    STREAM_END,
    is_turn_end_custom_data,
    is_turn_progress_chunk,
    stale_pending_frame_label,
)


def test_is_turn_end_custom_data_scopes_stream_end() -> None:
    assert is_turn_end_custom_data({"type": STREAM_END, "scope": "turn"})
    assert is_turn_end_custom_data({"type": STREAM_END})
    assert not is_turn_end_custom_data({"type": STREAM_END, "scope": "step"})
    assert is_turn_end_custom_data({"type": STRANGE_LOOP_COMPLETED})
    assert not is_turn_end_custom_data({"type": "soothe.test"})


def test_is_stream_end_cancel_reason() -> None:
    from soothe_client.stream_terminal import is_stream_end_cancel_reason

    assert is_stream_end_cancel_reason("cancelled")
    assert is_stream_end_cancel_reason("Canceled")
    assert is_stream_end_cancel_reason("client_disconnect")
    assert not is_stream_end_cancel_reason("completed")
    assert not is_stream_end_cancel_reason(None)
    assert not is_stream_end_cancel_reason("")


def test_is_turn_progress_chunk_excludes_intake_plan_phase() -> None:
    assert is_turn_progress_chunk("messages", {"type": "ai", "content": "hi"})
    assert is_turn_progress_chunk(
        "custom",
        {"type": "soothe.cognition.strange_loop.step.started", "step_id": "S1"},
    )
    assert not is_turn_progress_chunk(
        "custom",
        {"type": "soothe.cognition.strange_loop.plan.phase", "label": "Interpreting goal"},
    )
    assert not is_turn_progress_chunk("custom", {"type": STREAM_END, "scope": "turn"})
    assert is_turn_progress_chunk("custom", {"type": CARD_CREATED, "data": {"id": "c1"}})
    assert is_turn_progress_chunk("custom", {"type": CARD_UPDATED, "card_id": "c1"})
    assert is_turn_progress_chunk("custom", {"type": CARD_FINALIZED, "card_id": "c1"})


def test_card_projection_applies_soothe_card_frames() -> None:
    proj = CardProjection()
    assert proj.apply(
        {
            "type": CARD_CREATED,
            "data": {
                "id": "c1",
                "type": "assistant",
                "content": "hello",
            },
        }
    )
    assert proj.get("c1") is not None
    assert proj.apply({"type": CARD_UPDATED, "card_id": "c1", "data": {"content": "hi"}})
    assert proj.get("c1") is not None
    assert proj.get("c1").content == "hi"  # type: ignore[union-attr]


def test_stale_pending_frame_label_matches_peel_vocabulary() -> None:
    assert stale_pending_frame_label({"type": "complete"}) == "complete"
    assert (
        stale_pending_frame_label(
            {
                "type": "event",
                "mode": "custom",
                "data": {"type": STREAM_END, "scope": "turn"},
            }
        )
        == STREAM_END
    )
    assert (
        stale_pending_frame_label(
            {
                "type": "event",
                "mode": "custom",
                "data": {"type": STREAM_END, "scope": "step"},
            }
        )
        is None
    )
    assert stale_pending_frame_label({"type": "status", "state": "running"}) is None
    assert stale_pending_frame_label({"type": "status", "state": "idle"}) == "status.idle"
    assert stale_pending_frame_label({"type": "status", "state": "stopped"}) == "status.stopped"
    assert (
        stale_pending_frame_label(
            {"type": "next", "payload": {"type": "status", "state": "stopped"}}
        )
        == "status.stopped"
    )
