# src/rhosocial/activerecord/backend/impl/firebird/backend/async_backend.py
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
import threading
import time
from concurrent.futures import Executor
from typing import Optional, Tuple

from rhosocial.activerecord.backend.base import AsyncStorageBackend
from rhosocial.activerecord.backend.base.operations import execution_log_context
from rhosocial.activerecord.backend import errors as exc
from rhosocial.activerecord.backend.introspection.backend_mixin import IntrospectorBackendMixin
from rhosocial.activerecord.backend.options import (
    ExecutionOptions, InsertOptions, UpdateOptions, DeleteOptions,
    LogContext, derive_log_context,
)
from rhosocial.activerecord.backend.result import QueryResult
from rhosocial.activerecord.backend.schema import StatementType

from ..config import FirebirdConnectionConfig
from ..mixins import (
    FirebirdBackendMixin,
    track_firebird_backend,
    track_firebird_connection,
    untrack_firebird_backend,
    untrack_firebird_connection,
)
from ..async_transaction import AsyncFirebirdTransactionManager
from ..query_nodes import (
    database_probe_sql,
    engine_version_sql,
    health_check_sql,
    mon_version_sql,
)


_shared_executor_instance = None
_shared_executor_lock = None


def _shared_firebird_executor() -> "Executor":
    """Return a process-wide single-worker executor for fdb operations.

    Every ``AsyncFirebirdBackend`` that does not receive an explicit
    executor shares this one worker thread. This keeps the number of
    live threads constant (one) no matter how many backend instances the
    suite creates and guarantees that all firebird-driver calls are
    serialized process-wide, which avoids the libfbclient crashes seen
    when many worker threads coexist.
    """
    global _shared_executor_instance, _shared_executor_lock
    if _shared_executor_instance is None:
        from concurrent.futures import ThreadPoolExecutor
        if _shared_executor_lock is None:
            _shared_executor_lock = threading.Lock()
        with _shared_executor_lock:
            if _shared_executor_instance is None:
                _shared_executor_instance = ThreadPoolExecutor(max_workers=1)
    return _shared_executor_instance


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
        if executor is not None:
            self._executor = executor
        else:
            # firebird-driver / libfbclient are not thread-safe, and the
            # crash surfaces both during concurrent execute and during GC of
            # fdb objects while worker threads exist. Serialize every fdb
            # operation through a single shared worker thread for the whole
            # process so that (a) no two operations run concurrently and
            # (b) the number of live threads stays constant regardless of how
            # many backend instances the test suite creates.
            self._executor = _shared_firebird_executor()

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
            track_firebird_connection(self._connection)
            self._cursor = self._connection.cursor()
            self._is_connected = True
            self.log(logging.INFO, "Connected to Firebird (async)")
            track_firebird_backend(self)
        except Exception as e:
            if isinstance(e, exc.DatabaseError):
                raise
            await self._handle_error(e)

    async def disconnect(self) -> None:
        """Close the connection to the Firebird database."""
        if self._connection:
            try:
                loop = asyncio.get_event_loop()
                if self._cursor:
                    await loop.run_in_executor(self._executor, self._cursor.close)
                    self._cursor = None
                untrack_firebird_connection(self._connection)
                await loop.run_in_executor(self._executor, self._connection.close)
                self.log(logging.INFO, "Disconnected from Firebird (async)")
            except Exception as e:
                self.log(logging.WARNING, f"Error disconnecting from Firebird: {e}")
            finally:
                self._connection = None
                self._is_connected = False
                untrack_firebird_backend(self)

    async def ping(self, reconnect: bool = True) -> bool:
        """Check if the connection is alive."""
        if not self._is_connected or self._connection is None:
            if reconnect:
                await self.connect()
                return True
            return False
        try:
            loop = asyncio.get_event_loop()
            cursor = self._cursor
            temp_cursor = cursor is None
            if cursor is None:
                cursor = self._connection.cursor()
            probe, probe_params = health_check_sql(self.dialect)
            try:
                await loop.run_in_executor(
                    self._executor,
                    lambda: cursor.execute(probe, probe_params or None),
                )
                await loop.run_in_executor(self._executor, cursor.fetchone)
                return True
            finally:
                if temp_cursor:
                    try:
                        await loop.run_in_executor(self._executor, cursor.close)
                    except Exception:
                        pass
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
        context_sql, context_params = engine_version_sql(self.dialect)
        try:
            await loop.run_in_executor(
                self._executor,
                lambda: cursor.execute(context_sql, context_params or None),
            )
            row = await loop.run_in_executor(self._executor, cursor.fetchone)
            if row and row[0]:
                version_str = str(row[0])
            else:
                mon_sql, mon_params = mon_version_sql(self.dialect)
                await loop.run_in_executor(
                    self._executor,
                    lambda: cursor.execute(mon_sql, mon_params or None),
                )
                row = await loop.run_in_executor(self._executor, cursor.fetchone)
                if row and row[0]:
                    version_str = str(row[0])
                else:
                    return (2, 5, 0)
        except Exception:
            probe_sql, probe_params = database_probe_sql(self.dialect)
            try:
                await loop.run_in_executor(
                    self._executor,
                    lambda: cursor.execute(probe_sql, probe_params or None),
                )
                desc = cursor.description
                version_str = str(desc[0][0]) if desc else "2.5.0"
            except Exception:
                return (2, 5, 0)
        finally:
            if cursor is not self._cursor:
                try:
                    await loop.run_in_executor(self._executor, cursor.close)
                except Exception:
                    pass
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
            from ..adapters import FirebirdBooleanAdapter
            bool_adapter = FirebirdBooleanAdapter(use_char=True)
            self.adapter_registry.register(bool_adapter, bool, bool, allow_override=True)
            self.adapter_registry.register(bool_adapter, bool, str, allow_override=True)

    # ------------------------------------------------------------------
    # Error handling — FirebirdBackendMixin._handle_error is sync and
    # non-I/O, so we call it directly from the async wrapper.
    # ------------------------------------------------------------------

    async def _handle_error(self, error: Exception) -> None:
        """Handle and classify a Firebird error."""
        # A failed statement leaves the cursor with an attached firebird
        # Statement; closing it here avoids a GC-time abort in a worker thread
        # once the connection is gone (firebird-driver 2.0.x behaviour).
        await self._close_cursor_quietly()
        FirebirdBackendMixin._handle_error(self, error)

    async def _close_cursor_quietly(self) -> None:
        """Close the shared cursor without letting a close failure mask a cause.

        The original exception is already propagating when this runs, so a
        close failure is logged and discarded rather than raised.
        """
        cursor = self._cursor
        self._cursor = None
        if cursor is None:
            return
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(self._executor, cursor.close)
        except Exception as error:
            self.log(
                logging.DEBUG,
                f"Error closing cursor after failed execution, ignored: {error}",
            )

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
                    row_dict = dict(zip(column_names, row, strict=False))
                    adapted_row = self.adapt_row_types(row_dict, adapters)
                    final_row = self.remap_row_columns(adapted_row, mapping)
                    if char_columns:
                        for col in char_columns:
                            if isinstance(final_row.get(col), str):
                                final_row[col] = final_row[col].rstrip(' ')
                    final_results.append(final_row)
                return final_results
            except Exception as e:
                # The failure is re-raised and logged by the core execute pipeline;
                # a second ERROR record here would duplicate it.
                self.log(
                    logging.DEBUG,
                    f"Error processing result set, exception will be re-raised: {e}",
                )
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
        """Commit the connection's active transaction in the executor.

        Mirrors the synchronous contract: a failed commit raises
        :class:`TransactionError` from the driver exception, so the caller
        never receives a result whose data was not committed. A connection
        without an active transaction has nothing to commit.
        """
        connection = self._connection
        if connection is None:
            return
        main_transaction = getattr(connection, "main_transaction", None)
        is_active = getattr(main_transaction, "is_active", None)
        if callable(is_active) and not is_active():
            return
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(self._executor, connection.commit)
        except Exception as error:
            raise exc.TransactionError("Auto-commit failed") from error

    async def executescript(self, sql_script: str) -> None:
        """Execute a multi-statement SQL script asynchronously.

        Mirrors the synchronous :meth:`FirebirdBackend.executescript` by
        running the underlying firebird-driver cursor in a thread pool so
        sync and async expose the same API surface.  The summary carries
        no SQL text or parameter values.
        """
        start_time = time.perf_counter()
        self.log(logging.DEBUG, "Executing SQL script asynchronously.")
        cursor = None
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
                await loop.run_in_executor(self._executor, cursor.close)
            except Exception as error:
                # Closing after a successful script is cleanup: a close failure
                # must not turn success into an error.
                self.log(logging.DEBUG, f"Error closing script cursor, ignored: {error}")
        except Exception as e:
            if cursor is not None:
                try:
                    await loop.run_in_executor(self._executor, cursor.close)
                except Exception as error:
                    # The script failure below is the cause the caller must see.
                    self.log(logging.DEBUG, f"Error closing failed script cursor, ignored: {error}")
            if isinstance(e, exc.DatabaseError):
                raise
            # The exception is re-raised by _handle_error; a second ERROR
            # record would duplicate the application's own traceback.
            self.log(logging.DEBUG, f"Error executing async SQL script, will be re-raised: {e}")
            await self._handle_error(e)
            # Defensive contract: a handler that returns must not swallow the
            # script failure.
            raise exc.DatabaseError(str(e)) from e

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
            # Mirror the synchronous backend: the errored cursor is closed
            # before the failure propagates, and its close failure must not
            # replace the original exception.
            await self._close_cursor_quietly()
            if isinstance(e, exc.DatabaseError):
                raise
            await self._handle_error(e)
            # Defensive contract: a handler that returns must not turn a
            # failed execute into a None result.
            raise exc.DatabaseError(str(e)) from e

    # ------------------------------------------------------------------
    # High-level operations
    # ------------------------------------------------------------------

    async def bulk_insert(self, options) -> QueryResult:
        """Firebird does not support multi-row VALUES, so insert rows individually."""
        results = []
        affected = 0
        returning = options.returning_columns or []
        log_context = execution_log_context(options, "bulk_insert")
        for row in options.rows:
            row_dict = dict(zip(options.columns, row, strict=False)) if options.columns else {}
            if returning:
                res = await self.insert(
                    options.table,
                    values=row_dict,
                    returning_columns=returning,
                    log_context=log_context,
                )
            else:
                res = await self.insert(options.table, values=row_dict, log_context=log_context)
            if res and res.data:
                results.append(res.data[0])
            affected += res.affected_rows if res else 1
        if returning:
            return QueryResult(data=results, affected_rows=affected)
        return QueryResult(data=[], affected_rows=affected)

    async def insert(
        self,
        table_name,
        values=None,
        returning_columns=None,
        log_context: Optional[LogContext] = None,
    ):
        if isinstance(table_name, InsertOptions):
            if log_context is not None and table_name.log_context is None:
                table_name.log_context = log_context
            return await super().insert(table_name)
        options = InsertOptions(
            table=table_name,
            data=values or {},
            returning_columns=returning_columns,
            log_context=log_context,
        )
        options.log_context = execution_log_context(options, "insert")
        return await super().insert(options)

    async def update(
        self,
        table_name,
        values=None,
        where_clause=None,
        returning_columns=None,
        log_context: Optional[LogContext] = None,
    ):
        if isinstance(table_name, UpdateOptions):
            if log_context is not None and table_name.log_context is None:
                table_name.log_context = log_context
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
        # Mirror of the sync path: the target is a relation reference rendered
        # through the dialect's schema-object layer, never a bare identifier.
        target_sql = self.dialect.format_table_reference(table_name)
        sql = (
            f"UPDATE {target_sql} "
            f"SET {', '.join(set_clauses)} WHERE {where_sql}"
        )
        # The raw-SQL path has no *Options object, so the log context is built
        # from the operation's own identity.
        context = derive_log_context(log_context, operation="update", object_name=table_name)
        if returning_columns:
            ret_str = ', '.join(self.dialect.format_identifier(c) for c in returning_columns)
            sql += f" RETURNING {ret_str}"
            return await self.execute(
                sql, tuple(all_params),
                options=ExecutionOptions(
                    stmt_type=StatementType.DML,
                    process_result_set=True,
                    log_context=context,
                ),
            )
        return await self.execute(
            sql, tuple(all_params),
            options=ExecutionOptions(stmt_type=StatementType.DML, log_context=context),
        )

    async def delete(
        self,
        table_name,
        where_clause=None,
        returning_columns=None,
        log_context: Optional[LogContext] = None,
    ):
        if isinstance(table_name, DeleteOptions):
            if log_context is not None and table_name.log_context is None:
                table_name.log_context = log_context
            return await super().delete(table_name)
        all_params = []
        target_sql = self.dialect.format_table_reference(table_name)
        sql = f"DELETE FROM {target_sql}"
        if where_clause:
            where_sql, where_params = where_clause
            sql += f" WHERE {where_sql}"
            all_params.extend(where_params)
        # Same as update(): the raw-SQL path has no *Options object.
        context = derive_log_context(log_context, operation="delete", object_name=table_name)
        if returning_columns:
            ret_str = ', '.join(self.dialect.format_identifier(c) for c in returning_columns)
            sql += f" RETURNING {ret_str}"
            return await self.execute(
                sql, tuple(all_params) if all_params else None,
                options=ExecutionOptions(
                    stmt_type=StatementType.DML,
                    process_result_set=True,
                    log_context=context,
                ),
            )
        return await self.execute(
            sql, tuple(all_params) if all_params else None,
            options=ExecutionOptions(stmt_type=StatementType.DML, log_context=context),
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
        from ..introspection import AsyncFirebirdIntrospector
        from ..introspection.executor import AsyncFirebirdIntrospectorExecutor
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
        # Do NOT close the firebird-driver connection here. libfbclient is not
        # thread-safe, and closing from __del__ during a GC pass crashes the
        # process with a segmentation fault. Backends are kept strongly
        # referenced via track_firebird_backend() until disconnect() is called
        # explicitly, so this only runs for backends whose resources were
        # already released.
        pass
