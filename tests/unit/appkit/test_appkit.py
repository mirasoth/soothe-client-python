"""Unit tests for soothe_client.appkit."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from soothe_client.appkit import (
    PRIORITY_HIGH,
    PRIORITY_LOW,
    ErrQueryBusy,
    QueryGate,
    TurnApplyBatcher,
    TurnEventPipeline,
    is_loop_scoped_event,
    run_turn_pipeline,
    unwrap_next,
)


def test_unwrap_next_returns_inner_data() -> None:
    inner = {"type": "event", "loop_id": "L1", "data": {"x": 1}}
    frame = {
        "proto": "1",
        "type": "next",
        "payload": {"namespace": "n", "mode": "m", "data": inner},
    }
    assert unwrap_next(frame) == inner


def test_unwrap_next_passes_through_non_next() -> None:
    frame = {"type": "status", "state": "idle", "loop_id": "L1"}
    assert unwrap_next(frame) is frame


def test_is_loop_scoped_event_filters_status() -> None:
    assert is_loop_scoped_event(
        {"type": "status", "loop_id": "L1"},
        active_loop_id="L1",
    )
    assert not is_loop_scoped_event(
        {"type": "status", "loop_id": "L2"},
        active_loop_id="L1",
    )


def test_is_loop_scoped_event_unwraps_next() -> None:
    frame = {
        "type": "next",
        "payload": {
            "data": {"type": "event", "loop_id": "L1"},
        },
    }
    assert is_loop_scoped_event(frame, active_loop_id="L1")
    frame["payload"]["data"]["loop_id"] = "other"
    assert not is_loop_scoped_event(frame, active_loop_id="L1")


@pytest.mark.asyncio
async def test_query_gate_single_flight() -> None:
    gate = QueryGate()
    cancelled: list[str] = []

    def _cancel() -> None:
        cancelled.append("local")

    await gate.acquire("s1", _cancel)
    with pytest.raises(ErrQueryBusy):
        await gate.acquire("s1", _cancel)
    assert await gate.is_active("s1")
    await gate.release("s1")
    assert not await gate.is_active("s1")
    await gate.acquire("s1", _cancel)
    await gate.cancel("s1")
    assert cancelled == ["local"]
    assert not await gate.is_active("s1")


@pytest.mark.asyncio
async def test_query_gate_cancel_sends_daemon_first() -> None:
    gate = QueryGate()
    order: list[str] = []

    async def _send() -> None:
        order.append("daemon")

    def _cancel() -> None:
        order.append("local")

    await gate.acquire("s1", _cancel, _send)
    await gate.cancel("s1")
    assert order == ["daemon", "local"]


def test_turn_apply_batcher_flushes_on_high_priority() -> None:
    batcher: TurnApplyBatcher[str] = TurnApplyBatcher(max_batch_size=10, max_batch_delay_ms=50)

    @dataclass
    class _Plan:
        label: str
        priority: int = PRIORITY_LOW

    assert batcher.add(_Plan("low")) is False
    assert batcher.add(_Plan("high", priority=PRIORITY_HIGH)) is True
    batch = batcher.flush()
    assert [p.label for p in batch] == ["low", "high"]


@pytest.mark.asyncio
async def test_run_turn_pipeline_processes_chunks_in_order() -> None:
    received: list[Any] = []

    async def _source() -> Any:
        for item in [("ns", "custom", {"type": "t"}), ("", "messages", {"c": 1})]:
            yield item

    def _process(raw: Any) -> tuple[Any, ...]:
        return tuple(raw)

    async def _apply(prepared: tuple[Any, ...]) -> None:
        received.append(prepared)

    await run_turn_pipeline(_source(), _process, _apply)

    assert received == [
        ("ns", "custom", {"type": "t"}),
        ("", "messages", {"c": 1}),
    ]


@pytest.mark.asyncio
async def test_pipeline_propagates_processor_errors() -> None:
    loop = asyncio.get_running_loop()
    pipeline: TurnEventPipeline[None] = TurnEventPipeline(loop)

    def _boom(_raw: Any) -> None:
        raise ValueError("processor failed")

    pipeline.start_processor(_boom)
    await asyncio.to_thread(pipeline._inbound.put, ("", "updates", {}))

    with pytest.raises(ValueError, match="processor failed"):
        async for _item in pipeline.iter_prepared():
            pass

    pipeline.shutdown()
