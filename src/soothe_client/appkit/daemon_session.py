"""Dual-socket daemon loop session with turn streaming.

Owns a subscribed stream WebSocket plus an RPC sidecar so metadata calls do not
starve loop events. ``iter_turn_chunks`` handles idle timeout, post-idle drain,
loop scoping, and connection-loss detection.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable
from types import SimpleNamespace
from typing import Any

from soothe_client.appkit.chunk_filter import should_drop_stream_chunk_early
from soothe_client.appkit.events import unwrap_next
from soothe_client.appkit.observability import TurnEventStats
from soothe_client.session import bootstrap_loop_session, connect_websocket_with_retries
from soothe_client.stream_terminal import (
    STREAM_END,
    is_turn_end_custom_data,
    is_turn_progress_chunk,
)
from soothe_client.turn_boundary import frame_seq, frame_turn_id
from soothe_client.websocket import WebSocketClient

logger = logging.getLogger(__name__)

DEFAULT_POST_IDLE_DRAIN_S = 0.5
_RPC_HANDSHAKE_TIMEOUT_S = 20.0

EarlyDropFn = Callable[[tuple[Any, ...], str, Any], bool]
StatsFactory = Callable[[], Any]
StreamDeliveryResolver = Callable[[], str]


class DaemonSession:
    """Daemon-backed loop session with stream + RPC sockets."""

    def __init__(
        self,
        ws_url: str,
        *,
        workspace: str | None = None,
        stream_delivery: str | StreamDeliveryResolver = "adaptive",
        post_idle_drain_deadline: float = DEFAULT_POST_IDLE_DRAIN_S,
        early_drop_fn: EarlyDropFn | None = None,
        stats_factory: StatsFactory | None = None,
    ) -> None:
        self._ws_url = ws_url
        self._workspace = workspace
        self._stream_delivery = stream_delivery
        self._client = WebSocketClient(url=ws_url)
        self._rpc_client = WebSocketClient(url=ws_url)
        self._loop_id: str | None = None
        self._read_lock = asyncio.Lock()
        self._rpc_lock = asyncio.Lock()
        self._rpc_connected = False
        self._streaming = False
        self._post_idle_drain_deadline = post_idle_drain_deadline
        self._closed = False
        self._early_drop_fn = early_drop_fn or should_drop_stream_chunk_early
        self._stats_factory = stats_factory or TurnEventStats
        self.turn_event_stats = self._stats_factory()
        self.last_turn_end_state: str | None = None
        self.last_turn_cancellation_seen: bool = False
        self.last_turn_error_message: str | None = None
        # IG-659: last completed turn's seq floor (drop stale prior-turn frames).
        self._last_turn_end_seq: int = 0
        self._expected_turn_id: str | None = None

    @property
    def client(self) -> WebSocketClient:
        """Subscribed stream WebSocket (loop events)."""
        return self._client

    @property
    def rpc_client(self) -> WebSocketClient:
        """RPC sidecar WebSocket (metadata calls)."""
        return self._rpc_client

    @property
    def loop_id(self) -> str | None:
        """Active StrangeLoop id for this WebSocket session."""
        return self._loop_id

    def _resolve_stream_delivery_mode(self) -> str:
        delivery = getattr(self, "_stream_delivery", "adaptive")
        if callable(delivery):
            return str(delivery() or "adaptive")
        return str(delivery or "adaptive")

    def _should_drop(self, namespace: tuple[Any, ...], mode: str, data: Any) -> bool:
        drop_fn = getattr(self, "_early_drop_fn", None) or should_drop_stream_chunk_early
        return bool(drop_fn(namespace, mode, data))

    def _new_turn_stats(self) -> Any:
        factory = getattr(self, "_stats_factory", None) or TurnEventStats
        return factory()

    @property
    def _drain_deadline(self) -> float:
        return float(
            getattr(self, "_post_idle_drain_deadline", DEFAULT_POST_IDLE_DRAIN_S)
            or DEFAULT_POST_IDLE_DRAIN_S
        )

    async def connect(self, *, resume_loop_id: str | None = None) -> dict[str, Any]:
        """Connect and bootstrap a daemon loop session."""
        await connect_websocket_with_retries(self._client)
        return await self._bootstrap_loop(resume_loop_id=resume_loop_id)

    async def _bootstrap_loop(self, *, resume_loop_id: str | None = None) -> dict[str, Any]:
        status_event = await bootstrap_loop_session(
            self._client,
            resume_loop_id=resume_loop_id,
            stream_delivery=self._resolve_stream_delivery_mode(),
            workspace=getattr(self, "_workspace", None),
        )
        if status_event.get("type") == "error":
            raise RuntimeError(str(status_event.get("message", "daemon bootstrap failed")))
        self._loop_id = status_event.get("loop_id")
        return status_event

    async def new_loop(self) -> dict[str, Any]:
        """Start a new StrangeLoop conversation."""
        return await self._bootstrap_loop(resume_loop_id=None)

    async def switch_loop(self, loop_id: str) -> dict[str, Any]:
        """Subscribe to an existing loop (re-bootstrap on the same connection)."""
        return await self._bootstrap_loop(resume_loop_id=loop_id)

    async def ensure_connected(self) -> None:
        """Reconnect and re-subscribe when the stream WebSocket died.

        Prefers ``reconnect`` + ``reattach_and_probe`` when a loop id is known;
        falls back to bootstrap on ``StaleLoopError``.
        """
        from soothe_client.errors import StaleLoopError

        is_disconn = getattr(self._client, "is_disconnected", None)
        disconnected = bool(is_disconn()) if callable(is_disconn) else False
        if self._client.is_connection_alive() and not disconnected:
            return

        resume_loop_id = self._loop_id
        logger.info(
            "Daemon WebSocket closed; reconnecting%s",
            f" to loop {resume_loop_id[:8]}..." if resume_loop_id else "",
        )
        if self._rpc_connected:
            await self._rpc_client.close()
            self._rpc_connected = False

        reconnect = getattr(self._client, "reconnect", None)
        if callable(reconnect):
            await reconnect()
        else:
            await self._client.close()
            await connect_websocket_with_retries(self._client)

        if resume_loop_id:
            reattach = getattr(self._client, "reattach_and_probe", None)
            if callable(reattach):
                try:
                    await reattach(
                        resume_loop_id,
                        stream_delivery=self._resolve_stream_delivery_mode(),
                    )
                    self._loop_id = resume_loop_id
                    return
                except StaleLoopError:
                    logger.warning(
                        "Loop %s stale after reattach; bootstrapping fresh session",
                        resume_loop_id[:16],
                        exc_info=True,
                    )
                    resume_loop_id = None

        await self._bootstrap_loop(resume_loop_id=resume_loop_id)

    async def close(self, *, handshake_timeout: float = 2.0) -> None:
        """Close stream and RPC sockets (idempotent)."""
        if self._closed:
            return
        self._closed = True
        await asyncio.gather(
            self._client.close(handshake_timeout=handshake_timeout),
            self._rpc_client.close(handshake_timeout=handshake_timeout),
            return_exceptions=True,
        )
        self._rpc_connected = False

    async def detach(self) -> None:
        """Notify the daemon that this client is leaving (``disconnect``)."""
        if not self._client.is_connected:
            logger.debug("Skipping detach — connection already closed")
            return
        try:
            await self._client.notify("disconnect", {})
        except ConnectionError:
            logger.debug("Daemon connection closed before detach")

    async def send_turn(
        self,
        text: str,
        *,
        autonomous: bool = False,
        max_iterations: int | None = None,
        preferred_subagent: str | None = None,
        model: str | None = None,
        model_params: dict[str, Any] | None = None,
        router_profile: str | None = None,
        attachments: list[dict[str, str]] | None = None,
        clarification_mode: str | None = None,
        clarification_answer: bool = False,
        clarification_answers: list[str] | None = None,
        intent_hint: str | None = None,
    ) -> None:
        """Send a new user turn to the daemon."""
        if not self._loop_id:
            raise RuntimeError("No active loop session")
        await self._client.send_input(
            self._loop_id,
            text,
            autonomous=autonomous,
            max_iterations=max_iterations,
            preferred_subagent=preferred_subagent,
            model=model,
            model_params=model_params,
            router_profile=router_profile,
            attachments=attachments,
            clarification_mode=clarification_mode,
            clarification_answer=clarification_answer,
            clarification_answers=clarification_answers,
            intent_hint=intent_hint,
        )

    async def cancel_remote_query(self) -> None:
        """Ask the daemon to cancel via slash ``/cancel`` (CLI wire path)."""
        await self._client.notify("slash_command", {"cmd": "/cancel"})

    async def cancel_active_turn(self) -> None:
        """Cancel the in-flight query on the active loop."""
        await self.cancel_remote_query()

    async def _drain_stream_events_after_idle(
        self,
        *,
        expected_loop_id: str | None,
    ) -> AsyncIterator[tuple[tuple[Any, ...], str, Any]]:
        """Yield stream chunks that arrive just after ``idle``."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._drain_deadline
        exp = expected_loop_id
        while loop.time() < deadline:
            try:
                event = await asyncio.wait_for(self._client.read_event(), timeout=0.25)
            except TimeoutError:
                break
            if not event:
                break
            event_type = event.get("type", "")
            if event_type == "next":
                event = unwrap_next(event) or event
                event_type = event.get("type", "")
            event_loop_id = event.get("loop_id")
            if exp and isinstance(event_loop_id, str) and event_loop_id and event_loop_id != exp:
                continue
            if event_type == "error":
                err_obj = event.get("error") or {}
                err_msg = str(err_obj.get("message") or event.get("message") or "daemon error")
                raise RuntimeError(err_msg)
            if event_type == "status":
                loop_ev = event.get("loop_id")
                if isinstance(loop_ev, str) and loop_ev:
                    self._loop_id = loop_ev
                    exp = loop_ev
                continue
            if event_type != "event":
                continue
            data = event.get("data")
            namespace = tuple(event.get("namespace", []) or [])
            mode = str(event.get("mode", ""))
            if self._should_drop(namespace, mode, data):
                self.turn_event_stats.filtered_early += 1
                continue
            self.turn_event_stats.post_idle_drained += 1
            yield (namespace, mode, data)
            if mode == "updates" and isinstance(data, dict) and "__interrupt__" in data:
                continue

    async def list_loops(self, *, limit: int = 20) -> dict[str, Any]:
        """Return ``loop_list`` via the RPC sidecar."""
        async with self._rpc_lock:
            await self._ensure_rpc_connected()
            return await self._rpc_client.request("loop_list", {"limit": limit}, timeout=15.0)

    async def iter_turn_chunks(
        self,
        *,
        max_wait_s: float | None = None,
    ) -> AsyncIterator[tuple[tuple[Any, ...], str, Any]]:
        """Yield ``(namespace, mode, data)`` chunks for the active daemon turn.

        Args:
            max_wait_s: Optional absolute deadline for the whole turn. When set,
                raises ``TimeoutError`` if the daemon never emits a turn-end
                signal in time (idle after payload, stopped, stream.end, or
                strange_loop.completed).
        """
        self.turn_event_stats = self._new_turn_stats()
        self.last_turn_end_state = None
        self.last_turn_cancellation_seen = False
        self.last_turn_error_message = None
        inbound_dropped_baseline = getattr(self._client, "inbound_dropped", 0)
        query_started = False
        expected_loop_id = self._loop_id
        # Bind turn_id only after this turn's status=running (do not reuse prior).
        self._expected_turn_id = None
        expected_turn_id: str | None = None
        stream_payload_seen = False
        turn_progress_seen = False
        last_end_seq = int(getattr(self, "_last_turn_end_seq", 0) or 0)
        self._last_turn_end_seq = last_end_seq
        self._streaming = True
        turn_read_started = time.monotonic()
        first_event_logged = False
        progress_seen = False
        absolute_deadline = (
            time.monotonic() + max_wait_s if max_wait_s is not None and max_wait_s > 0 else None
        )
        peel = getattr(self._client, "peel_stale_pending_control_events", None)
        stale_pending = peel() if callable(peel) else []
        if stale_pending:
            logger.debug(
                "Peeled %d stale pending control frame(s) before turn (loop=%s): %s",
                len(stale_pending),
                (expected_loop_id or "?")[:16],
                ", ".join(stale_pending[:8]),
            )
        async with self._read_lock:
            try:
                while True:
                    if absolute_deadline is not None and time.monotonic() >= absolute_deadline:
                        raise TimeoutError(
                            f"Turn timed out after {max_wait_s:.0f}s "
                            f"(loop={expected_loop_id or '?'})"
                        )
                    if not progress_seen and time.monotonic() - turn_read_started > 30.0:
                        logger.warning(
                            "No daemon stream progress after %.0fs (loop=%s, "
                            "query_started=%s); check daemon sender / WebSocket reader",
                            time.monotonic() - turn_read_started,
                            (expected_loop_id or "?")[:16],
                            query_started,
                        )
                        turn_read_started = time.monotonic()
                    event = await self._client.read_event()
                    if event and not first_event_logged:
                        first_event_logged = True
                        logger.debug(
                            "First daemon event on turn: type=%s loop_id=%s turn_id=%s",
                            event.get("type"),
                            event.get("loop_id"),
                            frame_turn_id(event),
                        )
                    if not event:
                        if query_started and not self._client.is_connection_alive():
                            self.last_turn_end_state = "connection_lost"
                            raise ConnectionError("Daemon connection lost")
                        break

                    event_type = event.get("type", "")
                    if event_type == "next":
                        event = unwrap_next(event) or event
                        event_type = event.get("type", "")

                    event_loop_id = event.get("loop_id")
                    if (
                        expected_loop_id
                        and isinstance(event_loop_id, str)
                        and event_loop_id
                        and event_loop_id != expected_loop_id
                    ):
                        continue

                    # IG-659 phase 5: drop frames at or before prior turn end seq.
                    ev_seq = frame_seq(event)
                    if ev_seq is not None and last_end_seq > 0 and ev_seq <= last_end_seq:
                        continue

                    # IG-659 phases 1–2: drop mismatched turn_id once bound.
                    ev_turn_id = frame_turn_id(event)
                    if (
                        expected_turn_id
                        and ev_turn_id
                        and ev_turn_id != expected_turn_id
                        and event_type in {"event", "status"}
                    ):
                        logger.debug(
                            "Ignoring mismatched turn_id frame type=%s got=%s expected=%s",
                            event_type,
                            ev_turn_id[-24:],
                            expected_turn_id[-24:],
                        )
                        continue

                    if event_type == "error":
                        err_obj = event.get("error") or {}
                        err_msg = str(
                            err_obj.get("message") or event.get("message") or "daemon error"
                        )
                        raise RuntimeError(err_msg)

                    if event_type == "status":
                        loop_ev = event.get("loop_id")
                        if isinstance(loop_ev, str) and loop_ev:
                            self._loop_id = loop_ev
                            expected_loop_id = loop_ev
                        state = event.get("state", "")
                        if state == "running":
                            query_started = True
                            progress_seen = True
                            status_turn = frame_turn_id(event)
                            if status_turn:
                                expected_turn_id = status_turn
                                self._expected_turn_id = status_turn
                        elif query_started and state == "stopped":
                            self.last_turn_end_state = state
                            if ev_seq is not None:
                                self._last_turn_end_seq = max(self._last_turn_end_seq, ev_seq)
                            async for chunk in self._drain_stream_events_after_idle(
                                expected_loop_id=expected_loop_id,
                            ):
                                yield chunk
                            break
                        elif query_started and state == "idle":
                            if not stream_payload_seen and not self.last_turn_cancellation_seen:
                                continue
                            self.last_turn_end_state = state
                            if ev_seq is not None:
                                self._last_turn_end_seq = max(self._last_turn_end_seq, ev_seq)
                            async for chunk in self._drain_stream_events_after_idle(
                                expected_loop_id=expected_loop_id,
                            ):
                                yield chunk
                            break
                        continue

                    if event_type == "command_response":
                        content = str(event.get("content", ""))
                        if "Cancellation requested" in content:
                            self.last_turn_cancellation_seen = True
                        continue

                    if event_type != "event":
                        continue

                    data = event.get("data")
                    namespace = tuple(event.get("namespace", []) or [])
                    mode = str(event.get("mode", ""))
                    if self._should_drop(namespace, mode, data):
                        self.turn_event_stats.filtered_early += 1
                        continue

                    # Prefer turn_id match when present; else IG-658 progress gate.
                    if mode == "custom" and is_turn_end_custom_data(data):
                        data_turn = (
                            frame_turn_id(data if isinstance(data, dict) else None) or ev_turn_id
                        )
                        turn_ok = (
                            not expected_turn_id or not data_turn or data_turn == expected_turn_id
                        )
                        if not turn_ok or not query_started or not turn_progress_seen:
                            logger.debug(
                                "Ignoring premature turn-end frame %s "
                                "(loop=%s query_started=%s progress=%s turn_ok=%s)",
                                str(data.get("type", "")).strip()
                                if isinstance(data, dict)
                                else "?",
                                (expected_loop_id or "?")[:16],
                                query_started,
                                turn_progress_seen,
                                turn_ok,
                            )
                            continue

                    progress_seen = True
                    stream_payload_seen = True
                    if is_turn_progress_chunk(mode, data):
                        turn_progress_seen = True
                    yield (namespace, mode, data)
                    if mode == "custom" and is_turn_end_custom_data(data):
                        custom_type = str(data.get("type", "")).strip()
                        self.last_turn_end_state = (
                            "stream_end" if custom_type == STREAM_END else "completed"
                        )
                        if ev_seq is not None:
                            self._last_turn_end_seq = max(self._last_turn_end_seq, ev_seq)
                        async for chunk in self._drain_stream_events_after_idle(
                            expected_loop_id=expected_loop_id,
                        ):
                            yield chunk
                        break
                    if mode == "updates" and isinstance(data, dict) and "__interrupt__" in data:
                        continue
            except Exception as exc:
                self.last_turn_error_message = str(exc)
                raise
            finally:
                self._streaming = False
                self.turn_event_stats.inbound_dropped = max(
                    0,
                    getattr(self._client, "inbound_dropped", 0) - inbound_dropped_baseline,
                )

    async def list_skills(self) -> list[dict[str, Any]]:
        """Return skill rows from the daemon catalog."""
        async with self._rpc_lock:
            await self._ensure_rpc_connected()
            response = await self._rpc_client.list_skills(timeout=15.0)
        skills = response.get("skills", [])
        if not isinstance(skills, list):
            return []
        return [s for s in skills if isinstance(s, dict)]

    async def list_models(self) -> dict[str, Any]:
        """Return daemon ``models_list`` result."""
        async with self._rpc_lock:
            await self._ensure_rpc_connected()
            return await self._rpc_client.list_models(timeout=15.0)

    async def get_mcp_status(self) -> dict[str, Any]:
        """Return daemon ``mcp_status`` result."""
        async with self._rpc_lock:
            await self._ensure_rpc_connected()
            return await self._rpc_client.get_mcp_status(timeout=15.0)

    async def invoke_skill(
        self,
        skill: str,
        args: str = "",
        *,
        clarification_mode: str | None = None,
    ) -> dict[str, Any]:
        """Invoke a skill on the **stream** socket (required for turn enqueue)."""
        async with self._read_lock:
            return await self._client.invoke_skill(
                skill,
                args,
                timeout=120.0,
                clarification_mode=clarification_mode,
            )

    async def _ensure_rpc_connected(self) -> None:
        if self._rpc_connected:
            return
        await connect_websocket_with_retries(self._rpc_client)
        await self._rpc_client.request_connection_init()
        await self._rpc_client.wait_for_connection_ack(ack_timeout_s=_RPC_HANDSHAKE_TIMEOUT_S)
        self._rpc_connected = True

    async def fetch_loop_cards(self, loop_id: str) -> SimpleNamespace:
        """Fetch bound display-card snapshot for a loop."""
        lid = str(loop_id or "").strip()
        if not lid:
            return SimpleNamespace(cards=[], seq=0, success=False)

        async with self._rpc_lock:
            await self._ensure_rpc_connected()
            try:
                resp = await self._rpc_client.request(
                    "loop_cards_fetch",
                    {"loop_id": lid},
                    timeout=30.0,
                )
            except Exception:
                logger.warning("loop_cards_fetch failed for loop %s", lid[:16], exc_info=True)
                return SimpleNamespace(cards=[], seq=0, success=False)

        raw_cards = resp.get("cards")
        cards = list(raw_cards) if isinstance(raw_cards, list) else []
        seq = int(resp.get("seq") or 0)
        context_tokens_raw = resp.get("context_tokens")
        context_tokens = (
            context_tokens_raw
            if isinstance(context_tokens_raw, int) and context_tokens_raw >= 0
            else 0
        )
        return SimpleNamespace(
            cards=cards,
            seq=seq,
            context_tokens=context_tokens,
            success=True,
        )

    async def fetch_loop_history(self, loop_id: str) -> SimpleNamespace:
        """Fetch goal display snapshots plus live card tail."""
        lid = str(loop_id or "").strip()
        if not lid:
            return SimpleNamespace(
                goals=[],
                live_cards=[],
                live_goal_index=None,
                context_tokens=0,
                success=False,
            )

        async with self._rpc_lock:
            await self._ensure_rpc_connected()
            try:
                resp = await self._rpc_client.request(
                    "loop_history_fetch",
                    {"loop_id": lid},
                    timeout=30.0,
                )
            except Exception:
                logger.warning("loop_history_fetch failed for loop %s", lid[:16], exc_info=True)
                return SimpleNamespace(
                    goals=[],
                    live_cards=[],
                    live_goal_index=None,
                    context_tokens=0,
                    success=False,
                )

        goals_raw = resp.get("goals")
        goals = list(goals_raw) if isinstance(goals_raw, list) else []
        live_raw = resp.get("live_cards")
        live_cards = list(live_raw) if isinstance(live_raw, list) else []
        live_goal_index = resp.get("live_goal_index")
        if live_goal_index is not None and not isinstance(live_goal_index, int):
            live_goal_index = None
        context_tokens_raw = resp.get("context_tokens")
        context_tokens = (
            context_tokens_raw
            if isinstance(context_tokens_raw, int) and context_tokens_raw >= 0
            else 0
        )
        success = bool(resp.get("success", True))
        return SimpleNamespace(
            goals=goals,
            live_cards=live_cards,
            live_goal_index=live_goal_index,
            context_tokens=context_tokens,
            success=success,
        )

    async def aget_loop_state(self, loop_id: str) -> Any:
        """Load StrangeLoop state channels from the daemon."""
        lid = str(loop_id or "").strip()
        if not lid:
            return SimpleNamespace(values={})

        async with self._rpc_lock:
            await self._ensure_rpc_connected()
            try:
                resp = await self._rpc_client.request(
                    "loop_state_get",
                    {"loop_id": lid},
                    timeout=30.0,
                )
            except Exception:
                logger.warning("loop_state_get failed for loop %s", lid[:16], exc_info=True)
                return SimpleNamespace(values={})

        raw = resp.get("values")
        values: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
        return SimpleNamespace(values=values)

    async def aupdate_loop_state(
        self,
        loop_id: str,
        values: dict[str, Any],
        *,
        timeout: float = 10.0,
        as_node: str | None = None,
    ) -> None:
        """Merge partial state into the loop on the daemon host."""
        lid = str(loop_id or "").strip()
        if not lid:
            return

        async with self._rpc_lock:
            await self._ensure_rpc_connected()
            from soothe_sdk.wire.protocol import _serialize_for_json

            payload_values = _serialize_for_json(values)
            if not isinstance(payload_values, dict):
                return
            params: dict[str, Any] = {"loop_id": lid, "values": payload_values}
            if as_node:
                params["as_node"] = as_node
            await self._rpc_client.request(
                "loop_state_update",
                params,
                timeout=timeout,
            )

    async def fetch_conversation_log(
        self,
        loop_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
        include_events: bool = False,
    ) -> list[dict[str, Any]]:
        """Load persisted rows for a loop (conversation + optional events)."""
        lid = str(loop_id or "").strip()
        if not lid:
            return []

        async with self._rpc_lock:
            await self._ensure_rpc_connected()
            resp = await self._rpc_client.request(
                "loop_messages",
                {
                    "loop_id": lid,
                    "limit": limit,
                    "offset": offset,
                    "include_events": include_events,
                },
                timeout=10.0,
            )

        raw = resp.get("messages")
        if not isinstance(raw, list):
            return []
        return [m for m in raw if isinstance(m, dict)]

    async def fetch_goal_completion_text(self, loop_id: str) -> str | None:
        """Return the latest persisted ``goal_completion`` body for a loop, if any."""
        rows = await self.fetch_conversation_log(loop_id, limit=200, include_events=False)
        for row in reversed(rows):
            if row.get("phase") != "goal_completion":
                continue
            text = row.get("text") or row.get("content") or ""
            if isinstance(text, str) and text.strip():
                return text.strip()
        return None


__all__ = [
    "DEFAULT_POST_IDLE_DRAIN_S",
    "DaemonSession",
]
