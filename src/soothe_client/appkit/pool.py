"""Per-session connection pool for appkit.

Manages a pool of daemon connections, one active per session. Reuses an
active connection when still live, otherwise bootstraps a fresh loop or
reattaches an existing one. Persistence of session↔loop mappings is
abstracted behind ``SessionStore``.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from soothe_client.appkit.managed_client import (
    BootstrapFunc,
    ClientFactory,
    ManagedClient,
    default_bootstrap_func,
    default_client_factory,
)
from soothe_client.appkit.session_store import SessionStore
from soothe_client.errors import StaleLoopError


class ErrPoolExhausted(Exception):  # noqa: N818 — match Go/TS name
    """Raised when no free connection slot is available."""

    def __init__(self) -> None:
        super().__init__("appkit: connection pool exhausted")


@dataclass(slots=True)
class PoolConfig:
    """Configures a ``ConnectionPool``. Zero / negative sizes use defaults."""

    pool_size: int = 1000
    query_timeout_s: float = 30 * 60
    connection_timeout_s: float = 30.0
    max_idle_time_s: float = 10 * 60
    health_check_interval_s: float = 30.0


def default_pool_config() -> PoolConfig:
    """Return conservative pool defaults suitable for most apps."""
    return PoolConfig()


class PooledConn:
    """One connection slot in the pool."""

    __slots__ = (
        "slot_id",
        "client",
        "event_stream",
        "stream_cancel",
        "session_id",
        "loop_id",
        "workspace_id",
        "last_used",
    )

    def __init__(self, slot_id: int, client: ManagedClient) -> None:
        self.slot_id = slot_id
        self.client = client
        self.event_stream: AsyncIterator[dict[str, Any]] | None = None
        self.stream_cancel: asyncio.Event | None = None
        self.session_id = ""
        self.loop_id = ""
        self.workspace_id = ""
        self.last_used = 0.0

    def is_disconnected(self) -> bool:
        """Report whether the underlying client signalled a drop."""
        return self.client.is_disconnected()

    def is_connected(self) -> bool:
        """Report whether the slot is still usable."""
        return self.client.is_connected() and not self.is_disconnected()

    def get_loop_id(self) -> str:
        """Return the active loop id for this slot."""
        return self.loop_id


class ConnectionPool:
    """Manage a pool of daemon connections, one active per session."""

    def __init__(
        self,
        url: str,
        store: SessionStore,
        cfg: PoolConfig | None = None,
        factory: ClientFactory | None = None,
    ) -> None:
        self._cfg = cfg or default_pool_config()
        if self._cfg.pool_size <= 0:
            self._cfg = PoolConfig(
                pool_size=default_pool_config().pool_size,
                query_timeout_s=self._cfg.query_timeout_s,
                connection_timeout_s=self._cfg.connection_timeout_s,
                max_idle_time_s=self._cfg.max_idle_time_s,
                health_check_interval_s=self._cfg.health_check_interval_s,
            )
        self._factory = factory or default_client_factory()
        self._bootstrap: BootstrapFunc = default_bootstrap_func()
        self._store = store
        self._url = url
        self._pool: list[PooledConn] = []
        self._active: dict[str, PooledConn] = {}
        self._next_slot_id = 1
        self._lock = asyncio.Lock()
        for _ in range(self._cfg.pool_size):
            self._pool.append(self._new_slot())

    def with_bootstrap(self, bootstrap: BootstrapFunc) -> ConnectionPool:
        """Override the loop bootstrap function (useful for test fakes)."""
        self._bootstrap = bootstrap
        return self

    def with_client_factory(self, factory: ClientFactory) -> ConnectionPool:
        """Override the client factory (useful for test fakes)."""
        self._factory = factory
        return self

    def stats(self) -> dict[str, int]:
        """Return a snapshot of active and idle slot counts."""
        return {"active": len(self._active), "idle": len(self._pool)}

    def _new_slot(self) -> PooledConn:
        slot_id = self._next_slot_id
        self._next_slot_id += 1
        return PooledConn(slot_id, self._factory(self._url))

    async def acquire(
        self,
        session_id: str,
        workspace_id: str,
        user_id: str,
    ) -> PooledConn:
        """Return a live connection for ``session_id``.

        Caller must ``release`` when done (turn completes or session reset).
        """
        async with self._lock:
            existing = self._active.get(session_id)
            if existing is not None:
                if existing.is_disconnected() or not existing.is_connected():
                    await self._release_unlocked(session_id)
                else:
                    existing.last_used = time.monotonic()
                    with contextlib.suppress(Exception):
                        await self._store.update_last_used(session_id)
                    return existing

            if not self._pool:
                raise ErrPoolExhausted()
            conn = self._pool.pop()
            self._active[session_id] = conn

        loop_id = ""
        ok = False
        with contextlib.suppress(Exception):
            loop_id, ok = await self._store.get_loop_id_for_session(session_id)

        final_loop_id = ""
        try:
            if not ok or not loop_id:
                await conn.client.connect()
                final_loop_id = await self._bootstrap_new(conn, workspace_id, user_id)
                with contextlib.suppress(Exception):
                    await self._store.create_session(workspace_id, session_id, final_loop_id, "")
            else:
                try:
                    await self._resume_and_reattach(conn, loop_id)
                    final_loop_id = loop_id
                except Exception:
                    await conn.client.connect()
                    final_loop_id = await self._bootstrap_new(conn, workspace_id, user_id)
                    with contextlib.suppress(Exception):
                        await self._store.create_session(
                            workspace_id, session_id, final_loop_id, ""
                        )
        except Exception:
            await self.release(session_id)
            raise

        conn.session_id = session_id
        conn.loop_id = final_loop_id
        conn.workspace_id = workspace_id
        conn.last_used = time.monotonic()
        with contextlib.suppress(Exception):
            await self._store.update_last_used(session_id)
        return conn

    async def release(self, session_id: str) -> None:
        """Tear down the connection for ``session_id`` and return a fresh slot."""
        async with self._lock:
            await self._release_unlocked(session_id)

    async def _release_unlocked(self, session_id: str) -> None:
        conn = self._active.pop(session_id, None)
        if conn is None:
            return
        if conn.stream_cancel is not None:
            conn.stream_cancel.set()
            conn.stream_cancel = None
        with contextlib.suppress(Exception):
            await conn.client.close()
        conn.session_id = ""
        conn.loop_id = ""
        conn.event_stream = None
        self._pool.append(self._new_slot())

    async def reset_session(self, session_id: str) -> None:
        """Tear down so the next acquire bootstraps fresh."""
        await self.release(session_id)

    async def stop(self) -> None:
        """Gracefully shut down all active connections."""
        async with self._lock:
            for sid in list(self._active):
                await self._release_unlocked(sid)

    async def _bootstrap_new(
        self,
        conn: PooledConn,
        workspace_id: str,
        user_id: str,
    ) -> str:
        loop_id = await self._bootstrap(conn.client, workspace_id, user_id)
        self._start_reader(conn)
        return loop_id

    async def _resume_and_reattach(self, conn: PooledConn, loop_id: str) -> None:
        await conn.client.connect()
        try:
            await conn.client.reattach_and_probe(loop_id)
        except StaleLoopError:
            raise
        self._start_reader(conn)

    def _start_reader(self, conn: PooledConn) -> None:
        cancel = asyncio.Event()
        conn.stream_cancel = cancel
        conn.event_stream = conn.client.receive_messages(cancel_event=cancel)


__all__ = [
    "ConnectionPool",
    "ErrPoolExhausted",
    "PoolConfig",
    "PooledConn",
    "default_pool_config",
]
