"""Firebird asynchronous backend implementation.

This module provides the async Firebird backend using a thread pool
wrapper around the synchronous firebird-driver (fdb), since there is
no native async driver for Firebird.

IMPORTANT: This is a pseudo-async implementation. All I/O operations
are executed in a thread pool executor (``run_in_executor``), which
means:

1. Under high concurrency, the default ThreadPoolExecutor may become
   a bottleneck (default size: ``min(32, cpu_count + 4)``).
2. Performance benefits from uvloop or similar are lost — the
   underlying fdb calls remain synchronous.
3. To prevent connection storms, inject a bounded executor:

       from concurrent.futures import ThreadPoolExecutor
       backend = AsyncFirebirdBackend(
           executor=ThreadPoolExecutor(max_workers=10),
           ...
       )
"""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import Executor
from typing import Optional, Tuple

from rhosocial.activerecord.backend.base import AsyncStorageBackend
from rhosocial.activerecord.backend import errors as exc
from rhosocial.activerecord.backend.introspection.backend_mixin import IntrospectorBackendMixin
from rhosocial.activerecord.backend.options import (
    ExecutionOptions, InsertOptions, UpdateOptions, DeleteOptions,
)
from rhosocial.activerecord.backend.result import QueryResult
from rhosocial.activerecord.backend.schema import StatementType

from .config import FirebirdConnectionConfig
from .mixins import FirebirdBackendMixin
from .async_transaction import AsyncFirebirdTransactionManager


class AsyncFirebirdBackend(
    IntrospectorBackendMixin,
    FirebirdBackendMixin,
    AsyncStorageBackend,
):
    """Firebird-specific async backend implementation.

    Uses asyncio thread pool to wrap the synchronous firebird-driver
    for async compatibility.
    """

    def __init__(self, *, executor: Optional[Executor] = None, **kwargs):
        """Initialize async Firebird backend with connection configuration.

        Args:
            executor: Optional custom ``concurrent.futures.Executor`` for
                running synchronous fdb operations. If not provided, the
                default ``ThreadPoolExecutor`` is used.
        """
        self._executor = executor

        connection_config = kwargs.get('connection_config')
        if connection_config is None:
            config_params = {}
            fb_params = [
                'host', 'port', 'database', 'username', 'user',
                'password', 'role', 'charset', 'page_size',
                'wire_compression', 'use_unicode', 'autocommit',
                'timeout', 'timezone', 'version',
                'log_queries', 'log_level',
                'pool_size', 'pool_timeout',
            ]
            for param in fb_params:
                if param in kwargs:
                    config_params[param] = kwargs[param]
            kwargs['connection_config'] = FirebirdConnectionConfig(**config_params)

        super().__init__(**kwargs)
        self._connection = None
        self._cursor = None
        self._is_connected = False
        self._transaction_manager = AsyncFirebirdTransactionManager(self)
        self._register_firebird_adapters()
        self.log(logging.DEBUG, "Initialized AsyncFirebirdBackend")

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Establish a connection to the Firebird database asynchronously."""
        self._ensure_client_library()
        try:
            import firebird.driver as fdb
            config = self.config
            if config.host and config.port and config.database:
                dsn = f"{config.host}/{config.port}:{config.database}"
            elif config.database:
                dsn = config.database
            else:
                raise exc.ConnectionError("No database specified in config")
            connect_params = {
                'database': dsn,
                'user': config.username or getattr(config, 'user', None),
                'password': config.password,
                'charset': config.charset,
            }
            if config.role:
                connect_params['role'] = config.role
            if getattr(config, 'timezone', None):
                connect_params['session_time_zone'] = config.timezone

            loop = asyncio.get_event_loop()
            self._connection = await loop.run_in_executor(
                self._executor, lambda: fdb.connect(**connect_params)
            )
            self._cursor = self._connection.cursor()
            self._is_connected = True
            self.log(logging.INFO, "Connected to Firebird (async)")
        except Exception as e:
            raise exc.ConnectionError(f"Failed to connect to Firebird: {e}") from e

    async def disconnect(self) -> None:
        """Close the connection to the Firebird database."""
        if self._connection:
            try:
                loop = asyncio.get_event_loop()
                if self._cursor:
                    await loop.run_in_executor(self._executor, self._cursor.close)
                    self._cursor = None
                await loop.run_in_executor(self._executor, self._connection.close)
                self.log(logging.INFO, "Disconnected from Firebird (async)")
            except Exception as e:
                self.log(logging.WARNING, f"Error disconnecting from Firebird: {e}")
            finally:
                self._connection = None
                self._is_connected = False

    async def ping(self, reconnect: bool = True) -> bool:
        """Check if the connection is alive."""
        if not self._is_connected or self._connection is None:
            if reconnect:
                await self.connect()
                return True
            return False
        try:
            loop = asyncio.get_event_loop()
            cursor = self._cursor or self._connection.cursor()
            await loop.run_in_executor(
                self._executor, lambda: cursor.execute("SELECT 1 FROM RDB$DATABASE")
            )
            await loop.run_in_executor(self._executor, cursor.fetchone)
            return True
        except Exception:
            if reconnect:
                try:
                    await self.disconnect()
                    await self.connect()
                    return True
                except Exception:
                    return False
            return False

    async def get_server_version(self) -> Tuple[int, int, int]:
        """Get the Firebird server version asynchronously."""
        if not self._is_connected:
            await self.connect()
        loop = asyncio.get_event_loop()
        cursor = self._cursor or self._connection.cursor()
        try:
            await loop.run_in_executor(
                self._executor,
                lambda: cursor.execute(
                    "SELECT RDB$GET_CONTEXT('SYSTEM', 'ENGINE_VERSION') FROM RDB$DATABASE"
                ),
            )
            row = await loop.run_in_executor(self._executor, cursor.fetchone)
            if row and row[0]:
                version_str = str(row[0])
            else:
                await loop.run_in_executor(
                    self._executor,
                    lambda: cursor.execute("SELECT MON$VERSION FROM MON$DATABASE"),
                )
                row = await loop.run_in_executor(self._executor, cursor.fetchone)
                if row and row[0]:
                    version_str = str(row[0])
                else:
                    return (2, 5, 0)
        except Exception:
            try:
                await loop.run_in_executor(
                    self._executor,
                    lambda: cursor.execute("SELECT * FROM RDB$DATABASE"),
                )
                desc = cursor.description
                version_str = str(desc[0][0]) if desc else "2.5.0"
            except Exception:
                return (2, 5, 0)
        import re
        match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_str)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return (2, 5, 0)

    async def introspect_and_adapt(self) -> None:
        """Introspect the Firebird database and adapt type mappings."""
        if not self._is_connected:
            await self.connect()
        version = await self.get_server_version()
        self.dialect.version = version
        if hasattr(self.config, 'version') and self.config.version is None:
            self.config.version = version
        if version < (3, 0, 0):
            from .adapters import FirebirdBooleanAdapter
            bool_adapter = FirebirdBooleanAdapter(use_char=True)
            self.adapter_registry.register(bool_adapter, bool, bool, allow_override=True)
            self.adapter_registry.register(bool_adapter, bool, str, allow_override=True)

    # ------------------------------------------------------------------
    # Error handling — FirebirdBackendMixin._handle_error is sync and
    # non-I/O, so we call it directly from the async wrapper.
    # ------------------------------------------------------------------

    async def _handle_error(self, error: Exception) -> None:
        """Handle and classify a Firebird error."""
        FirebirdBackendMixin._handle_error(self, error)

    # ------------------------------------------------------------------
    # Execution hooks — wrap sync fdb operations in run_in_executor
    # ------------------------------------------------------------------

    async def _get_cursor(self):
        """Get or create a cursor asynchronously."""
        if not self._is_connected or self._connection is None:
            raise exc.ConnectionError("Not connected to Firebird database")
        if self._cursor is None:
            self._cursor = self._connection.cursor()
        return self._cursor

    async def _execute_query(self, cursor, sql: str, params: Optional[Tuple]):
        """Execute query in thread pool."""
        loop = asyncio.get_event_loop()

        def _run():
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return cursor

        return await loop.run_in_executor(self._executor, _run)

    async def _process_result_set(self, cursor, is_select, column_adapters=None, column_mapping=None):
        """Process result set in thread pool."""
        if not is_select:
            return None

        loop = asyncio.get_event_loop()

        def _run():
            try:
                rows = cursor.fetchall()
                if not rows:
                    return []
                column_names = [desc[0].strip('"').lower() for desc in cursor.description]
                char_columns = self._char_columns_from_cursor(cursor)
                adapters = column_adapters or {}
                mapping = column_mapping or {}
                final_results = []
                for row in rows:
                    row_dict = dict(zip(column_names, row))
                    adapted_row = self._adapt_row_types(row_dict, adapters)
                    final_row = self._remap_row_columns(adapted_row, mapping)
                    if char_columns:
                        for col in char_columns:
                            if isinstance(final_row.get(col), str):
                                final_row[col] = final_row[col].rstrip(' ')
                    final_results.append(final_row)
                return final_results
            except Exception as e:
                self.logger.error(f"Error processing result set: {str(e)}", exc_info=True)
                raise

        return await loop.run_in_executor(self._executor, _run)

    def _char_columns_from_cursor(self, cursor) -> set:
        """Detect CHAR-type columns using the sync backend helper.

        Firebird pads CHAR values with trailing spaces on read, so only CHAR
        columns need the padding stripped. Delegates to the shared
        implementation on :class:`FirebirdBackend`.
        """
        from .backend import FirebirdBackend

        return FirebirdBackend._char_columns_from_cursor(cursor)

    async def _handle_auto_commit(self) -> None:
        """Handle auto commit in thread pool."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(self._executor, self._connection.commit)
        except Exception:
            pass

    async def executescript(self, sql_script: str) -> None:
        """Execute a multi-statement SQL script asynchronously.

        Mirrors the synchronous :meth:`FirebirdBackend.executescript` by
        running the underlying firebird-driver cursor in a thread pool so
        async and sync backends expose the same API surface.
        """
        start_time = time.perf_counter()
        try:
            if not self._is_connected or self._connection is None:
                await self.connect()
            cursor = self._connection.cursor()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self._executor, lambda: cursor.execute(sql_script))
            duration = time.perf_counter() - start_time
            self.log(logging.INFO, f"Async SQL script executed successfully, duration={duration:.3f}s")
            await self._handle_auto_commit_if_needed()
            try:
                cursor.close()
            except Exception:
                pass
        except Exception as e:
            try:
                cursor.close()
            except Exception:
                pass
            self.log(logging.ERROR, f"Error executing async SQL script: {e}")
            await self._handle_error(e)

    # ------------------------------------------------------------------
    # SQL helpers
    # ------------------------------------------------------------------

    def _prepare_sql_and_params(self, sql: str, params: Optional[Tuple] = None) -> Tuple[str, Optional[Tuple]]:
        return sql, params

    def _detect_statement_type(self, sql: str) -> StatementType:
        sql_upper = sql.strip().upper()
        if sql_upper.startswith(('SELECT', 'WITH', 'EXECUTE BLOCK')):
            return StatementType.DQL
        if sql_upper.startswith(('INSERT', 'UPDATE', 'DELETE', 'MERGE', 'UPDATE OR INSERT')):
            return StatementType.DML
        if sql_upper.startswith(('EXECUTE', 'CALL')):
            return StatementType.DQL
        return StatementType.DDL

    def _build_query_result(self, cursor, data, duration):
        affected = getattr(cursor, "rowcount", 0)
        if affected < 0:
            if data:
                affected = len(data)
            else:
                affected = 0
        return QueryResult(
            data=data,
            affected_rows=affected,
            last_insert_id=getattr(cursor, "lastrowid", None),
            duration=duration,
        )

    async def execute(
        self,
        sql: str,
        params: Optional[Tuple] = None,
        *,
        options: Optional[ExecutionOptions] = None,
        **kwargs,
    ) -> QueryResult:
        """Execute a SQL statement asynchronously.

        Mirrors :meth:`FirebirdBackend.execute` by detecting the statement
        type when no explicit options are provided, so bare ``execute(sql)``
        calls treat SELECT/WITH as DQL and return result data.
        """
        if options is None:
            stmt_type = kwargs.get('stmt_type') or self._detect_statement_type(sql)
            column_adapters = kwargs.get('column_adapters')
            column_mapping = kwargs.get('column_mapping')
            process_result_set = kwargs.get('process_result_set')
            options = ExecutionOptions(
                stmt_type=stmt_type,
                column_adapters=column_adapters,
                column_mapping=column_mapping,
                process_result_set=process_result_set,
            )
        try:
            return await super().execute(sql, params, options=options)
        except Exception as e:
            if isinstance(e, exc.DatabaseError):
                raise
            await self._handle_error(e)

    # ------------------------------------------------------------------
    # High-level operations
    # ------------------------------------------------------------------

    async def bulk_insert(self, options) -> QueryResult:
        """Firebird does not support multi-row VALUES, so insert rows individually."""
        results = []
        affected = 0
        returning = options.returning_columns or []
        for row in options.rows:
            row_dict = dict(zip(options.columns, row)) if options.columns else {}
            if returning:
                res = await self.insert(options.table, values=row_dict, returning_columns=returning)
            else:
                res = await self.insert(options.table, values=row_dict)
            if res and res.data:
                results.append(res.data[0])
            affected += res.affected_rows if res else 1
        if returning:
            return QueryResult(data=results, affected_rows=affected)
        return QueryResult(data=[], affected_rows=affected)

    async def insert(self, table_name, values=None, returning_columns=None):
        if isinstance(table_name, InsertOptions):
            return await super().insert(table_name)
        options = InsertOptions(
            table=table_name,
            data=values or {},
            returning_columns=returning_columns,
        )
        return await super().insert(options)

    async def update(self, table_name, values=None, where_clause=None, returning_columns=None):
        if isinstance(table_name, UpdateOptions):
            return await super().update(table_name)
        values = values or {}
        all_params = list(values.values())
        if where_clause:
            where_sql, where_params = where_clause
            all_params.extend(where_params)
        set_clauses = []
        for col in values:
            set_clauses.append(
                f"{self.dialect.format_identifier(col)} = {self.dialect.get_parameter_placeholder()}"
            )
        where_sql = where_clause[0] if where_clause else "1=1"
        sql = (
            f"UPDATE {self.dialect.format_identifier(table_name)} "
            f"SET {', '.join(set_clauses)} WHERE {where_sql}"
        )
        if returning_columns:
            ret_str = ', '.join(self.dialect.format_identifier(c) for c in returning_columns)
            sql += f" RETURNING {ret_str}"
            return await self.execute(
                sql, tuple(all_params),
                options=ExecutionOptions(stmt_type=StatementType.DML, process_result_set=True),
            )
        return await self.execute(
            sql, tuple(all_params),
            options=ExecutionOptions(stmt_type=StatementType.DML),
        )

    async def delete(self, table_name, where_clause=None, returning_columns=None):
        if isinstance(table_name, DeleteOptions):
            return await super().delete(table_name)
        all_params = []
        sql = f"DELETE FROM {self.dialect.format_identifier(table_name)}"
        if where_clause:
            where_sql, where_params = where_clause
            sql += f" WHERE {where_sql}"
            all_params.extend(where_params)
        if returning_columns:
            ret_str = ', '.join(self.dialect.format_identifier(c) for c in returning_columns)
            sql += f" RETURNING {ret_str}"
            return await self.execute(
                sql, tuple(all_params) if all_params else None,
                options=ExecutionOptions(stmt_type=StatementType.DML, process_result_set=True),
            )
        return await self.execute(
            sql, tuple(all_params) if all_params else None,
            options=ExecutionOptions(stmt_type=StatementType.DML),
        )

    # ------------------------------------------------------------------
    # Transaction manager
    # ------------------------------------------------------------------

    @property
    def transaction_manager(self) -> AsyncFirebirdTransactionManager:
        return self._transaction_manager

    # ------------------------------------------------------------------
    # Introspector factory
    # ------------------------------------------------------------------

    def _create_introspector(self):
        from .introspection import AsyncFirebirdIntrospector
        from .introspection.executor import AsyncFirebirdIntrospectorExecutor
        return AsyncFirebirdIntrospector(self, AsyncFirebirdIntrospectorExecutor(self))

    # ------------------------------------------------------------------
    # Client library helper
    # ------------------------------------------------------------------

    def _ensure_client_library(self) -> None:
        import os
        lib_path = os.environ.get('FIREBIRD_CLIENT_LIBRARY')
        if lib_path:
            from pathlib import Path
            from firebird.driver.fbapi import load_api, has_api
            if not has_api():
                load_api(filename=Path(lib_path))

    # ------------------------------------------------------------------
    # Lifetime
    # ------------------------------------------------------------------

    def __del__(self):
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
