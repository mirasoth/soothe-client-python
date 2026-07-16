"""Unit tests for turn_id / seq helpers (IG-659)."""

from __future__ import annotations

from soothe_client.turn_boundary import format_turn_id, frame_seq, frame_turn_id


def test_format_turn_id() -> None:
    assert format_turn_id("loop-a", 3) == "loop-a:3"
    assert format_turn_id("", 1) == ""
    assert format_turn_id("loop-a", 0) == ""


def test_frame_turn_id_and_seq() -> None:
    assert frame_turn_id({"turn_id": "L:1"}) == "L:1"
    assert frame_turn_id({"data": {"turn_id": "L:2"}}) == "L:2"
    assert frame_seq({"seq": 7}) == 7
    assert frame_seq({"seq": True}) is None
    assert frame_seq({}) is None
