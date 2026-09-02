# src/rhosocial/activerecord/backend/impl/firebird/backend.py
"""Firebird synchronous backend implementation."""

from typing import Any, List, Optional, Tuple

from rhosocial.activerecord.backend.base import StorageBackend
from rhosocial.activerecord.backend.introspection.backend_mixin import IntrospectorBackendMixin
from rhosocial.activerecord.backend.result import QueryResult
from rhosocial.activerecord.backend.options import (
    ExecutionOptions, InsertOptions, UpdateOptions, DeleteOptions,
)
from rhosocial.activerecord.backend.schema import StatementType
from rhosocial.activerecord.backend import errors as exc

from .mixins import (
    FirebirdBackendMixin,
    FirebirdConcurrencyMixin,
    track_firebird_backend,
    track_firebird_connection,
    untrack_firebird_backend,
    untrack_firebird_connection,
)
from .transaction import FirebirdTransactionManager


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
            self._cursor.execute("SELECT 1 FROM RDB$DATABASE")
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

    def _handle_auto_commit(self) -> None:
        try:
            self._connection.commit()
        except Exception:
            pass

    def execute_many(self, sql: str, params_list: List[Tuple]) -> QueryResult:
        is_dml = sql.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'MERGE'))
        try:
            result = super().execute_many(sql, params_list)
            if result and result.affected_rows < 0 and len(params_list) > 0:
                result.affected_rows = len(params_list)
            if is_dml:
                self._handle_auto_commit_if_needed()
            return result
        except Exception as e:
            # Re-raise already-wrapped rhosocial errors unchanged; see execute().
            if isinstance(e, exc.DatabaseError):
                raise
            self._handle_error(e)

    def executescript(self, sql: str) -> QueryResult:
        cursor = self._get_cursor()
        try:
            cursor.execute(sql)
            result = QueryResult(affected_rows=cursor.rowcount or 0)
            self._handle_auto_commit_if_needed()
            return result
        except Exception as e:
            # Re-raise already-wrapped rhosocial errors unchanged; see execute().
            if isinstance(e, exc.DatabaseError):
                raise
            self._handle_error(e)

    def get_server_version(self) -> Tuple[int, int, int]:
        if not self._is_connected:
            self.connect()
        cursor = self._get_cursor()
        try:
            cursor.execute("SELECT RDB$GET_CONTEXT('SYSTEM', 'ENGINE_VERSION') FROM RDB$DATABASE")
            row = cursor.fetchone()
            if row and row[0]:
                version_str = str(row[0])
            else:
                cursor.execute("SELECT MON$VERSION FROM MON$DATABASE")
                row = cursor.fetchone()
                if row and row[0]:
                    version_str = str(row[0])
                else:
                    return (2, 5, 0)
        except Exception:
            try:
                cursor.execute("SELECT * FROM RDB$DATABASE")
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
            from .adapters import FirebirdBooleanAdapter
            bool_adapter = FirebirdBooleanAdapter(use_char=True)
            self.adapter_registry.register(bool_adapter, bool, bool, allow_override=True)
            self.adapter_registry.register(bool_adapter, bool, str, allow_override=True)

    def _create_introspector(self):
        from .introspection.introspector import SyncFirebirdIntrospector
        return SyncFirebirdIntrospector(self)

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
        from .explain.types import FirebirdExplainResult
        rows = result.data or []
        plan_text = " ".join(str(row[0]) for row in rows) if rows else ""
        return FirebirdExplainResult(plan_text=plan_text)

    def bulk_insert(self, options) -> QueryResult:
        """Firebird does not support multi-row VALUES, so insert rows individually."""
        results = []
        affected = 0
        returning = options.returning_columns or []
        for row in options.rows:
            row_dict = dict(zip(options.columns, row, strict=False)) if options.columns else {}
            if returning:
                res = self.insert(options.table, values=row_dict, returning_columns=returning)
            else:
                res = self.insert(options.table, values=row_dict)
            if res and res.data:
                results.append(res.data[0])
            affected += res.affected_rows if res else 1
        if returning:
            return QueryResult(data=results, affected_rows=affected)
        return QueryResult(data=[], affected_rows=affected)

    def insert(self, table, values=None, returning_columns=None):
        if isinstance(table, InsertOptions):
            return super().insert(table)
        options = InsertOptions(
            table=table,
            data=values or {},
            returning_columns=returning_columns,
        )
        return super().insert(options)

    def update(self, table, values=None, where_clause=None, returning_columns=None):
        if isinstance(table, UpdateOptions):
            return super().update(table)
        values = values or {}
        all_params = list(values.values())
        if where_clause:
            where_sql, where_params = where_clause
            all_params.extend(where_params)
        set_clauses = []
        for col in values:
            set_clauses.append(f"{self.dialect.format_identifier(col)} = {self.dialect.get_parameter_placeholder()}")
        where_sql = where_clause[0] if where_clause else "1=1"
        sql = f"UPDATE {self.dialect.format_identifier(table)} SET {', '.join(set_clauses)} WHERE {where_sql}"
        if returning_columns:
            ret_str = ', '.join(self.dialect.format_identifier(c) for c in returning_columns)
            sql += f" RETURNING {ret_str}"
            return self.execute(sql, tuple(all_params), options=ExecutionOptions(
                stmt_type=StatementType.DML, process_result_set=True))
        return self.execute(sql, tuple(all_params), options=ExecutionOptions(stmt_type=StatementType.DML))

    def delete(self, table, where_clause=None, returning_columns=None):
        if isinstance(table, DeleteOptions):
            return super().delete(table)
        all_params = []
        sql = f"DELETE FROM {self.dialect.format_identifier(table)}"
        if where_clause:
            where_sql, where_params = where_clause
            sql += f" WHERE {where_sql}"
            all_params.extend(where_params)
        if returning_columns:
            ret_str = ', '.join(self.dialect.format_identifier(c) for c in returning_columns)
            sql += f" RETURNING {ret_str}"
            return self.execute(sql, tuple(all_params) if all_params else None,
                                options=ExecutionOptions(stmt_type=StatementType.DML, process_result_set=True))
        return self.execute(sql, tuple(all_params) if all_params else None,
                            options=ExecutionOptions(stmt_type=StatementType.DML))

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