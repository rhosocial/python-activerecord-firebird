"""Firebird asynchronous transaction manager implementation."""

import asyncio
from typing import Optional

from rhosocial.activerecord.backend.transaction import (
    AsyncTransactionManager, IsolationLevel, TransactionMode
)


class AsyncFirebirdTransactionManager(AsyncTransactionManager):
    """Firebird-specific async transaction manager.

    Uses firebird-driver's native transaction API (connection.begin/commit/
    rollback/savepoint), mirroring the synchronous :class:`FirebirdTransactionManager`,
    with the blocking fdb calls dispatched through a thread pool executor.
    """

    def _run(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        executor = getattr(self._backend, "_executor", None)
        return loop.run_in_executor(executor, lambda: func(*args, **kwargs))

    async def _do_begin(self, isolation_level: Optional[IsolationLevel] = None,
                        mode: Optional[TransactionMode] = None,
                        wait: bool = True,
                        lock_timeout: Optional[int] = None) -> None:
        """Begin a transaction using the native connection API."""
        conn = self._backend._connection
        await self._run(conn.begin)

    async def _do_commit(self) -> None:
        """Commit the current transaction using the native connection API."""
        conn = self._backend._connection
        await self._run(conn.commit)

    async def _do_rollback(self) -> None:
        """Rollback the current transaction using the native connection API."""
        conn = self._backend._connection
        await self._run(conn.rollback)

    async def _do_create_savepoint(self, name: str) -> None:
        """Create a savepoint using the native connection API."""
        conn = self._backend._connection
        await self._run(conn.savepoint, name)

    async def _do_release_savepoint(self, name: str) -> None:
        pass

    async def _do_rollback_savepoint(self, name: str) -> None:
        """Rollback to a savepoint using the native connection API."""
        conn = self._backend._connection
        await self._run(lambda: conn.rollback(savepoint=name))

    async def supports_savepoint(self) -> bool:
        return True
