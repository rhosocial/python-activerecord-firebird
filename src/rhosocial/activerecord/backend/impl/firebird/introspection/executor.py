# src/rhosocial/activerecord/backend/impl/firebird/introspection/executor.py
"""Firebird-specific introspector executor.

The core :class:`AsyncIntrospectorExecutor` assumes the driver's cursor
exposes an async API (``await cursor.execute``). firebird-driver cursors
are synchronous, so this executor wraps the sync cursor operations in the
async backend's thread pool executor.
"""

import asyncio
from typing import Any, Dict, List, Tuple


class SyncFirebirdIntrospectorExecutor:
    """Executor that wraps a synchronous Firebird backend."""

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def execute(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Execute SQL synchronously and return rows as a list of dicts."""
        cursor = self._backend._get_cursor()
        try:
            cursor.execute(sql, params)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
        finally:
            cursor.close()


class AsyncFirebirdIntrospectorExecutor:
    """Executor that wraps an asynchronous Firebird backend.

    Runs the synchronous firebird-driver cursor operations in the async
    backend's thread pool executor.
    """

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    async def execute(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Execute SQL asynchronously and return rows as a list of dicts."""
        loop = asyncio.get_event_loop()
        cursor = await self._backend._get_cursor()
        try:
            await loop.run_in_executor(
                self._backend._executor, lambda: cursor.execute(sql, params)
            )
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = await loop.run_in_executor(self._backend._executor, cursor.fetchall)
                return [dict(zip(columns, row, strict=False)) for row in rows]
            return []
        finally:
            try:
                await loop.run_in_executor(self._backend._executor, cursor.close)
            except Exception:
                pass


__all__ = [
    "SyncFirebirdIntrospectorExecutor",
    "AsyncFirebirdIntrospectorExecutor",
]
