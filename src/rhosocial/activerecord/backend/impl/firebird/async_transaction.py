"""Firebird asynchronous transaction manager implementation."""

import logging
from typing import Optional

from rhosocial.activerecord.backend.transaction import (
    AsyncTransactionManager, IsolationLevel, TransactionMode
)


class AsyncFirebirdTransactionManager(AsyncTransactionManager):
    """Firebird-specific async transaction manager.

    Executes transaction SQL via backend.execute() using the async
    execution pipeline (which wraps sync fdb calls in a thread pool).
    """

    async def _do_begin(self, isolation_level: Optional[IsolationLevel] = None,
                        mode: Optional[TransactionMode] = None,
                        wait: bool = True,
                        lock_timeout: Optional[int] = None) -> None:
        """Begin a transaction via backend.execute()."""
        sql, params = self._build_begin_sql()
        self.log(logging.DEBUG, f"Executing: {sql}")
        await self._backend.execute(sql, params)

    async def _do_commit(self) -> None:
        """Commit the current transaction via backend.execute()."""
        sql, params = self._build_commit_sql()
        self.log(logging.DEBUG, f"Executing: {sql}")
        await self._backend.execute(sql, params)

    async def _do_rollback(self) -> None:
        """Rollback the current transaction via backend.execute()."""
        sql, params = self._build_rollback_sql()
        self.log(logging.DEBUG, f"Executing: {sql}")
        await self._backend.execute(sql, params)

    async def _do_create_savepoint(self, name: str) -> None:
        """Create a savepoint via backend.execute()."""
        sql, params = self._build_savepoint_sql(name)
        await self._backend.execute(sql, params)

    async def _do_release_savepoint(self, name: str) -> None:
        pass

    async def _do_rollback_savepoint(self, name: str) -> None:
        """Rollback to a savepoint via backend.execute()."""
        sql, params = self._build_rollback_sql(savepoint=name)
        await self._backend.execute(sql, params)

    async def supports_savepoint(self) -> bool:
        return True
