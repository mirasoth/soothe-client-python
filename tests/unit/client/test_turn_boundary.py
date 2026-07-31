"""Unit tests for turn_id / seq helpers (IG-616)."""

from __future__ import annotations

from soothe_client.turn_boundary import (
    format_turn_id,
    frame_seq,
    frame_turn_id,
    is_idle_terminal_allowed,
    is_turn_terminal_allowed,
    parse_turn_generation,
    turn_ids_match,
)


def test_format_and_parse_turn_id() -> None:
    assert format_turn_id("loop-a", 3) == "loop-a:3"
    assert format_turn_id("", 1) == ""
    assert format_turn_id("loop-a", 0) == ""
    assert parse_turn_generation("loop-a:3") == 3
    assert parse_turn_generation("bad") is None
    assert parse_turn_generation(None) is None


def test_frame_turn_id_and_seq() -> None:
    assert frame_turn_id({"turn_id": "L:1"}) == "L:1"
    assert frame_turn_id({"data": {"turn_id": "L:2"}}) == "L:2"
    assert frame_seq({"seq": 7}) == 7
    assert frame_seq({"seq": True}) is None
    assert frame_seq({}) is None


def test_turn_ids_match_rejects_absent() -> None:
    assert turn_ids_match("L:1", "L:1")
    assert not turn_ids_match("L:1", None)
    assert not turn_ids_match(None, "L:1")
    assert not turn_ids_match("L:1", "")
    assert not turn_ids_match("L:1", "L:2")


def test_turn_terminal_requires_bound_matching_id() -> None:
    assert not is_turn_terminal_allowed(
        expected_turn_id=None,
        frame_turn_id="L:1",
        query_started=True,
        turn_progress_seen=True,
    )
    assert not is_turn_terminal_allowed(
        expected_turn_id="L:1",
        frame_turn_id=None,
        query_started=True,
        turn_progress_seen=True,
    )
    assert is_turn_terminal_allowed(
        expected_turn_id="L:1",
        frame_turn_id="L:1",
        query_started=True,
        turn_progress_seen=True,
    )


def test_idle_terminal_requires_progress_or_cancel() -> None:
    assert not is_idle_terminal_allowed(
        expected_turn_id="L:1",
        frame_turn_id="L:1",
        query_started=True,
        turn_progress_seen=False,
        cancellation_seen=False,
    )
    assert is_idle_terminal_allowed(
        expected_turn_id="L:1",
        frame_turn_id="L:1",
        query_started=True,
        turn_progress_seen=False,
        cancellation_seen=True,
    )
    # Absent idle id: cancel-only escape hatch.
    assert is_idle_terminal_allowed(
        expected_turn_id="L:1",
        frame_turn_id=None,
        query_started=True,
        turn_progress_seen=True,
        cancellation_seen=False,
    ) is False
    assert is_idle_terminal_allowed(
        expected_turn_id="L:1",
        frame_turn_id=None,
        query_started=True,
        turn_progress_seen=False,
        cancellation_seen=True,
    )
