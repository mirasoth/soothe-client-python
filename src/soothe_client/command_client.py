"""Async and sync daemon command clients (jobs, autopilot, cron).

``AsyncCommandClient`` for asyncio; ``CommandClient`` for scripts/CLI.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast
from uuid import uuid4

from soothe_sdk.wire.codec import (
    ConnectionInitEnvelope,
    ConnectionInitParams,
    ErrorEnvelope,
    MessageType,
    WireEnvelope,
    decode_envelope,
    encode_envelope,
)

from soothe_client.helpers import websocket_url_from_config

logger = logging.getLogger(__name__)

_TRANSITIONAL_DAEMON_READY_STATES = frozenset({"starting", "warming"})
_DAEMON_READY_POLL_INTERVAL_S = 0.05

try:
    from soothe_sdk import __version__ as _client_version
except Exception:  # pragma: no cover
    _client_version = "0.0.0"


def _normalize_cron_add_result(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize daemon cron_add payloads to ``{"job": {...}}`` for CLI callers."""
    if "job" in result:
        out = dict(result)
    elif result.get("job_id") or result.get("id"):
        job_id = result.get("job_id") or result.get("id")
        job = dict(result)
        job["id"] = job_id
        job.pop("job_id", None)
        out = {"job": job}
    else:
        return result
    if result.get("duplicate"):
        out["duplicate"] = True
    return out


def _normalize_cron_show_result(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize daemon cron_show payloads to ``{"job": {...}}`` for CLI callers."""
    if "job" in result:
        return result
    job_id = result.get("job_id") or result.get("id")
    if not job_id:
        return {"job": None}
    job = dict(result)
    job["id"] = job_id
    job.pop("job_id", None)
    return {"job": job}


async def _perform_handshake(ws: Any, *, timeout: float) -> None:
    """Complete protocol-1 ``connection_init`` / ``connection_ack``.

    Args:
        ws: Connected WebSocket.
        timeout: Maximum seconds to wait for a ready ``connection_ack``.

    Raises:
        RuntimeError: If the handshake fails or times out.
    """
    init = ConnectionInitEnvelope(
        params=ConnectionInitParams(
            client_version=_client_version,
            client_name="soothe-sdk",
            accept_proto=["1"],
            capabilities=["streaming", "batch", "heartbeat"],
        )
    )

    async with asyncio.timeout(timeout):
        await ws.send(encode_envelope(init))
        while True:
            response_str = await ws.recv()
            response = decode_envelope(response_str)
            if not isinstance(response, dict):
                continue

            msg_type = response.get("type")
            if msg_type == "status":
                continue

            if msg_type == MessageType.ERROR.value:
                err = ErrorEnvelope.from_wire_dict(response)
                raise RuntimeError(
                    f"[{err.code}] {err.message}" + (f" ({err.data})" if err.data else "")
                )

            if msg_type != "connection_ack":
                continue

            result = response.get("result") or {}
            state = result.get("readiness_state")
            if state == "incompatible":
                raise RuntimeError(
                    "Protocol version incompatible: "
                    f"daemon returned {result.get('protocol_version')!r}"
                )
            if state == "ready":
                return
            if state == "error":
                raise RuntimeError(
                    "Daemon startup failed. Check soothed logs, then restart and retry."
                )
            if state == "degraded":
                raise RuntimeError(
                    "Daemon is degraded. Check soothed health, then restart and retry."
                )
            if state == "stopped":
                raise RuntimeError(
                    "Daemon is stopped (not accepting clients). "
                    "Start or restart soothed, then retry."
                )
            if state in _TRANSITIONAL_DAEMON_READY_STATES:
                await asyncio.sleep(_DAEMON_READY_POLL_INTERVAL_S)
                await ws.send(encode_envelope(init))
                continue
            raise RuntimeError(f"Daemon state is {state}")


# Command message types
_AUTOPilot_COMMANDS = {
    "status": "autopilot_status",
    "submit": "autopilot_submit",
    "list_goals": "autopilot_list_goals",
    "get_goal": "autopilot_get_goal",
    "cancel_goal": "autopilot_cancel_goal",
    "cancel_all": "autopilot_cancel_all",
    "wake": "autopilot_wake",
    "dream": "autopilot_dream",
    "resume": "autopilot_resume",
    "list_jobs": "autopilot_list_jobs",
    "get_job": "autopilot_get_job",
}

_CRON_COMMANDS = {
    "add": "cron_add",
    "list": "cron_list",
    "list_jobs": "cron_list",
    "show": "cron_show",
    "cancel": "cron_cancel",
}

_MEMORY_COMMANDS = {
    "stats": "memory_stats",
}


class AsyncCommandClient:
    """Async client for one-shot daemon RPCs (jobs, autopilot, cron).

    Prefer this for asyncio apps. For scripts/CLI without an event loop, use
    ``CommandClient``. For streaming agent turns, use ``DaemonSession`` instead.

    Job lifecycle uses ``job_*`` methods. Autopilot goal helpers use
    ``autopilot_*``. ``job_cancel`` cancels a root job and its descendants;
    ``autopilot_cancel_all`` cancels every open goal in one call.

    Example::

        client = AsyncCommandClient("ws://127.0.0.1:8765")
        created = await client.job_create("Summarize the README")
        await client.job_cancel(created["job_id"])

    Args:
        ws_url: Daemon WebSocket URL (e.g. ``ws://127.0.0.1:8765``).
        timeout: Per-command timeout in seconds.
    """

    def __init__(self, ws_url: str, *, timeout: float = 30.0) -> None:
        self._ws_url = ws_url.rstrip("/")
        self._timeout = timeout

    async def _send_command(
        self, command_type: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a protocol-1 request envelope and wait for the response.

        Builds a ``WireEnvelope`` with ``type='request'``, ``method=command_type``,
        ``params=payload``, and a UUID4 correlation ``id`` (, ). The envelope is serialized with:func:`encode_envelope` and the
        reply is parsed with:func:`decode_envelope`. Responses are matched by
        ``id``; ``response`` envelopes return their ``result`` and ``error``
        envelopes raise:class:`RuntimeError` carrying the daemon's code/message.

        Args:
            command_type: RPC method name (e.g. ``"autopilot_status"``).
            payload: Structured parameters object for the method.

        Returns:
            The ``result`` dict from the matching ``response`` envelope.

        Raises:
            RuntimeError: If the daemon replies with an ``error`` envelope, the
                connection fails, or the command times out.
        """
        import websockets

        req_id = str(uuid4())
        envelope = WireEnvelope(
            type=MessageType.REQUEST.value,
            method=command_type,
            params=payload or {},
            id=req_id,
        )

        try:
            async with websockets.connect(self._ws_url, open_timeout=self._timeout) as ws:
                await _perform_handshake(ws, timeout=self._timeout)

                # Send the protocol-1 request envelope.
                await ws.send(encode_envelope(envelope))

                # Wait for the matching response/error envelope.
                while True:
                    response_str = await asyncio.wait_for(ws.recv(), timeout=self._timeout)
                    response = decode_envelope(response_str)
                    if not isinstance(response, dict):
                        raise RuntimeError(f"Unexpected response: {response_str!r}")

                    msg_type = response.get("type")

                    # Error envelope: raise with the daemon's code/message.
                    if msg_type == MessageType.ERROR.value:
                        err = ErrorEnvelope.from_wire_dict(response)
                        raise RuntimeError(
                            f"[{err.code}] {err.message}" + (f" ({err.data})" if err.data else "")
                        )

                    # Success: return the result payload.
                    if msg_type == MessageType.RESPONSE.value:
                        if response.get("id") != req_id:
                            # Not our response; keep waiting for the match.
                            continue
                        result = response.get("result") or {}
                        if not isinstance(result, dict):
                            raise RuntimeError(f"Unexpected result payload: {result!r}")
                        return cast(dict[str, Any], result)

                    # Other message types (next/complete/etc.) are unexpected
                    # for a blocking request; keep reading.
                    continue

        except TimeoutError:
            raise RuntimeError(f"Command timeout after {self._timeout}s") from None
        except websockets.exceptions.ConnectionClosedError as exc:
            raise RuntimeError(f"WebSocket connection closed: {exc}") from exc
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Command failed: {exc}") from exc

    # --- Autopilot goals -------------------------------------------------

    async def autopilot_status(self) -> dict[str, Any]:
        """Return autopilot scheduler status (running / dreaming / pool)."""
        return await self._send_command("autopilot_status")

    async def autopilot_submit(
        self, description: str, *, priority: int = 50, workspace: str | None = None
    ) -> dict[str, Any]:
        """Submit a new autopilot goal (returns ``goal_id``)."""
        payload: dict[str, Any] = {"description": description, "priority": priority}
        if workspace:
            payload["workspace"] = workspace
        return await self._send_command("autopilot_submit", payload)

    async def autopilot_list_goals(self) -> dict[str, Any]:
        """List all goals (including non-root children)."""
        return await self._send_command("autopilot_list_goals")

    async def autopilot_get_goal(self, goal_id: str) -> dict[str, Any]:
        """Fetch one goal by id."""
        return await self._send_command("autopilot_get_goal", {"goal_id": goal_id})

    async def autopilot_cancel_goal(self, goal_id: str) -> dict[str, Any]:
        """Cancel a goal and its non-terminal descendants."""
        return await self._send_command("autopilot_cancel_goal", {"goal_id": goal_id})

    async def autopilot_cancel_all(self) -> dict[str, Any]:
        """Cancel every open (non-terminal) goal in one call.

        Prefer ``job_cancel(job_id)`` when you know the job root. Use this when
        you need a bulk stop of leftover pending/active goals.
        """
        return await self._send_command("autopilot_cancel_all")

    async def autopilot_wake(self) -> dict[str, Any]:
        """Exit dreaming mode and resume scheduling."""
        return await self._send_command("autopilot_wake")

    async def autopilot_dream(self) -> dict[str, Any]:
        """Force dreaming mode."""
        return await self._send_command("autopilot_dream")

    async def autopilot_resume(self, goal_id: str) -> dict[str, Any]:
        """Resume a suspended or blocked goal."""
        return await self._send_command("autopilot_resume", {"goal_id": goal_id})

    async def autopilot_list_jobs(self) -> dict[str, Any]:
        """List root goals only (jobs). Prefer ``job_*`` for job control."""
        return await self._send_command("autopilot_list_jobs")

    async def autopilot_get_job(self, job_id: str) -> dict[str, Any]:
        """Get a root job with DAG snapshot. Prefer ``job_status`` / ``job_dag``."""
        return await self._send_command("autopilot_get_job", {"job_id": job_id})

    async def autopilot_subscribe(self) -> dict[str, Any]:
        """Subscribe this connection to autopilot worker events."""
        return await self._send_command("autopilot_subscribe")

    async def autopilot_unsubscribe(self) -> dict[str, Any]:
        """Unsubscribe from autopilot worker events."""
        return await self._send_command("autopilot_unsubscribe")

    # --- Jobs (preferred for job lifecycle) ------------------------------

    async def job_create(
        self,
        goal: str,
        *,
        workspace: str | None = None,
        autonomous: bool = False,
        max_iterations: int | None = None,
        guidance: str | None = None,
    ) -> dict[str, Any]:
        """Create a background job (root goal). Returns ``job_id`` + status."""
        payload: dict[str, Any] = {"goal": goal}
        if workspace:
            payload["workspace"] = workspace
        if autonomous:
            payload["autonomous"] = autonomous
        if max_iterations:
            payload["max_iterations"] = max_iterations
        if guidance:
            payload["guidance"] = guidance
        return await self._send_command("job_create", payload)

    async def job_status(self, job_id: str) -> dict[str, Any]:
        """Get job status with goal counts and workers."""
        return await self._send_command("job_status", {"job_id": job_id})

    async def job_pause(self, job_id: str) -> dict[str, Any]:
        """Pause a running job (status becomes suspended)."""
        return await self._send_command("job_pause", {"job_id": job_id})

    async def job_resume(self, job_id: str) -> dict[str, Any]:
        """Resume a paused job."""
        return await self._send_command("job_resume", {"job_id": job_id})

    async def job_cancel(self, job_id: str) -> dict[str, Any]:
        """Cancel a job root and all non-terminal descendants."""
        return await self._send_command("job_cancel", {"job_id": job_id})

    async def job_dag(self, job_id: str) -> dict[str, Any]:
        """Get the job goal DAG (nodes/edges) for visualization."""
        return await self._send_command("job_dag", {"job_id": job_id})

    async def job_guidance(
        self, job_id: str, content: str, *, goal_id: str | None = None
    ) -> dict[str, Any]:
        """Send guidance text to a job or a specific goal under it."""
        payload: dict[str, Any] = {"job_id": job_id, "content": content}
        if goal_id:
            payload["goal_id"] = goal_id
        return await self._send_command("job_guidance", payload)

    # --- Cron ------------------------------------------------------------

    async def cron_add(self, text: str, *, priority: int | None = None) -> dict[str, Any]:
        """Submit a natural-language scheduled job."""
        payload: dict[str, Any] = {"text": text}
        if priority is not None:
            payload["priority"] = priority
        result = await self._send_command("cron_add", payload)
        return _normalize_cron_add_result(result)

    async def cron_list(self, *, status: str | None = None) -> dict[str, Any]:
        """List scheduled cron jobs (optional ``status`` filter)."""
        payload: dict[str, Any] = {}
        if status:
            payload["status"] = status
        return await self._send_command("cron_list", payload)

    async def cron_show(self, job_id: str) -> dict[str, Any]:
        """Get details for one cron job."""
        result = await self._send_command("cron_show", {"job_id": job_id})
        return _normalize_cron_show_result(result)

    async def cron_cancel(self, job_id: str) -> dict[str, Any]:
        """Cancel a scheduled cron job."""
        return await self._send_command("cron_cancel", {"job_id": job_id})

    # --- Memory (admin) --------------------------------------------------

    async def memory_stats(self, mode: str = "daemon") -> dict[str, Any]:
        """Query daemon memory profiling stats (admin)."""
        return await self._send_command("memory_stats", {"mode": mode})


class CommandClient:
    """Synchronous wrapper around ``AsyncCommandClient`` for scripts and CLI.

    Each method opens a short-lived WebSocket RPC (same behavior as async).

    Args:
        ws_url: Daemon WebSocket URL.
        timeout: Per-command timeout in seconds.
    """

    def __init__(self, ws_url: str, *, timeout: float = 30.0) -> None:
        self._client = AsyncCommandClient(ws_url, timeout=timeout)

    def _run_async(self, coro: Any) -> Any:
        """Run an async coroutine from sync code."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            return asyncio.ensure_future(coro)
        return asyncio.run(coro)

    # --- Autopilot goals -------------------------------------------------

    def autopilot_status(self) -> dict[str, Any]:
        """Return autopilot scheduler status."""
        return cast(dict[str, Any], self._run_async(self._client.autopilot_status()))

    def autopilot_submit(
        self, description: str, *, priority: int = 50, workspace: str | None = None
    ) -> dict[str, Any]:
        """Submit a new autopilot goal."""
        return cast(
            dict[str, Any],
            self._run_async(
                self._client.autopilot_submit(description, priority=priority, workspace=workspace)
            ),
        )

    def autopilot_list_goals(self) -> dict[str, Any]:
        """List all goals."""
        return cast(dict[str, Any], self._run_async(self._client.autopilot_list_goals()))

    def autopilot_get_goal(self, goal_id: str) -> dict[str, Any]:
        """Fetch one goal by id."""
        return cast(dict[str, Any], self._run_async(self._client.autopilot_get_goal(goal_id)))

    def autopilot_cancel_goal(self, goal_id: str) -> dict[str, Any]:
        """Cancel a goal and its non-terminal descendants."""
        return cast(dict[str, Any], self._run_async(self._client.autopilot_cancel_goal(goal_id)))

    def autopilot_cancel_all(self) -> dict[str, Any]:
        """Cancel every open (non-terminal) goal."""
        return cast(dict[str, Any], self._run_async(self._client.autopilot_cancel_all()))

    def autopilot_wake(self) -> dict[str, Any]:
        """Exit dreaming mode."""
        return cast(dict[str, Any], self._run_async(self._client.autopilot_wake()))

    def autopilot_dream(self) -> dict[str, Any]:
        """Force dreaming mode."""
        return cast(dict[str, Any], self._run_async(self._client.autopilot_dream()))

    def autopilot_resume(self, goal_id: str) -> dict[str, Any]:
        """Resume a suspended or blocked goal."""
        return cast(dict[str, Any], self._run_async(self._client.autopilot_resume(goal_id)))

    def autopilot_list_jobs(self) -> dict[str, Any]:
        """List root goals only (jobs)."""
        return cast(dict[str, Any], self._run_async(self._client.autopilot_list_jobs()))

    def autopilot_get_job(self, job_id: str) -> dict[str, Any]:
        """Get a root job with DAG snapshot."""
        return cast(dict[str, Any], self._run_async(self._client.autopilot_get_job(job_id)))

    def autopilot_subscribe(self) -> dict[str, Any]:
        """Subscribe to autopilot worker events."""
        return cast(dict[str, Any], self._run_async(self._client.autopilot_subscribe()))

    def autopilot_unsubscribe(self) -> dict[str, Any]:
        """Unsubscribe from autopilot worker events."""
        return cast(dict[str, Any], self._run_async(self._client.autopilot_unsubscribe()))

    # --- Jobs ------------------------------------------------------------

    def job_create(
        self,
        goal: str,
        *,
        workspace: str | None = None,
        autonomous: bool = False,
        max_iterations: int | None = None,
        guidance: str | None = None,
    ) -> dict[str, Any]:
        """Create a background job (root goal)."""
        return cast(
            dict[str, Any],
            self._run_async(
                self._client.job_create(
                    goal,
                    workspace=workspace,
                    autonomous=autonomous,
                    max_iterations=max_iterations,
                    guidance=guidance,
                )
            ),
        )

    def job_status(self, job_id: str) -> dict[str, Any]:
        """Get job status with goal counts and workers."""
        return cast(dict[str, Any], self._run_async(self._client.job_status(job_id)))

    def job_pause(self, job_id: str) -> dict[str, Any]:
        """Pause a running job."""
        return cast(dict[str, Any], self._run_async(self._client.job_pause(job_id)))

    def job_resume(self, job_id: str) -> dict[str, Any]:
        """Resume a paused job."""
        return cast(dict[str, Any], self._run_async(self._client.job_resume(job_id)))

    def job_cancel(self, job_id: str) -> dict[str, Any]:
        """Cancel a job root and all non-terminal descendants."""
        return cast(dict[str, Any], self._run_async(self._client.job_cancel(job_id)))

    def job_dag(self, job_id: str) -> dict[str, Any]:
        """Get the job goal DAG for visualization."""
        return cast(dict[str, Any], self._run_async(self._client.job_dag(job_id)))

    def job_guidance(
        self, job_id: str, content: str, *, goal_id: str | None = None
    ) -> dict[str, Any]:
        """Send guidance text to a job or a specific goal under it."""
        return cast(
            dict[str, Any],
            self._run_async(self._client.job_guidance(job_id, content, goal_id=goal_id)),
        )

    # --- Cron ------------------------------------------------------------

    def cron_add(self, text: str, *, priority: int | None = None) -> dict[str, Any]:
        """Submit a natural-language scheduled job."""
        return cast(dict[str, Any], self._run_async(self._client.cron_add(text, priority=priority)))

    def cron_list(self, *, status: str | None = None) -> dict[str, Any]:
        """List scheduled cron jobs."""
        return cast(dict[str, Any], self._run_async(self._client.cron_list(status=status)))

    def cron_show(self, job_id: str) -> dict[str, Any]:
        """Get details for one cron job."""
        return cast(dict[str, Any], self._run_async(self._client.cron_show(job_id)))

    def cron_cancel(self, job_id: str) -> dict[str, Any]:
        """Cancel a scheduled cron job."""
        return cast(dict[str, Any], self._run_async(self._client.cron_cancel(job_id)))

    # --- Memory (admin) --------------------------------------------------

    def memory_stats(self, mode: str = "daemon") -> dict[str, Any]:
        """Query daemon memory profiling stats (admin)."""
        return cast(dict[str, Any], self._run_async(self._client.memory_stats(mode)))


def command_client_from_config(cfg: Any) -> CommandClient:
    """Build a sync command client from soothe/CLI config (host/port)."""
    ws_url = websocket_url_from_config(cfg)
    return CommandClient(ws_url)


def async_command_client_from_config(cfg: Any) -> AsyncCommandClient:
    """Build an async command client from soothe/CLI config (host/port)."""
    ws_url = websocket_url_from_config(cfg)
    return AsyncCommandClient(ws_url)


__all__ = [
    "AsyncCommandClient",
    "CommandClient",
    "command_client_from_config",
    "async_command_client_from_config",
]
