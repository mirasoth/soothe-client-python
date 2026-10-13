"""Tests for early stream chunk filtering in the client appkit."""

from __future__ import annotations

from soothe_client.appkit.chunk_filter import (
    should_drop_stream_chunk_early,
    updates_chunk_is_noop,
)


def test_updates_noop_without_interrupt() -> None:
    assert updates_chunk_is_noop({"messages": []}) is True
    assert updates_chunk_is_noop({"__interrupt__": []}) is False


def test_should_drop_empty_wire_dict() -> None:
    wire = ({"type": "ai", "data": {"type": "ai", "content": ""}}, {})
    assert should_drop_stream_chunk_early((), "messages", wire) is True


def test_should_keep_wire_dict_with_text() -> None:
    wire = ({"type": "ai", "data": {"type": "ai", "content": "hello"}}, {})
    assert should_drop_stream_chunk_early((), "messages", wire) is False


def test_should_keep_wire_dict_with_tool_calls() -> None:
    wire = (
        {
            "type": "ai",
            "data": {
                "type": "ai",
                "content": "",
                "tool_calls": [{"name": "edit_file", "id": "tc1", "args": {}}],
            },
        },
        {},
    )
    assert should_drop_stream_chunk_early((), "messages", wire) is False


def test_should_keep_wire_dict_with_reasoning_content() -> None:
    """Reasoning-only wire dict chunks must not be dropped."""
    wire = (
        {
            "type": "ai",
            "data": {
                "type": "ai",
                "content": "",
                "additional_kwargs": {"reasoning_content": "I should search first."},
            },
        },
        {},
    )
    assert should_drop_stream_chunk_early((), "messages", wire) is False


def test_should_drop_wire_dict_with_empty_reasoning_content() -> None:
    """Empty reasoning_content string should still be dropped."""
    wire = (
        {
            "type": "ai",
            "data": {
                "type": "ai",
                "content": "",
                "additional_kwargs": {"reasoning_content": ""},
            },
        },
        {},
    )
    assert should_drop_stream_chunk_early((), "messages", wire) is True
