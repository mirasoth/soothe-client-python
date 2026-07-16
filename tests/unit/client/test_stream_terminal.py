"""Unit tests for shared stream/turn terminal helpers."""

from soothe_client.stream_terminal import (
    STRANGE_LOOP_COMPLETED,
    STREAM_END,
    is_turn_end_custom_data,
    stale_pending_frame_label,
)


def test_is_turn_end_custom_data_scopes_stream_end() -> None:
    assert is_turn_end_custom_data({"type": STREAM_END, "scope": "turn"})
    assert is_turn_end_custom_data({"type": STREAM_END})
    assert not is_turn_end_custom_data({"type": STREAM_END, "scope": "step"})
    assert is_turn_end_custom_data({"type": STRANGE_LOOP_COMPLETED})
    assert not is_turn_end_custom_data({"type": "soothe.test"})


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
