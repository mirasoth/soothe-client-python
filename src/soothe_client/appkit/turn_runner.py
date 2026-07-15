"""Turn runner for appkit (RFC-629 Layer 1).

Executes one query turn end-to-end: acquire a pooled connection, enforce
single-flight, send loop_input, consume the event stream, classify events,
resolve the deliverable, persist the reply, and broadcast completion.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
    """Raised when a turn exceeds the configured timeout."""

    def __init__(self) -> None:
        super().__init__("appkit: query timeout")


@dataclass(slots=True)
class TurnConfig:
    """Configures a ``TurnRunner``."""

    query_timeout_s: float = 30 * 60


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
        timeout = (cfg.query_timeout_s if cfg is not None else 0) or (30 * 60)
        self._cfg = TurnConfig(query_timeout_s=timeout if timeout > 0 else 30 * 60)
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
        timed_out = asyncio.Event()
        timer = asyncio.create_task(self._arm_timeout(timed_out))

        async def send_cancel() -> None:
            await self._send_loop_cancel(conn, loop_id)

        def local_cancel() -> None:
            timed_out.set()

        try:
            await self._gate.acquire(session_id, local_cancel, send_cancel)
        except Exception as err:
            timer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await timer
            await self._pool.release(session_id)
            await self._persist_failed(session_id, loop_id, err)
            self._broadcast_error(session_id, err)
            if self._on_error is not None:
                self._on_error(session_id, loop_id, err)
            raise

        try:
            input_msg = self._build_input(message, loop_id, attachments, opts)
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

            while True:
                if cancel_event is not None and cancel_event.is_set():
                    err = RuntimeError("aborted")
                    await self._persist_failed(session_id, loop_id, err)
                    self._broadcast_error(session_id, err)
                    if self._on_error is not None:
                        self._on_error(session_id, loop_id, err)
                    raise err

                if timed_out.is_set():
                    with contextlib.suppress(Exception):
                        await self._send_loop_cancel(conn, loop_id)
                    timeout_err = ErrQueryTimeout()
                    await self._persist_failed(session_id, loop_id, timeout_err)
                    self._broadcast_error(session_id, timeout_err)
                    if self._on_error is not None:
                        self._on_error(session_id, loop_id, timeout_err)
                    raise timeout_err

                next_task = asyncio.create_task(agen.__anext__())
                timeout_wait = asyncio.create_task(timed_out.wait())
                waiters: list[asyncio.Task[Any]] = [next_task, timeout_wait]
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

                if timeout_wait in done and timed_out.is_set():
                    with contextlib.suppress(Exception):
                        await self._send_loop_cancel(conn, loop_id)
                    timeout_err = ErrQueryTimeout()
                    await self._persist_failed(session_id, loop_id, timeout_err)
                    self._broadcast_error(session_id, timeout_err)
                    if self._on_error is not None:
                        self._on_error(session_id, loop_id, timeout_err)
                    raise timeout_err

                if caller_wait is not None and caller_wait in done:
                    err = RuntimeError("aborted")
                    await self._persist_failed(session_id, loop_id, err)
                    self._broadcast_error(session_id, err)
                    if self._on_error is not None:
                        self._on_error(session_id, loop_id, err)
                    raise err

                try:
                    msg = next_task.result()
                except StopAsyncIteration:
                    err = RuntimeError("event stream closed")
                    await self._persist_failed(session_id, loop_id, err)
                    self._broadcast_error(session_id, err)
                    if self._on_error is not None:
                        self._on_error(session_id, loop_id, err)
                    raise err from None

                event_result = self._classifier.classify(msg, assistant_content)
                if (
                    event_result.err is not None
                    and event_result.terminal == ChatEventTerminal.FAILED_COMPLETE
                ):
                    await self._persist_failed(session_id, loop_id, event_result.err)
                    self._broadcast_error(session_id, event_result.err)
                    if self._on_error is not None:
                        self._on_error(session_id, loop_id, event_result.err)
                    raise event_result.err

                step = (event_result.thinking_step or "").strip()
                if step:
                    self._broadcast_thinking_step(session_id, step)

                if event_result.content:
                    if event_result.content.startswith(assistant_content):
                        assistant_content = event_result.content
                    else:
                        assistant_content += event_result.content

                final, deliverable = self._classifier.resolve_deliverable_final_content(
                    event_result,
                    assistant_content,
                )
                if deliverable:
                    elapsed_ms = (time.time() - started_at) * 1000.0
                    await self._persist_response(
                        session_id,
                        loop_id,
                        final,
                        started_at,
                        event_result.completion_event or "",
                    )
                    self._broadcast_complete(session_id, final)
                    if self._on_complete is not None:
                        self._on_complete(
                            session_id,
                            loop_id,
                            final,
                            event_result.completion_event or "",
                            elapsed_ms,
                        )
                    return
        finally:
            timer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await timer
            await self._gate.release(session_id)

    async def _arm_timeout(self, timed_out: asyncio.Event) -> None:
        try:
            await asyncio.sleep(self._cfg.query_timeout_s)
            timed_out.set()
        except asyncio.CancelledError:
            return

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
    "Attachment",
    "ErrQueryTimeout",
    "InputOpts",
    "OnComplete",
    "OnError",
    "TurnConfig",
    "TurnRunner",
    "input_message_for_loop",
]
