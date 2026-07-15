"""Unit tests for EventClassifier, thinking_step, and SSEBroadcaster."""

from __future__ import annotations

import pytest

from soothe_client.appkit import (
    DEFAULT_THINKING_STEP_EVENTS,
    ChatEventTerminal,
    ClassifierConfig,
    EventClassifier,
    SSEBroadcaster,
    SSEEvent,
    extract_thinking_step,
)

TRIARCH_PHASES = frozenset(
    {
        "quiz",
        "goal_completion",
        "direct_model",
        "text_completion",
        "image_to_text",
        "ocr",
        "embed",
    }
)


def _triarch() -> EventClassifier:
    return EventClassifier(ClassifierConfig(deliverable_phases=TRIARCH_PHASES))


def _deliverable_next(phase: str, content: str) -> dict:
    return {
        "type": "next",
        "payload": {
            "namespace": ["soothe", "protocol"],
            "mode": "messages",
            "data": {
                "mode": "messages",
                "data": [{"type": "AIMessage", "phase": phase, "content": content}],
            },
        },
    }


def _streaming_chunk_next(content: str) -> dict:
    return {
        "type": "next",
        "payload": {
            "mode": "messages",
            "data": {
                "mode": "messages",
                "data": [{"type": "AIMessageChunk", "content": content}],
            },
        },
    }


def test_classifier_rejects_empty_phases() -> None:
    with pytest.raises(ValueError, match="deliverable_phases"):
        EventClassifier(ClassifierConfig(deliverable_phases=set()))


def test_classifier_deliverable_phase() -> None:
    cl = _triarch()
    r = cl.classify(_deliverable_next("quiz", "Hello, this is the answer."), "")
    assert r.terminal == ChatEventTerminal.DELIVERABLE_COMPLETE
    assert r.completion_event is not None
    assert "quiz" in r.completion_event


def test_classifier_phase_not_in_config() -> None:
    cl = EventClassifier(ClassifierConfig(deliverable_phases=frozenset({"direct_model"})))
    r = cl.classify(_deliverable_next("quiz", "Hello, this is the answer."), "")
    assert r.terminal != ChatEventTerminal.DELIVERABLE_COMPLETE


def test_classifier_streaming_chunk_continue() -> None:
    cl = _triarch()
    r = cl.classify(_streaming_chunk_next("partial"), "")
    assert r.terminal == ChatEventTerminal.CONTINUE
    assert r.content == "partial"


def test_classifier_substantive_reply_guard() -> None:
    cl = _triarch()
    r = cl.classify(_deliverable_next("quiz", "..."), "")
    assert r.terminal != ChatEventTerminal.DELIVERABLE_COMPLETE


def test_classifier_error_envelope() -> None:
    cl = _triarch()
    r = cl.classify({"type": "error", "error": {"code": -32603, "message": "boom"}}, "")
    assert r.terminal == ChatEventTerminal.FAILED_COMPLETE
    assert r.err is not None
    assert "boom" in str(r.err)


def test_extract_thinking_step_plan_started() -> None:
    line, ok = extract_thinking_step(
        "soothe.cognition.plan.step.started",
        {"step_id": "1", "description": "Search docs"},
    )
    assert ok
    assert line == "Step 1: Search docs"


def test_extract_thinking_step_unknown_event() -> None:
    line, ok = extract_thinking_step("soothe.stream.token", {"text": "x"})
    assert not ok
    assert line == ""


def test_default_thinking_step_allowlist_nonempty() -> None:
    assert "soothe.tool.execution.started" in DEFAULT_THINKING_STEP_EVENTS


@pytest.mark.asyncio
async def test_sse_broadcaster_subscribe_broadcast_close() -> None:
    b = SSEBroadcaster()
    it, sub_id = b.subscribe("s1")
    b.broadcast("s1", SSEEvent(type="delta", data="hi"))
    b.broadcast("nope", SSEEvent(type="x"))  # unknown session: no raise
    agen = it.__aiter__()
    ev = await agen.__anext__()
    assert ev.type == "delta"
    assert ev.data == "hi"
    b.close("s1")
    with pytest.raises(StopAsyncIteration):
        await agen.__anext__()
    assert sub_id


@pytest.mark.asyncio
async def test_sse_broadcaster_drop_on_full() -> None:
    b = SSEBroadcaster()
    it, _ = b.subscribe("s1")
    for i in range(100):
        b.broadcast("s1", SSEEvent(type="delta", data=i))
    # Must not block (drop-on-full).
    b.broadcast("s1", SSEEvent(type="delta", data="overflow"))
    agen = it.__aiter__()
    first = await agen.__anext__()
    assert first.data == 0
    b.close("s1")
