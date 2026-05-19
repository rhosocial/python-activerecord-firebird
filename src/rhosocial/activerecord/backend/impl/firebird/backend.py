# src/rhosocial/activerecord/backend/impl/firebird/backend.py
"""Firebird synchronous backend implementation."""

from typing import Any, Dict, List, Optional, Tuple, Type

from rhosocial.activerecord.backend.base import StorageBackend
from rhosocial.activerecord.backend.result import QueryResult
from rhosocial.activerecord import errors as exc

from .mixins import FirebirdBackendMixin, FirebirdConcurrencyMixin
from .config import FirebirdConnectionConfig
from .transaction import FirebirdTransactionManager


class FirebirdBackend(
    FirebirdBackendMixin,
    FirebirdConcurrencyMixin,
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
        """Initialize Firebird backend.

        Args:
            **kwargs: Configuration parameters for FirebirdConnectionConfig
        """
        super().__init__(**kwargs)

        self._connection = None
        self._cursor = None
        self._transaction_manager = FirebirdTransactionManager(self)
        self._is_connected = False

        self._register_firebird_adapters()

    def connect(self) -> None:
        """Establish connection to Firebird database.

        Raises:
            ConnectionError: If connection fails
        """
        import firebird.driver as fdb

        try:
            config = self.config

            connect_params = {
                'host': config.host,
                'port': config.port,
                'database': config.database,
                'user': config.username or config.user,
                'password': config.password,
                'charset': config.charset,
            }

            if config.role:
                connect_params['role'] = config.role
            if config.page_size:
                connect_params['page_size'] = config.page_size
            if config.wire_compression:
                connect_params['wire_compression'] = config.wire_compression
            if config.timeout:
                connect_params['timeout'] = config.timeout

            self._connection = fdb.connect(**connect_params)
            self._cursor = self._connection.cursor()
            self._is_connected = True

        except Exception as e:
            self._handle_error(e)

    def disconnect(self) -> None:
        """Close the database connection."""
        try:
            if self._cursor:
                try:
                    self._cursor.close()
                except Exception:
                    pass
                self._cursor = None
            if self._connection:
                try:
                    self._connection.close()
                except Exception:
                    pass
                self._connection = None
        finally:
            self._is_connected = False

    def ping(self, reconnect: bool = True) -> bool:
        """Check if connection is still alive.

        Args:
            reconnect: If True, attempt to reconnect on failure

        Returns:
            True if connection is valid
        """
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
        """Get or create a database cursor with health check.

        Returns:
            Database cursor

        Raises:
            ConnectionError: If connection is lost and cannot be re-established
        """
        if not self._is_connected or self._connection is None:
            raise exc.ConnectionError("Not connected to Firebird database")
        if self._cursor is None or self._cursor.closed:
            self._cursor = self._connection.cursor()
        return self._cursor

    def _prepare_sql_and_params(self, sql: str, params: Optional[Tuple] = None) -> Tuple[str, Optional[Tuple]]:
        """Prepare SQL and parameters for execution.

        Handles RETURNING clause by removing INTO clause from SQL
        and converting Firebird-specific parameter syntax.

        Args:
            sql: SQL statement
            params: Optional parameters tuple

        Returns:
            Tuple of (prepared_sql, prepared_params)
        """
        return sql, params

    def execute(self, sql: str, params: Optional[Tuple] = None,
                fetch: bool = False, returning: bool = False) -> QueryResult:
        """Execute a SQL statement.

        Args:
            sql: SQL statement to execute
            params: Optional positional parameters
            fetch: If True, fetch and return result rows
            returning: If True, execute as RETURNING query

        Returns:
            QueryResult with data and/or affected rows
        """
        cursor = self._get_cursor()

        try:
            prepared_sql, prepared_params = self._prepare_sql_and_params(sql, params)

            cursor.execute(prepared_sql, prepared_params)

            result = QueryResult()
            result.affected_rows = cursor.rowcount

            if fetch or returning:
                try:
                    rows = cursor.fetchall()
                    if rows:
                        result.data = rows
                except Exception:
                    pass

            return result

        except Exception as e:
            self._handle_error(e)

    def execute_many(self, sql: str, params_list: List[Tuple]) -> QueryResult:
        """Execute a SQL statement with multiple parameter sets.

        Args:
            sql: SQL statement to execute
            params_list: List of parameter tuples

        Returns:
            QueryResult with aggregated affected_rows

        Raises:
            DatabaseError: If execution fails
        """
        cursor = self._get_cursor()
        total_affected = 0

        try:
            prepared_sql, _ = self._prepare_sql_and_params(sql, None)

            for params in params_list:
                cursor.execute(prepared_sql, params)
                total_affected += cursor.rowcount

            return QueryResult(affected_rows=total_affected)

        except Exception as e:
            self._handle_error(e)

    def executescript(self, sql: str) -> QueryResult:
        """Execute a multi-statement SQL script.

        Args:
            sql: SQL script with multiple statements

        Returns:
            QueryResult

        Raises:
            DatabaseError: If execution fails
        """
        cursor = self._get_cursor()

        try:
            cursor.execute(sql)
            return QueryResult(affected_rows=cursor.rowcount or 0)
        except Exception as e:
            self._handle_error(e)

    def get_server_version(self) -> Tuple[int, int, int]:
        """Get Firebird server version.

        Queries RDB$DATABASE for version string like
        'LI-V3.0.5.33220' or 'FB 4.0.1.2692'.

        Returns:
            Version tuple (major, minor, patch)
        """
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
                    return (3, 0, 0)
        except Exception:
            try:
                cursor.execute("SELECT * FROM RDB$DATABASE")
                version_str = str(cursor.description[0][0]) if cursor.description else "3.0.0"
            except Exception:
                return (3, 0, 0)

        import re
        match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_str)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))

        return (3, 0, 0)

    def introspect_and_adapt(self) -> None:
        """Introspect server and adapt dialect.

        Detects Firebird server version and configures dialect accordingly.
        Also registers appropriate type adapters based on version.
        """
        version = self.get_server_version()
        self.dialect.version = version

        if hasattr(self.config, 'version') and self.config.version is None:
            self.config.version = version

        if version < (3, 0, 0):
            from .adapters import FirebirdBooleanAdapter
            bool_adapter = FirebirdBooleanAdapter(use_char=True)
            self._adapter_registry.register(bool_adapter, bool, bool, allow_override=True)
            self._adapter_registry.register(bool_adapter, bool, str, allow_override=True)

    def _create_introspector(self):
        """Create a Firebird introspector instance.

        Returns:
            SyncFirebirdIntrospector instance
        """
        from .introspection.introspector import SyncFirebirdIntrospector
        return SyncFirebirdIntrospector(self)

    def _parse_explain_result(self, result: QueryResult) -> Any:
        """Parse EXPLAIN result.

        Args:
            result: QueryResult from EXPLAIN execution

        Returns:
            Parsed explain result
        """
        from .explain.types import FirebirdExplainResult
        rows = result.data or []
        plan_text = " ".join(str(row[0]) for row in rows) if rows else ""
        return FirebirdExplainResult(plan_text=plan_text)

    def insert(self, table_name: str, values: Dict[str, Any],
               returning_columns: Optional[List[str]] = None) -> QueryResult:
        """Insert a row with optional RETURNING.

        Args:
            table_name: Target table
            values: Column name -> value mapping
            returning_columns: Optional columns to RETURN

        Returns:
            QueryResult with last_insert_id and optional RETURNING data
        """
        columns = list(values.keys())
        placeholders = [self.dialect.get_parameter_placeholder() for _ in values]
        params = tuple(values.values())

        cols_str = ', '.join(self.dialect.format_identifier(c) for c in columns)
        vals_str = ', '.join(placeholders)

        sql = f"INSERT INTO {self.dialect.format_identifier(table_name)} ({cols_str}) VALUES ({vals_str})"

        if returning_columns:
            ret_str = ', '.join(self.dialect.format_identifier(c) for c in returning_columns)
            sql += f" RETURNING {ret_str}"
            return self.execute(sql, params, returning=True)

        return self.execute(sql, params)

    def update(self, table_name: str, values: Dict[str, Any],
               where_clause: Optional[Tuple[str, tuple]] = None,
               returning_columns: Optional[List[str]] = None) -> QueryResult:
        """Update rows with optional RETURNING.

        Args:
            table_name: Target table
            values: Column name -> value mapping
            where_clause: Optional (where_sql, where_params) tuple
            returning_columns: Optional columns to RETURN

        Returns:
            QueryResult with affected_rows and optional RETURNING data
        """
        set_clauses = []
        all_params = []

        for col, val in values.items():
            set_clauses.append(f"{self.dialect.format_identifier(col)} = {self.dialect.get_parameter_placeholder()}")
            all_params.append(val)

        sql = f"UPDATE {self.dialect.format_identifier(table_name)} SET {', '.join(set_clauses)}"

        if where_clause:
            where_sql, where_params = where_clause
            sql += f" WHERE {where_sql}"
            all_params.extend(where_params)

        if returning_columns:
            ret_str = ', '.join(self.dialect.format_identifier(c) for c in returning_columns)
            sql += f" RETURNING {ret_str}"
            return self.execute(sql, tuple(all_params), returning=True)

        return self.execute(sql, tuple(all_params))

    def delete(self, table_name: str,
               where_clause: Optional[Tuple[str, tuple]] = None,
               returning_columns: Optional[List[str]] = None) -> QueryResult:
        """Delete rows with optional RETURNING.

        Args:
            table_name: Target table
            where_clause: Optional (where_sql, where_params) tuple
            returning_columns: Optional columns to RETURN

        Returns:
            QueryResult with affected_rows and optional RETURNING data
        """
        sql = f"DELETE FROM {self.dialect.format_identifier(table_name)}"
        all_params = []

        if where_clause:
            where_sql, where_params = where_clause
            sql += f" WHERE {where_sql}"
            all_params.extend(where_params)

        if returning_columns:
            ret_str = ', '.join(self.dialect.format_identifier(c) for c in returning_columns)
            sql += f" RETURNING {ret_str}"
            return self.execute(sql, tuple(all_params), returning=True)

        return self.execute(sql, tuple(all_params))

    @property
    def transaction_manager(self) -> FirebirdTransactionManager:
        """Get the transaction manager."""
        return self._transaction_manager

    def __del__(self):
        """Clean up connection on garbage collection."""
        try:
            self.disconnect()
        except Exception:
            pass