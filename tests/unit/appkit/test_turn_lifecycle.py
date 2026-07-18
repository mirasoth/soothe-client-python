"""Turn lifecycle tests (idle timeout, status-idle, soft-complete, attachments)."""

from __future__ import annotations

import asyncio
import base64
import io
from typing import Any

import pytest

from soothe_client.appkit import (
    ChatEventTerminal,
    ClassifierConfig,
    CompactImageOptions,
    ConnectionPool,
    ErrIdleTimeout,
    EventClassifier,
    PoolConfig,
    QueryGate,
    SessionEntry,
    SessionMessage,
    SSEBroadcaster,
    TimeoutPolicy,
    TurnConfig,
    TurnRunner,
    compact_attachments,
    compact_image_attachment,
    idle_timeout_for_turn,
)

TRIARCH_PHASES = frozenset({"text_completion", "goal_completion", "quiz"})


class MemStore:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionEntry] = {}
        self.msgs: dict[str, list[SessionMessage]] = {}

    async def get_session(self, session_id: str) -> SessionEntry | None:
        return self.sessions.get(session_id)

    async def create_session(
        self,
        workspace_id: str,
        session_id: str,
        loop_id: str,
        session_type: str,
    ) -> None:
        self.sessions[session_id] = SessionEntry(
            workspace_id=workspace_id,
            session_id=session_id,
            loop_id=loop_id,
            session_type=session_type,
        )

    async def update_last_used(self, session_id: str) -> None:
        return None

    async def increment_reset_count(self, session_id: str) -> None:
        return None

    async def get_loop_id_for_session(self, session_id: str) -> tuple[str, bool]:
        entry = self.sessions.get(session_id)
        if entry and entry.loop_id:
            return entry.loop_id, True
        return "", False

    async def append_message(self, session_id: str, message: SessionMessage) -> None:
        self.msgs.setdefault(session_id, []).append(message)

    def messages(self, session_id: str) -> list[SessionMessage]:
        return list(self.msgs.get(session_id, []))


class FakeClient:
    def __init__(
        self, events: list[Any] | None = None, *, paced: list[tuple[float, Any]] | None = None
    ) -> None:
        self.connected = False
        self.closed = False
        self._scripted = list(events or [])
        self._paced = list(paced or [])
        self.send_capture: list[dict[str, Any]] = []

    async def connect(self) -> None:
        self.connected = True

    async def reconnect(self) -> None:
        self.connected = True

    async def reattach_and_probe(self, loop_id: str) -> None:  # noqa: ARG002
        return None

    async def send_message(self, msg: Any) -> None:
        if isinstance(msg, dict):
            self.send_capture.append(msg)

    async def receive_messages(self, *, cancel_event: asyncio.Event | None = None):
        for delay, ev in self._paced:
            if cancel_event is not None and cancel_event.is_set():
                return
            if delay > 0:
                await asyncio.sleep(delay)
            yield ev
        for ev in self._scripted:
            if cancel_event is not None and cancel_event.is_set():
                return
            yield ev
        while cancel_event is None or not cancel_event.is_set():
            await asyncio.sleep(0.05)

    def is_disconnected(self) -> bool:
        return False

    def disconnect_cause(self) -> None:
        return None

    def is_connected(self) -> bool:
        return self.connected and not self.closed

    async def close(self) -> None:
        self.closed = True
        self.connected = False


async def _bootstrap(_c: Any, _w: str, _u: str) -> str:
    return "loop-fresh"


def _pool(store: MemStore, fake: FakeClient) -> ConnectionPool:
    pool = ConnectionPool(
        "ws://localhost:0",
        store,
        PoolConfig(pool_size=2),
        factory=lambda _url: fake,
    )
    return pool.with_bootstrap(_bootstrap)


def _triarch(*, treat_idle: bool = False) -> EventClassifier:
    return EventClassifier(
        ClassifierConfig(
            deliverable_phases=TRIARCH_PHASES,
            treat_status_idle_as_complete=treat_idle,
        )
    )


def test_idle_timeout_for_turn_floor() -> None:
    cfg = TurnConfig(idle_timeout_s=30.0, min_idle_timeout_with_attachments_s=90.0)
    assert idle_timeout_for_turn(cfg, True) == 90.0
    assert idle_timeout_for_turn(cfg, False) == 30.0
    assert idle_timeout_for_turn(TurnConfig(idle_timeout_s=0), True) == 0.0


def test_classifier_status_idle_opt_in() -> None:
    cl = _triarch(treat_idle=True)
    r = cl.classify(
        {"type": "status", "state": "idle", "loop_id": "L1"},
        "Hello, this is a long enough reply.",
    )
    assert r.terminal == ChatEventTerminal.DELIVERABLE_COMPLETE
    assert r.completion_event == "status.idle"


def test_classifier_status_idle_no_content_ignored() -> None:
    cl = _triarch(treat_idle=True)
    r = cl.classify({"type": "status", "state": "idle"}, "")
    assert r.terminal == ChatEventTerminal.CONTINUE


def test_classifier_status_idle_default_off() -> None:
    cl = _triarch(treat_idle=False)
    r = cl.classify(
        {"type": "status", "state": "idle"},
        "Hello, this is a long enough reply.",
    )
    assert r.terminal == ChatEventTerminal.CONTINUE


def test_classifier_skips_subscription_metadata() -> None:
    cl = _triarch()
    r = cl.classify(
        {
            "type": "next",
            "payload": {
                "mode": "event",
                "namespace": "soothe.output",
                "data": {
                    "type": "soothe.output.autonomous.final_report.reported",
                    "loop_id": "L1",
                    "latest_seq": 3,
                },
            },
        },
        "",
    )
    assert r.terminal == ChatEventTerminal.CONTINUE
    assert not r.content


@pytest.mark.asyncio
async def test_turn_runner_idle_timeout() -> None:
    store = MemStore()
    fake = FakeClient([])
    tr = TurnRunner(
        _pool(store, fake),
        QueryGate(),
        _triarch(),
        store,
        SSEBroadcaster(),
        TurnConfig(query_timeout_s=5.0, idle_timeout_s=0.05),
    )
    with pytest.raises(ErrIdleTimeout):
        await tr.execute("s1", "hi", "u", "ws", None, None)
    assert store.messages("s1")[0].role == "error"


@pytest.mark.asyncio
async def test_turn_runner_idle_soft_complete() -> None:
    store = MemStore()
    # Stream a chunk, then go silent until idle soft-completes.
    chunk = {
        "type": "next",
        "payload": {
            "mode": "messages",
            "data": [{"type": "AIMessageChunk", "content": "Partial answer here!!"}],
        },
    }
    fake = FakeClient([chunk])
    tr = TurnRunner(
        _pool(store, fake),
        QueryGate(),
        _triarch(),
        store,
        SSEBroadcaster(),
        TurnConfig(
            query_timeout_s=5.0,
            idle_timeout_s=0.08,
            on_idle_timeout=TimeoutPolicy.SOFT_COMPLETE,
        ),
    )
    await tr.execute("s1", "hi", "u", "ws", None, None)
    msgs = store.messages("s1")
    assert msgs and msgs[0].role == "assistant"
    assert "Partial" in msgs[0].content


@pytest.mark.asyncio
async def test_turn_runner_stream_close_soft_complete() -> None:
    store = MemStore()

    class ClosingFake(FakeClient):
        async def receive_messages(self, *, cancel_event: asyncio.Event | None = None):
            yield {
                "type": "next",
                "payload": {
                    "mode": "messages",
                    "data": [{"type": "AIMessageChunk", "content": "Closed midstream reply."}],
                },
            }
            return

    fake = ClosingFake()
    tr = TurnRunner(
        _pool(store, fake),
        QueryGate(),
        _triarch(),
        store,
        SSEBroadcaster(),
        TurnConfig(query_timeout_s=5.0, on_stream_close=TimeoutPolicy.SOFT_COMPLETE),
    )
    await tr.execute("s1", "hi", "u", "ws", None, None)
    assert store.messages("s1")[0].role == "assistant"


def test_compact_non_image_passthrough() -> None:
    mime, data = compact_image_attachment("application/pdf", "AAAA")
    assert mime == "application/pdf"
    assert data == "AAAA"


def test_compact_attachments_copies() -> None:
    atts = [{"mime_type": "text/plain", "data": "QQ==", "name": "a"}]
    out = compact_attachments(atts)
    assert out[0]["name"] == "a"
    assert out is not atts


def test_compact_image_with_pillow() -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    img = Image.new("RGB", (1200, 800), color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    out_mime, out_data = compact_image_attachment(
        "image/jpeg",
        data,
        CompactImageOptions(max_dim=200, jpeg_quality=80),
    )
    assert out_mime == "image/jpeg"
    raw = base64.b64decode(out_data)
    with Image.open(io.BytesIO(raw)) as resized:
        assert max(resized.size) <= 200
