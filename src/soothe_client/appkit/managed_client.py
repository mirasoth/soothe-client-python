"""ManagedClient seam for appkit ConnectionPool / TurnRunner (RFC-629).

The concrete ``WebSocketClient`` satisfies it via ``WebSocketManagedClient``;
tests supply fakes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from soothe_client.errors import DisconnectCause
from soothe_client.websocket import WebSocketClient

ClientFactory = Callable[[str], "ManagedClient"]
BootstrapFunc = Callable[
    ["ManagedClient", str, str],
    Awaitable[str],
]


@runtime_checkable
class ManagedClient(Protocol):
    """Subset of Layer 0 that ConnectionPool and TurnRunner depend on."""

    async def connect(self) -> None:
        """Dial and handshake."""
        ...

    async def reconnect(self) -> None:
        """Re-dial after a drop."""
        ...

    async def reattach_and_probe(self, loop_id: str) -> None:
        """Resume a loop by id and probe liveness."""
        ...

    async def send_message(self, msg: Any) -> None:
        """Send a fire-and-forget JSON frame (legacy flat or wire envelope)."""
        ...

    def receive_messages(
        self,
        *,
        cancel_event: Any | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield decoded daemon events until EOF or cancel."""
        ...

    def is_disconnected(self) -> bool:
        """Return whether the disconnect signal has fired."""
        ...

    def disconnect_cause(self) -> DisconnectCause | None:
        """Return the disconnect cause, or None if still connected."""
        ...

    def is_connected(self) -> bool:
        """Report connection liveness."""
        ...

    async def close(self) -> None:
        """Tear down the connection."""
        ...


class WebSocketManagedClient:
    """Adapter wrapping ``WebSocketClient`` as a ``ManagedClient``."""

    def __init__(self, client: WebSocketClient) -> None:
        self._client = client

    @property
    def underlying(self) -> WebSocketClient:
        """Return the wrapped Layer 0 client."""
        return self._client

    async def connect(self) -> None:
        await self._client.connect()
        await self._client.request_connection_init()
        await self._client.wait_for_connection_ack()

    async def reconnect(self) -> None:
        await self._client.reconnect()

    async def reattach_and_probe(self, loop_id: str) -> None:
        await self._client.reattach_and_probe(loop_id)

    async def send_message(self, msg: Any) -> None:
        if not isinstance(msg, dict):
            raise TypeError("send_message expects a dict payload")
        await self._client.send(msg)

    async def receive_messages(
        self,
        *,
        cancel_event: Any | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                return
            event = await self._client.read_event()
            if event is None:
                return
            yield event

    def is_disconnected(self) -> bool:
        return self._client.is_disconnected()

    def disconnect_cause(self) -> DisconnectCause | None:
        return self._client.disconnect_cause()

    def is_connected(self) -> bool:
        alive = getattr(self._client, "is_connection_alive", None)
        if callable(alive):
            return bool(alive()) and not self._client.is_disconnected()
        return bool(self._client.is_connected) and not self._client.is_disconnected()

    async def close(self) -> None:
        await self._client.close()


def default_client_factory() -> ClientFactory:
    """Return a factory that builds ``WebSocketManagedClient`` instances."""

    def _factory(url: str) -> ManagedClient:
        return WebSocketManagedClient(WebSocketClient(url=url))

    return _factory


def default_bootstrap_func() -> BootstrapFunc:
    """Default bootstrap: ``loop_new`` + ``subscribe(loop_events)``."""

    async def _bootstrap(client: ManagedClient, workspace_id: str, user_id: str) -> str:
        from soothe_client.session import bootstrap_loop_session

        underlying = getattr(client, "underlying", client)
        status = await bootstrap_loop_session(
            underlying,
            resume_loop_id=None,
            user_id=user_id or None,
            client_workspace_id=workspace_id or None,
            workspace=workspace_id or None,
        )
        if status.get("type") == "error":
            raise RuntimeError(str(status.get("message", "daemon bootstrap failed")))
        loop_id = str(status.get("loop_id") or "").strip()
        if not loop_id:
            raise RuntimeError("bootstrap_loop_session returned no loop_id")
        return loop_id

    return _bootstrap


__all__ = [
    "BootstrapFunc",
    "ClientFactory",
    "ManagedClient",
    "WebSocketManagedClient",
    "default_bootstrap_func",
    "default_client_factory",
]
