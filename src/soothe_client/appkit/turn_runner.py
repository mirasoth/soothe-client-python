"""Turn runner for appkit.

Executes one query turn end-to-end: acquire a pooled connection, enforce
single-flight, send loop_input, consume the event stream, classify events,
resolve the deliverable, persist the reply, and broadcast completion.

Supports absolute query timeout, optional idle silence watchdog, soft-complete
policies, and optional attachment compaction before send.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from soothe_client.appkit.attachments import CompactImageOptions, compact_attachments
from soothe_client.appkit.broadcaster import SSEBroadcaster, SSEEvent
from soothe_client.appkit.classifier import ChatEventTerminal, EventClassifier
from soothe_client.appkit.pool import ConnectionPool, PooledConn
from soothe_client.appkit.query_gate import QueryGate
from soothe_client.appkit.session_store import SessionMessage, SessionStore
from soothe_client.intent_hints import validate_loop_input_intent_hint

Attachment = dict[str, Any]
OnComplete = Callable[[str, str, str, str, float], None]
OnError = Callable[[str, str, BaseException], None]
InputBuilder = Callable[
    [str, str, list[Attachment] | None, "InputOpts | None"],
    dict[str, Any],
]


class ErrQueryTimeout(Exception):  # noqa: N818 — match Go/TS name
    """Raised when a turn exceeds the configured query timeout (fail policy)."""

    def __init__(self) -> None:
        super().__init__("appkit: query timeout")


class ErrIdleTimeout(Exception):  # noqa: N818 — match Go name
    """Raised when no events arrive within IdleTimeout (fail policy)."""

    def __init__(self) -> None:
        super().__init__("appkit: idle timeout")


class TimeoutPolicy(IntEnum):
    """Fail vs soft-complete behaviour for idle, query, and stream-close."""

    FAIL = 0
    SOFT_COMPLETE = 1


StreamClosePolicy = TimeoutPolicy
STREAM_CLOSE_FAIL = TimeoutPolicy.FAIL
STREAM_CLOSE_SOFT_COMPLETE = TimeoutPolicy.SOFT_COMPLETE


@dataclass(slots=True)
class TurnConfig:
    """Configures a ``TurnRunner``."""

    query_timeout_s: float = 30 * 60
    idle_timeout_s: float = 0.0
    min_idle_timeout_with_attachments_s: float = 0.0
    on_idle_timeout: TimeoutPolicy = TimeoutPolicy.FAIL
    on_query_timeout: TimeoutPolicy = TimeoutPolicy.FAIL
    on_stream_close: TimeoutPolicy = TimeoutPolicy.FAIL
    compact_attachments_before_send: bool = False
    compact_image_opts: CompactImageOptions | None = None


@dataclass(slots=True)
class InputOpts:
    """Optional daemon hints on a ``loop_input`` payload."""

    intent_hint: str | None = None
    preferred_subagent: str | None = None
    response_schema: dict[str, Any] | None = None
    response_schema_name: str | None = None
    response_schema_strict: bool | None = None


def input_message_for_loop(
    text: str,
    loop_id: str,
    attachments: list[Attachment] | None = None,
    opts: InputOpts | None = None,
) -> dict[str, Any]:
    """Build a ``loop_input`` payload with optional attachments and hints."""
    msg: dict[str, Any] = {"type": "loop_input", "content": text}
    if loop_id:
        msg["loop_id"] = loop_id
    if attachments:
        msg["attachments"] = attachments
    if opts is not None:
        if opts.intent_hint and opts.intent_hint.strip():
            hint_err = validate_loop_input_intent_hint(opts.intent_hint)
            if hint_err:
                raise ValueError(hint_err)
            msg["intent_hint"] = opts.intent_hint.strip()
        if opts.preferred_subagent and opts.preferred_subagent.strip():
            msg["preferred_subagent"] = opts.preferred_subagent.strip()
        if opts.response_schema:
            msg["response_schema"] = opts.response_schema
        if opts.response_schema_name and opts.response_schema_name.strip():
            msg["response_schema_name"] = opts.response_schema_name.strip()
        if opts.response_schema_strict is not None:
            msg["response_schema_strict"] = opts.response_schema_strict
    return msg


def idle_timeout_for_turn(cfg: TurnConfig, has_attachments: bool) -> float:
    """Compute effective idle timeout seconds for one turn (0 = disabled)."""
    idle = cfg.idle_timeout_s
    if idle <= 0:
        return 0.0
    floor = cfg.min_idle_timeout_with_attachments_s
    if has_attachments and floor > 0 and idle < floor:
        return floor
    return idle


class TurnRunner:
    """Execute one query turn end-to-end."""

    def __init__(
        self,
        pool: ConnectionPool,
        gate: QueryGate,
        classifier: EventClassifier,
        store: SessionStore,
        broadcaster: SSEBroadcaster | None,
        cfg: TurnConfig | None = None,
    ) -> None:
        self._pool = pool
        self._gate = gate
        self._classifier = classifier
        self._store = store
        self._broadcaster = broadcaster
        base = cfg or TurnConfig()
        timeout = base.query_timeout_s if base.query_timeout_s > 0 else 30 * 60
        self._cfg = TurnConfig(
            query_timeout_s=timeout,
            idle_timeout_s=base.idle_timeout_s,
            min_idle_timeout_with_attachments_s=base.min_idle_timeout_with_attachments_s,
            on_idle_timeout=base.on_idle_timeout,
            on_query_timeout=base.on_query_timeout,
            on_stream_close=base.on_stream_close,
            compact_attachments_before_send=base.compact_attachments_before_send,
            compact_image_opts=base.compact_image_opts,
        )
        self._build_input: InputBuilder = input_message_for_loop
        self._on_complete: OnComplete | None = None
        self._on_error: OnError | None = None

    def with_input_builder(self, builder: InputBuilder) -> TurnRunner:
        """Override the loop_input payload builder."""
        self._build_input = builder
        return self

    def with_on_complete(self, hook: OnComplete) -> TurnRunner:
        """Set a completion hook (runs inline on success)."""
        self._on_complete = hook
        return self

    def with_on_error(self, hook: OnError) -> TurnRunner:
        """Set an error hook (runs inline on failure)."""
        self._on_error = hook
        return self

    async def execute(
        self,
        session_id: str,
        message: str,
        user_id: str,
        workspace_id: str,
        attachments: list[Attachment] | None = None,
        opts: InputOpts | None = None,
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> None:
        """Run one query turn; persist and broadcast the result (no return value)."""
        try:
            conn = await self._pool.acquire(session_id, workspace_id, user_id)
        except Exception as err:
            await self._persist_failed(session_id, "", err)
            self._broadcast_error(session_id, err)
            if self._on_error is not None:
                self._on_error(session_id, "", err)
            raise

        loop_id = conn.get_loop_id()
        query_timed_out = asyncio.Event()
        query_timer = asyncio.create_task(
            self._arm_sleep(query_timed_out, self._cfg.query_timeout_s)
        )

        async def send_cancel() -> None:
            await self._send_loop_cancel(conn, loop_id)

        def local_cancel() -> None:
            query_timed_out.set()

        try:
            await self._gate.acquire(session_id, local_cancel, send_cancel)
        except Exception as err:
            query_timer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await query_timer
            await self._pool.release(session_id)
            await self._persist_failed(session_id, loop_id, err)
            self._broadcast_error(session_id, err)
            if self._on_error is not None:
                self._on_error(session_id, loop_id, err)
            raise

        idle_for_turn = idle_timeout_for_turn(self._cfg, bool(attachments))
        idle_fired = asyncio.Event()
        idle_task: asyncio.Task[None] | None = None

        def arm_idle() -> None:
            nonlocal idle_task
            if idle_for_turn <= 0:
                return
            if idle_task is not None:
                idle_task.cancel()
            idle_fired.clear()
            idle_task = asyncio.create_task(self._arm_sleep(idle_fired, idle_for_turn))

        try:
            atts = attachments
            if self._cfg.compact_attachments_before_send and atts:
                atts = compact_attachments(atts, self._cfg.compact_image_opts)

            input_msg = self._build_input(message, loop_id, atts, opts)
            try:
                await conn.client.send_message(input_msg)
            except Exception as err:
                await self._persist_failed(session_id, loop_id, err)
                self._broadcast_error(session_id, err)
                if self._on_error is not None:
                    self._on_error(session_id, loop_id, err)
                raise

            event_stream = conn.event_stream
            if event_stream is None:
                err = RuntimeError(
                    f"missing event stream for session {session_id} (loop {loop_id})"
                )
                await self._persist_failed(session_id, loop_id, err)
                self._broadcast_error(session_id, err)
                if self._on_error is not None:
                    self._on_error(session_id, loop_id, err)
                raise err

            assistant_content = ""
            started_at = time.time()
            agen = event_stream.__aiter__()
            arm_idle()

            while True:
                if cancel_event is not None and cancel_event.is_set():
                    err = RuntimeError("aborted")
                    await self._fail_turn(session_id, loop_id, err)
                    raise err

                if query_timed_out.is_set():
                    with contextlib.suppress(Exception):
                        await self._send_loop_cancel(conn, loop_id)
                    await self._finish_timeout(
                        session_id,
                        loop_id,
                        assistant_content,
                        started_at,
                        ErrQueryTimeout(),
                        "query_timeout",
                        self._cfg.on_query_timeout,
                    )
                    return

                if idle_fired.is_set():
                    with contextlib.suppress(Exception):
                        await self._send_loop_cancel(conn, loop_id)
                    await self._finish_timeout(
                        session_id,
                        loop_id,
                        assistant_content,
                        started_at,
                        ErrIdleTimeout(),
                        "idle_timeout",
                        self._cfg.on_idle_timeout,
                    )
                    return

                next_task = asyncio.create_task(agen.__anext__())
                waiters: list[asyncio.Task[Any]] = [
                    next_task,
                    asyncio.create_task(query_timed_out.wait()),
                ]
                idle_wait: asyncio.Task[Any] | None = None
                if idle_for_turn > 0:
                    idle_wait = asyncio.create_task(idle_fired.wait())
                    waiters.append(idle_wait)
                caller_wait: asyncio.Task[Any] | None = None
                if cancel_event is not None:
                    caller_wait = asyncio.create_task(cancel_event.wait())
                    waiters.append(caller_wait)

                done, pending = await asyncio.wait(
                    waiters,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

                if waiters[1] in done and query_timed_out.is_set():
                    with contextlib.suppress(Exception):
                        await self._send_loop_cancel(conn, loop_id)
                    await self._finish_timeout(
                        session_id,
                        loop_id,
                        assistant_content,
                        started_at,
                        ErrQueryTimeout(),
                        "query_timeout",
                        self._cfg.on_query_timeout,
                    )
                    return

                if idle_wait is not None and idle_wait in done and idle_fired.is_set():
                    with contextlib.suppress(Exception):
                        await self._send_loop_cancel(conn, loop_id)
                    await self._finish_timeout(
                        session_id,
                        loop_id,
                        assistant_content,
                        started_at,
                        ErrIdleTimeout(),
                        "idle_timeout",
                        self._cfg.on_idle_timeout,
                    )
                    return

                if caller_wait is not None and caller_wait in done:
                    err = RuntimeError("aborted")
                    await self._fail_turn(session_id, loop_id, err)
                    raise err

                try:
                    msg = next_task.result()
                except StopAsyncIteration:
                    if (
                        self._cfg.on_stream_close == TimeoutPolicy.SOFT_COMPLETE
                        and assistant_content.strip()
                    ):
                        await self._complete_turn(
                            session_id,
                            loop_id,
                            assistant_content.strip(),
                            started_at,
                            "stream_closed",
                        )
                        return
                    err = RuntimeError("event stream closed")
                    await self._fail_turn(session_id, loop_id, err)
                    raise err from None

                arm_idle()

                event_result = self._classifier.classify(msg, assistant_content)
                if (
                    event_result.err is not None
                    and event_result.terminal == ChatEventTerminal.FAILED_COMPLETE
                ):
                    await self._fail_turn(session_id, loop_id, event_result.err)
                    raise event_result.err

                step = (event_result.thinking_step or "").strip()
                if step:
                    self._broadcast_thinking_step(session_id, step)

                if event_result.content:
                    if event_result.content.startswith(assistant_content):
                        delta = event_result.content[len(assistant_content) :]
                        assistant_content = event_result.content
                    else:
                        delta = event_result.content
                        assistant_content += event_result.content
                    if delta:
                        self._broadcast_delta(session_id, delta)

                final, deliverable = self._classifier.resolve_deliverable_final_content(
                    event_result,
                    assistant_content,
                )
                if deliverable:
                    await self._complete_turn(
                        session_id,
                        loop_id,
                        final,
                        started_at,
                        event_result.completion_event or "",
                    )
                    return
        finally:
            query_timer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await query_timer
            if idle_task is not None:
                idle_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await idle_task
            await self._gate.release(session_id)

    async def _arm_sleep(self, flag: asyncio.Event, seconds: float) -> None:
        try:
            await asyncio.sleep(seconds)
            flag.set()
        except asyncio.CancelledError:
            return

    async def _finish_timeout(
        self,
        session_id: str,
        loop_id: str,
        content: str,
        started_at: float,
        fail_err: BaseException,
        completion_event: str,
        policy: TimeoutPolicy,
    ) -> None:
        if policy == TimeoutPolicy.SOFT_COMPLETE and content.strip():
            await self._complete_turn(
                session_id,
                loop_id,
                content.strip(),
                started_at,
                completion_event,
            )
            return
        await self._fail_turn(session_id, loop_id, fail_err)
        raise fail_err

    async def _complete_turn(
        self,
        session_id: str,
        loop_id: str,
        final: str,
        started_at: float,
        completion_event: str,
    ) -> None:
        elapsed_ms = (time.time() - started_at) * 1000.0
        await self._persist_response(session_id, loop_id, final, started_at, completion_event)
        self._broadcast_complete(session_id, final)
        if self._on_complete is not None:
            self._on_complete(session_id, loop_id, final, completion_event, elapsed_ms)

    async def _fail_turn(
        self,
        session_id: str,
        loop_id: str,
        err: BaseException,
    ) -> None:
        await self._persist_failed(session_id, loop_id, err)
        self._broadcast_error(session_id, err)
        if self._on_error is not None:
            self._on_error(session_id, loop_id, err)

    async def _send_loop_cancel(self, conn: PooledConn, loop_id: str) -> None:
        lid = (loop_id or "").strip()
        if not lid:
            return
        cancel_msg = {"type": "command_request", "command": "cancel", "loop_id": lid}
        await conn.client.send_message(cancel_msg)

    async def _persist_response(
        self,
        session_id: str,
        loop_id: str,
        content: str,
        started_at: float,
        completion_event: str,
    ) -> None:
        now = time.time()
        msg = SessionMessage(
            role="assistant",
            content=content,
            metadata={
                "started_at": started_at,
                "completed_at": now,
                "duration_ms": (now - started_at) * 1000.0,
                "status": "completed",
                "completion_event": completion_event,
                "deliverable": True,
                "loop_id": loop_id,
            },
        )
        with contextlib.suppress(Exception):
            await self._store.append_message(session_id, msg)

    async def _persist_failed(
        self,
        session_id: str,
        _loop_id: str,
        err: BaseException,
    ) -> None:
        msg = SessionMessage(
            role="error",
            content=str(err),
            metadata={"status": "failed", "error_message": str(err)},
        )
        with contextlib.suppress(Exception):
            await self._store.append_message(session_id, msg)

    def _broadcast_thinking_step(self, session_id: str, step: str) -> None:
        if self._broadcaster is None:
            return
        self._broadcaster.broadcast(
            session_id,
            SSEEvent(type="thinking_step", data=f"{step}\n"),
        )

    def _broadcast_delta(self, session_id: str, delta: str) -> None:
        if self._broadcaster is None or not delta:
            return
        self._broadcaster.broadcast(session_id, SSEEvent(type="delta", data=delta))

    def _broadcast_complete(self, session_id: str, content: str) -> None:
        if self._broadcaster is None:
            return
        self._broadcaster.broadcast(session_id, SSEEvent(type="complete", data=content))

    def _broadcast_error(self, session_id: str, err: BaseException) -> None:
        if self._broadcaster is None:
            return
        self._broadcaster.broadcast(
            session_id,
            SSEEvent(type="query_error", data=str(err)),
        )


__all__ = [
    "STREAM_CLOSE_FAIL",
    "STREAM_CLOSE_SOFT_COMPLETE",
    "Attachment",
    "ErrIdleTimeout",
    "ErrQueryTimeout",
    "InputOpts",
    "OnComplete",
    "OnError",
    "StreamClosePolicy",
    "TimeoutPolicy",
    "TurnConfig",
    "TurnRunner",
    "idle_timeout_for_turn",
    "input_message_for_loop",
]
