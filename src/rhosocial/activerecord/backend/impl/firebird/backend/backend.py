# src/rhosocial/activerecord/backend/impl/firebird/backend/backend.py
"""Firebird synchronous backend implementation."""

import logging
import time
from typing import Any, List, Optional, Tuple

from rhosocial.activerecord.backend.base import StorageBackend
from rhosocial.activerecord.backend.base.operations import execution_log_context
from rhosocial.activerecord.backend.introspection.backend_mixin import IntrospectorBackendMixin
from rhosocial.activerecord.backend.result import QueryResult
from rhosocial.activerecord.backend.options import (
    ExecutionOptions, InsertOptions, UpdateOptions, DeleteOptions,
    LogContext, derive_log_context,
)
from rhosocial.activerecord.backend.schema import StatementType
from rhosocial.activerecord.backend import errors as exc

from ..mixins import (
    FirebirdBackendMixin,
    FirebirdConcurrencyMixin,
    track_firebird_backend,
    track_firebird_connection,
    untrack_firebird_backend,
    untrack_firebird_connection,
)
from ..transaction import FirebirdTransactionManager
from ..query_nodes import (
    database_probe_sql,
    engine_version_sql,
    health_check_sql,
    mon_version_sql,
)


class FirebirdBackend(
    FirebirdBackendMixin,
    FirebirdConcurrencyMixin,
    IntrospectorBackendMixin,
    StorageBackend,
):
    """Firebird synchronous backend implementation.

    Uses `firebird-driver` (fdb/engine) for database connectivity.

    Connection parameters:
        host: Firebird server hostname (default: localhost)
        port: Firebird port (default: 3050)
        database: Database path or host:path connection string
        user/username: Database user name
        password: Database password
        role: SQL role name
        charset: Connection character set (default: UTF8)
        page_size: Database page size
        wire_compression: Enable wire compression
        use_unicode: Use Unicode strings (default: True)
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._connection = None
        self._cursor = None
        self._transaction_manager = FirebirdTransactionManager(self)
        self._is_connected = False
        self._register_firebird_adapters()

    def _ensure_client_library(self) -> None:
        import os
        lib_path = os.environ.get('FIREBIRD_CLIENT_LIBRARY')
        if lib_path:
            from pathlib import Path
            from firebird.driver.fbapi import load_api, has_api
            if not has_api():
                load_api(filename=Path(lib_path))

    def connect(self) -> None:
        self._ensure_client_library()
        import firebird.driver as fdb
        try:
            config = self.config
            if config.host and config.port and config.database:
                dsn = f"{config.host}/{config.port}:{config.database}"
            elif config.database:
                dsn = config.database
            else:
                raise exc.ConnectionError("No database specified in config")
            connect_params = {
                'database': dsn,
                'user': config.username or config.user,
                'password': config.password,
                'charset': config.charset,
            }
            if config.role:
                connect_params['role'] = config.role
            if config.timezone:
                connect_params['session_time_zone'] = config.timezone
            self._connection = fdb.connect(**connect_params)
            track_firebird_connection(self._connection)
            self._cursor = self._connection.cursor()
            self._is_connected = True
            self._fetch_concurrency_hint()
            track_firebird_backend(self)
        except Exception as e:
            self._handle_error(e)

    def disconnect(self) -> None:
        try:
            if self._cursor:
                try:
                    self._cursor.close()
                except Exception:
                    pass
                self._cursor = None
            if self._connection:
                untrack_firebird_connection(self._connection)
                try:
                    self._connection.close()
                except Exception:
                    pass
                self._connection = None
        finally:
            self._is_connected = False
            untrack_firebird_backend(self)

    def ping(self, reconnect: bool = True) -> bool:
        if not self._is_connected or self._connection is None:
            if reconnect:
                try:
                    self.connect()
                    return True
                except Exception:
                    return False
            return False
        try:
            probe, probe_params = health_check_sql(self.dialect)
            self._cursor.execute(probe, probe_params or None)
            self._cursor.fetchone()
            return True
        except Exception:
            if reconnect:
                try:
                    self.disconnect()
                    self.connect()
                    return True
                except Exception:
                    pass
            return False

    def _get_cursor(self):
        if not self._is_connected or self._connection is None:
            raise exc.ConnectionError("Not connected to Firebird database")
        if self._cursor is None:
            self._cursor = self._connection.cursor()
        return self._cursor

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

    def execute(
        self,
        sql: str,
        params: Optional[Tuple] = None,
        *,
        options: Optional[ExecutionOptions] = None,
        **kwargs,
    ) -> QueryResult:
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
            return super().execute(sql, params, options=options)
        except Exception as e:
            # A failed statement leaves the cursor in an errored state with an
            # active firebird Statement attached. Closing it now prevents that
            # statement from being garbage-collected later (which, under the
            # firebird-driver 2.0.x, aborts the process when the connection has
            # already been closed and GC runs in a worker thread).
            try:
                if self._cursor is not None:
                    self._cursor.close()
            except Exception:
                pass
            self._cursor = None
            # If the upstream execute() already wrapped the original driver
            # error into a rhosocial ActiveRecord error (IntegrityError,
            # ConnectionError, etc.) via _handle_execution_error, re-raise it
            # unchanged. Otherwise, treat the exception as a raw driver error
            # and dispatch through _handle_error for proper classification.
            if isinstance(e, exc.DatabaseError):
                raise
            self._handle_error(e)
            # _handle_error() is required to raise. Keep a defensive fallback so
            # a handler that returns cannot turn a failed execute into success.
            raise exc.DatabaseError(str(e)) from e

    def _handle_auto_commit(self) -> None:
        """Commit the connection's active transaction.

        The result is built just before this call, so a failed commit must not
        leave the caller with a "successful" result: the failure surfaces as
        :class:`TransactionError` carrying the driver exception.

        ``Connection.commit()`` goes through firebird-driver's main transaction
        manager, which has nothing to commit before the first statement starts
        a transaction. That state is not a commit failure, so it is skipped.
        """
        connection = self._connection
        if connection is None:
            return
        main_transaction = getattr(connection, "main_transaction", None)
        is_active = getattr(main_transaction, "is_active", None)
        if callable(is_active) and not is_active():
            return
        try:
            connection.commit()
        except Exception as error:
            raise exc.TransactionError("Auto-commit failed") from error

    def execute_many(
        self,
        sql: str,
        params_list: List[Tuple],
        *,
        options: Optional[ExecutionOptions] = None,
    ) -> QueryResult:
        """Execute the same statement once per parameter set.

        The caller's ``options`` - including its log context - is forwarded so
        the core batch logging stays the single owner of SQL/parameter records.
        The core pipeline owns auto-commit for the batch; committing here again
        would commit the same transaction twice.
        """
        try:
            result = super().execute_many(sql, params_list, options=options)
            if result and result.affected_rows < 0 and len(params_list) > 0:
                result.affected_rows = len(params_list)
            return result
        except Exception as e:
            # Re-raise already-wrapped rhosocial errors unchanged; see execute().
            if isinstance(e, exc.DatabaseError):
                raise
            self._handle_error(e)
            # Defensive contract: a handler that returns must not swallow the
            # batch failure.
            raise exc.DatabaseError(str(e)) from e

    def executescript(self, sql: str) -> QueryResult:
        """Execute a multi-statement SQL script.

        Scripts bypass the core ``execute`` pipeline, so the summary is emitted
        here; it carries no SQL text or parameter values.
        """
        start_time = time.perf_counter()
        self.log(logging.DEBUG, "Executing SQL script.")
        cursor = self._get_cursor()
        try:
            cursor.execute(sql)
            result = QueryResult(affected_rows=cursor.rowcount or 0)
            duration = time.perf_counter() - start_time
            self.log(logging.INFO, f"SQL script executed successfully, duration={duration:.3f}s")
            self._handle_auto_commit_if_needed()
            return result
        except Exception as e:
            # Re-raise already-wrapped rhosocial errors unchanged; see execute().
            if isinstance(e, exc.DatabaseError):
                raise
            self.log(logging.DEBUG, f"Error executing SQL script, exception will be re-raised: {e}")
            self._handle_error(e)
            raise exc.DatabaseError(str(e)) from e

    def get_server_version(self) -> Tuple[int, int, int]:
        if not self._is_connected:
            self.connect()
        cursor = self._get_cursor()
        try:
            context_sql, context_params = engine_version_sql(self.dialect)
            cursor.execute(context_sql, context_params or None)
            row = cursor.fetchone()
            if row and row[0]:
                version_str = str(row[0])
            else:
                mon_sql, mon_params = mon_version_sql(self.dialect)
                cursor.execute(mon_sql, mon_params or None)
                row = cursor.fetchone()
                if row and row[0]:
                    version_str = str(row[0])
                else:
                    return (2, 5, 0)
        except Exception:
            try:
                probe_sql, probe_params = database_probe_sql(self.dialect)
                cursor.execute(probe_sql, probe_params or None)
                version_str = str(cursor.description[0][0]) if cursor.description else "2.5.0"
            except Exception:
                return (2, 5, 0)
        import re
        match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_str)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return (2, 5, 0)

    def introspect_and_adapt(self) -> None:
        if not self._is_connected:
            self.connect()
        version = self.get_server_version()
        self.dialect.version = version
        if hasattr(self.config, 'version') and self.config.version is None:
            self.config.version = version
        if version < (3, 0, 0):
            from ..adapters import FirebirdBooleanAdapter
            bool_adapter = FirebirdBooleanAdapter(use_char=True)
            self.adapter_registry.register(bool_adapter, bool, bool, allow_override=True)
            self.adapter_registry.register(bool_adapter, bool, str, allow_override=True)

    def _create_introspector(self):
        from ..introspection.introspector import FirebirdIntrospector
        return FirebirdIntrospector(self)

    def _process_result_set(self, cursor, is_select, column_adapters=None, column_mapping=None):
        if not is_select:
            return None
        try:
            rows = cursor.fetchall()
            if not rows:
                return []
            # Firebird returns uppercase column names; lowercase for case-insensitive matching
            column_names = [desc[0].strip('"').lower() for desc in cursor.description]
            char_columns = self._char_columns_from_cursor(cursor)
            final_results = []
            adapters = column_adapters or {}
            mapping = column_mapping or {}
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

    @staticmethod
    def _char_columns_from_cursor(cursor) -> set:
        """Detect CHAR-type columns using the firebird-driver statement metadata.

        The public ``cursor.description`` reports both CHAR and VARCHAR as ``str``
        and their declared sizes, so it cannot distinguish them. Firebird pads
        CHAR values with trailing spaces on read, so only CHAR columns need the
        padding stripped (VARCHAR/BLOB TEXT must round-trip trailing whitespace).
        The datatype codes come from the driver's message metadata descriptor.
        """
        try:
            stmt = getattr(cursor, "_stmt", None)
            if stmt is None:
                return set()
            out_desc = getattr(stmt, "_out_desc", None)
            if not out_desc:
                return set()
            names = getattr(stmt, "_names", None)
            return {
                (names[i].lower() if names and i < len(names) else str(meta.field).lower())
                for i, meta in enumerate(out_desc)
                if getattr(meta, "datatype", None) == 452  # SQLDataType.TEXT == CHAR
            }
        except Exception:
            return set()

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

    def _parse_explain_result(self, result: QueryResult) -> Any:
        from ..explain.types import FirebirdExplainResult
        rows = result.data or []
        plan_text = " ".join(str(row[0]) for row in rows) if rows else ""
        return FirebirdExplainResult(plan_text=plan_text)

    def bulk_insert(self, options) -> QueryResult:
        """Firebird does not support multi-row VALUES, so insert rows individually."""
        results = []
        affected = 0
        returning = options.returning_columns or []
        log_context = execution_log_context(options, "bulk_insert")
        for row in options.rows:
            row_dict = dict(zip(options.columns, row, strict=False)) if options.columns else {}
            if returning:
                res = self.insert(
                    options.table,
                    values=row_dict,
                    returning_columns=returning,
                    log_context=log_context,
                )
            else:
                res = self.insert(options.table, values=row_dict, log_context=log_context)
            if res and res.data:
                results.append(res.data[0])
            affected += res.affected_rows if res else 1
        if returning:
            return QueryResult(data=results, affected_rows=affected)
        return QueryResult(data=[], affected_rows=affected)

    def insert(
        self,
        table_name,
        values=None,
        returning_columns=None,
        log_context: Optional[LogContext] = None,
    ):
        if isinstance(table_name, InsertOptions):
            if log_context is not None and table_name.log_context is None:
                table_name.log_context = log_context
            return super().insert(table_name)
        options = InsertOptions(
            table=table_name,
            data=values or {},
            returning_columns=returning_columns,
            log_context=log_context,
        )
        options.log_context = execution_log_context(options, "insert")
        return super().insert(options)

    def update(
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
            return super().update(table_name)
        values = values or {}
        all_params = list(values.values())
        if where_clause:
            where_sql, where_params = where_clause
            all_params.extend(where_params)
        set_clauses = []
        for col in values:
            set_clauses.append(f"{self.dialect.format_identifier(col)} = {self.dialect.get_parameter_placeholder()}")
        where_sql = where_clause[0] if where_clause else "1=1"
        # The target is a relation reference rendered through the dialect's
        # schema-object layer, so a caller that hands over a qualified
        # reference is told Firebird cannot express it instead of having the
        # qualification dropped here.
        target_sql = self.dialect.format_table_reference(table_name)
        sql = f"UPDATE {target_sql} SET {', '.join(set_clauses)} WHERE {where_sql}"
        # This raw-SQL path has no *Options object, so the log context is built
        # from the operation's own identity rather than execution_log_context().
        context = derive_log_context(log_context, operation="update", object_name=table_name)
        if returning_columns:
            ret_str = ', '.join(self.dialect.format_identifier(c) for c in returning_columns)
            sql += f" RETURNING {ret_str}"
            return self.execute(sql, tuple(all_params), options=ExecutionOptions(
                stmt_type=StatementType.DML, process_result_set=True, log_context=context))
        return self.execute(sql, tuple(all_params), options=ExecutionOptions(
            stmt_type=StatementType.DML, log_context=context))

    def delete(
        self,
        table_name,
        where_clause=None,
        returning_columns=None,
        log_context: Optional[LogContext] = None,
    ):
        if isinstance(table_name, DeleteOptions):
            if log_context is not None and table_name.log_context is None:
                table_name.log_context = log_context
            return super().delete(table_name)
        all_params = []
        target_sql = self.dialect.format_table_reference(table_name)
        sql = f"DELETE FROM {target_sql}"
        if where_clause:
            where_sql, where_params = where_clause
            sql += f" WHERE {where_sql}"
            all_params.extend(where_params)
        # Same as update(): this raw-SQL path has no *Options object.
        context = derive_log_context(log_context, operation="delete", object_name=table_name)
        if returning_columns:
            ret_str = ', '.join(self.dialect.format_identifier(c) for c in returning_columns)
            sql += f" RETURNING {ret_str}"
            return self.execute(sql, tuple(all_params) if all_params else None,
                                options=ExecutionOptions(
                                    stmt_type=StatementType.DML,
                                    process_result_set=True,
                                    log_context=context))
        return self.execute(sql, tuple(all_params) if all_params else None,
                            options=ExecutionOptions(
                                stmt_type=StatementType.DML, log_context=context))

    @property
    def transaction_manager(self) -> FirebirdTransactionManager:
        return self._transaction_manager

    def __del__(self):
        # Do NOT call disconnect() here. firebird-driver objects must not be
        # closed from the garbage collector: libfbclient is not thread-safe,
        # and closing from __del__ during a GC pass crashes the process with a
        # segmentation fault. Backends (and their Connection/Cursor) are kept
        # strongly referenced via track_firebird_backend() until disconnect()
        # is called explicitly, so this only runs for backends whose resources
        # were already released.
        pass