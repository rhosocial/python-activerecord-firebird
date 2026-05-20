# src/rhosocial/activerecord/backend/impl/firebird/mixins.py
"""Firebird backend mixin classes.

Firebird version requirements:
  - All features listed are available since Firebird 3.0 unless noted.
  - Firebird 2.5 features are noted explicitly.
"""

from typing import Any, Dict, List, Optional, Tuple, Type

from rhosocial.activerecord.backend import errors as exc
from rhosocial.activerecord.backend.base import TypeAdaptionMixin
from rhosocial.activerecord.backend.type_adapter import BaseSQLTypeAdapter, SQLTypeAdapter

from .adapters import (
    FirebirdBlobAdapter, FirebirdBooleanAdapter, FirebirdDateAdapter,
    FirebirdDatetimeAdapter, FirebirdDecimalAdapter, FirebirdTimeAdapter,
    FirebirdUUIDAdapter, FirebirdTextBlobAdapter,
    firebird_adapters,
)
from .types import FirebirdBlobType

FIREBIRD_VERSION_BOUNDARIES = {
    'WINDOW_FUNCTIONS': (3, 0, 0),
    'CTE': (3, 0, 0),
    'BOOLEAN': (3, 0, 0),
    'IDENTITY': (3, 0, 0),
    'SEQUENCE': (3, 0, 0),
    'PACKAGES': (3, 0, 0),
    'DATABASE_TRIGGERS': (3, 0, 0),
    'AUTONOMOUS_TRANS': (3, 0, 0),
    'UUID_TO_FROM_CHAR': (3, 0, 0),
    'SKIP_LOCKED': (4, 0, 0),
    'OFFSET_FETCH': (4, 0, 0),
    'DECFLOAT': (4, 0, 0),
    'EXPLAIN_PLAN': (3, 0, 0),
    'RETURNING_NO_INTO': (3, 0, 0),
    'EXECUTE_BLOCK': (2, 5, 0),
    'ROWS_SYNTAX': (2, 5, 0),
    'MON_TABLES': (2, 5, 0),
    'LIST_FUNCTION': (2, 5, 0),
    'DATEADD_DATEDIFF': (2, 5, 0),
    'GEN_UUID': (2, 5, 0),
    'REPLACE_FUNCTION': (2, 5, 0),
    'POSITION_FUNCTION': (2, 5, 0),
    'IIF_DECODE': (2, 5, 0),
    'COMPUTED_BY': (2, 5, 0),
}


class FirebirdTransactionMixin:
    """Mixin for Firebird transaction management.

    Firebird transaction model:
    - SET TRANSACTION must be the first statement in a transaction
    - Multiple isolation levels: READ COMMITTED, SNAPSHOT, SNAPSHOT TABLE STABILITY
    - READ ONLY / READ WRITE modes
    - WAIT / NO WAIT for conflict resolution
    """

    def _format_begin_sql(self, isolation_level=None, mode=None, wait=True, lock_timeout=None):
        """Format Firebird SET TRANSACTION statement.

        Firebird uses SET TRANSACTION instead of START TRANSACTION.

        Args:
            isolation_level: Optional isolation level name
            mode: Optional 'READ ONLY' or 'READ WRITE'
            wait: Whether to use WAIT (True) or NO WAIT (False)
            lock_timeout: Optional lock timeout in seconds

        Returns:
            SQL string
        """
        parts = ["SET TRANSACTION"]

        if isolation_level:
            level_map = {
                'READ UNCOMMITTED': 'READ COMMITTED',
                'READ COMMITTED': 'READ COMMITTED',
                'REPEATABLE READ': 'SNAPSHOT',
                'SERIALIZABLE': 'SNAPSHOT TABLE STABILITY',
            }
            fb_level = level_map.get(isolation_level.upper() if isinstance(isolation_level, str) else isolation_level, isolation_level)
            parts.append(f"ISOLATION LEVEL {fb_level}")

        if mode:
            parts.append(mode.upper())

        if wait:
            parts.append("WAIT")
        else:
            parts.append("NO WAIT")

        if lock_timeout is not None:
            parts.append(f"LOCK TIMEOUT {lock_timeout}")

        return " ".join(parts)


class FirebirdBackendMixin:
    """Shared non-I/O methods for Firebird backends."""

    CONNECTION_ERROR_CODES = {
        -902: "Unable to connect to database",
        -904: "Connection lost",
        -909: "Database shutdown",
        -916: "Database is not started",
        -917: "Database already in use",
        -923: "Connection not established",
    }

    _dialect = None
    _default_suggestions_cache = None

    @property
    def dialect(self):
        if self._dialect is None:
            from .dialect import FirebirdDialect
            self._dialect = FirebirdDialect()
            if hasattr(self, 'config') and self.config.version:
                self._dialect.version = self.config.version
        return self._dialect

    @dialect.setter
    def dialect(self, value):
        self._dialect = value

    @property
    def threadsafety(self) -> int:
        """Firebird driver supports thread-level safety (level 2)."""
        return 2

    def _register_firebird_adapters(self):
        """Register Firebird-specific type adapters."""
        registry = self.adapter_registry
        for adapter_class, py_type, db_type in firebird_adapters:
            adapter = adapter_class()
            if isinstance(py_type, tuple):
                for pt in py_type:
                    registry.register(adapter, pt, db_type, allow_override=True)
            else:
                registry.register(adapter, py_type, db_type, allow_override=True)

    @property
    def requires_manual_commit(self) -> bool:
        """Firebird requires manual COMMIT/ROLLBACK."""
        return True

    def _is_connection_error(self, error: Exception) -> bool:
        """Check if an exception represents a connection error.

        Args:
            error: Exception to check

        Returns:
            True if the error is a connection error
        """
        error_code = getattr(error, 'sqlcode', None)
        if error_code is not None and error_code in self.CONNECTION_ERROR_CODES:
            return True

        error_msg = str(error).lower()
        connection_keywords = [
            'unable to connect', 'connection lost', 'connection not established',
            'database shutdown', 'broken pipe', 'connection reset',
            'network error', 'connection refused', 'database already in use',
        ]
        return any(kw in error_msg for kw in connection_keywords)

    def _handle_error(self, error: Exception) -> None:
        """Classify and convert Firebird errors to framework exceptions.

        Args:
            error: Exception to classify

        Raises:
            Appropriate framework exception
        """
        error_msg = str(error)
        error_code = getattr(error, 'sqlcode', None)
        gds_code = getattr(error, 'gds_codes', None)

        if self._is_connection_error(error):
            raise exc.ConnectionError(error_msg) from error

        if gds_code:
            for code in gds_code if isinstance(gds_code, (list, tuple)) else [gds_code]:
                if abs(code) in (803, 804, 805):
                    raise exc.IntegrityError(error_msg) from error
                if abs(code) in (901,):
                    raise exc.LockError(error_msg) from error
                if abs(code) in (902,):
                    raise exc.DeadlockError(error_msg) from error

        if error_code:
            if error_code in (-803, -804, -805):
                raise exc.IntegrityError(error_msg) from error
            if error_code == -901:
                raise exc.DeadlockError(error_msg) from error
            if error_code in (-902, -904, -909, -916, -917, -923):
                raise exc.ConnectionError(error_msg) from error
            if error_code in (-530, -531):
                raise exc.IntegrityError(error_msg) from error
            if error_code in (-104, -206, -207):
                raise exc.QueryError(error_msg) from error
            if error_code in (-204,):
                raise exc.DatabaseError(error_msg) from error

        raise exc.DatabaseError(error_msg) from error

    def get_default_adapter_suggestions(self) -> Dict[Type, Tuple[SQLTypeAdapter, Type]]:
        """Provides default type adapter suggestions for Firebird."""
        if self._default_suggestions_cache is not None:
            return self._default_suggestions_cache

        import datetime as dt
        from decimal import Decimal

        suggestions: Dict[Type, Tuple[SQLTypeAdapter, Type]] = {}
        type_mappings = [
            (int, int),
            (float, float),
            (str, str),
            (bytes, bytes),
            (bool, bool),
            (dt.datetime, dt.datetime),
            (dt.date, dt.date),
            (dt.time, dt.time),
            (Decimal, Decimal),
            (dict, str),
            (list, str),
        ]

        for py_type, db_type in type_mappings:
            adapter = self.adapter_registry.get_adapter(py_type, db_type)
            if adapter:
                suggestions[py_type] = (adapter, db_type)

        self._default_suggestions_cache = suggestions
        return suggestions

    def _check_returning_compatibility(self, returning_columns):
        """Check if RETURNING clause is compatible with this backend."""
        version = getattr(self.dialect, 'version', None)
        if version is not None and version < (3, 0, 0):
            raise exc.UnsupportedTransactionModeError(
                "RETURNING clause", "Firebird",
                "RETURNING clause requires Firebird 3.0 or later"
            )
        return True

    def _get_result_mapping(self, cursor):
        """Get column names and types from cursor description.

        Args:
            cursor: Firebird cursor

        Returns:
            List of (name, type_code, display_size, internal_size, precision, scale, nullable) tuples
        """
        if cursor is None or cursor.description is None:
            return []

        mapping = []
        for desc in cursor.description:
            name = desc[0]  # Column name
            col_type = desc[1] if len(desc) > 1 else None
            mapping.append((name, col_type, None, None, None, None, True))
        return mapping


class FirebirdConcurrencyMixin:
    """Firebird concurrency support mixin."""

    @property
    def threadsafety(self) -> int:
        return 2

    @property
    def concurrency_hint(self) -> Optional[int]:
        """Firebird doesn't have a standard max_connections variable,
        but we return the configured pool_size as a hint."""
        return getattr(self, 'config', None) and getattr(self.config, 'pool_size', None)


class FirebirdDMLOperationMixin:
    """Firebird-specific DML operations mixin.

    Provides SQL generation for:
    - INSERT ... RETURNING
    - UPDATE ... RETURNING
    - DELETE ... RETURNING
    - UPDATE OR INSERT (Firebird UPSERT)
    - MERGE
    """

    def format_insert_statement(self, expr) -> Tuple[str, tuple]:
        """Format INSERT statement with optional RETURNING for Firebird.

        Firebird supports:
        - INSERT INTO table (cols) VALUES (vals) RETURNING col1, col2 INTO :var1, :var2
        - INSERT INTO table DEFAULT VALUES (for all-defaults insert)

        Args:
            expr: InsertExpression instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        all_params: List[Any] = []

        table_sql, table_params = expr.into.to_sql()
        all_params.extend(table_params)

        columns_sql = ""
        if expr.columns:
            columns_sql = "(" + ", ".join(self.format_identifier(c) for c in expr.columns) + ")"

        from rhosocial.activerecord.backend.expression.statements import DefaultValuesSource, ValuesSource, SelectSource

        source_sql = ""
        if isinstance(expr.source, DefaultValuesSource):
            source_sql = "DEFAULT VALUES"
        elif isinstance(expr.source, ValuesSource):
            all_rows_sql = []
            for row in expr.source.values_list:
                row_sql, row_params = [], []
                for val in row:
                    s, p = val.to_sql()
                    row_sql.append(s)
                    row_params.extend(p)
                all_rows_sql.append(f"({', '.join(row_sql)})")
                all_params.extend(row_params)
            source_sql = "VALUES " + ", ".join(all_rows_sql)
        elif isinstance(expr.source, SelectSource):
            s_sql, s_params = expr.source.select_query.to_sql()
            source_sql = s_sql
            all_params.extend(s_params)

        sql = f"INSERT INTO {table_sql} {columns_sql} {source_sql}".strip()

        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            sql += f" {returning_sql}"
            all_params.extend(returning_params)

        return sql, tuple(all_params)

    def format_update_statement(self, expr) -> Tuple[str, tuple]:
        """Format UPDATE statement with optional RETURNING for Firebird."""
        all_params: List[Any] = []

        table_sql, table_params = expr.table.to_sql()
        all_params.extend(table_params)

        set_parts = []
        for col, val in expr.assignments.items():
            col_str = self.format_identifier(col)
            if hasattr(val, 'to_sql'):
                val_sql, val_params = val.to_sql()
                set_parts.append(f"{col_str} = {val_sql}")
                all_params.extend(val_params)
            else:
                all_params.append(val)
                set_parts.append(f"{col_str} = {self.get_parameter_placeholder()}")

        sql = f"UPDATE {table_sql} SET {', '.join(set_parts)}"

        if expr.where:
            where_sql, where_params = expr.where.to_sql()
            sql += f" {where_sql}"
            all_params.extend(where_params)

        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            sql += f" {returning_sql}"
            all_params.extend(returning_params)

        return sql, tuple(all_params)

    def format_delete_statement(self, expr) -> Tuple[str, tuple]:
        """Format DELETE statement with optional RETURNING for Firebird."""
        all_params: List[Any] = []

        table_sql, table_params = expr.tables[0].to_sql()
        all_params.extend(table_params)

        sql = f"DELETE FROM {table_sql}"

        if expr.where:
            where_sql, where_params = expr.where.to_sql()
            sql += f" {where_sql}"
            all_params.extend(where_params)

        if expr.returning:
            returning_sql, returning_params = self.format_returning_clause(expr.returning)
            sql += f" {returning_sql}"
            all_params.extend(returning_params)

        return sql, tuple(all_params)

    def format_returning_clause(self, clause) -> Tuple[str, tuple]:
        """Format RETURNING clause for Firebird.

        Firebird syntax: RETURNING col1, col2 (INTO :var1, :var2 is optional in DSQL)

        Args:
            clause: ReturningClause instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        all_params = []
        expr_parts = []
        for expr in clause.expressions:
            expr_sql, expr_params = expr.to_sql()
            expr_parts.append(expr_sql)
            all_params.extend(expr_params)

        returning_sql = f"RETURNING {', '.join(expr_parts)}"
        return returning_sql, tuple(all_params)

    def format_update_or_insert(self, table_name: str, insert_columns: List[str],
                                insert_values: List, match_columns: List[str],
                                returning_columns: Optional[List[str]] = None) -> Tuple[str, tuple]:
        """Format UPDATE OR INSERT statement (Firebird UPSERT).

        Syntax:
          UPDATE OR INSERT INTO table (col1, col2) VALUES (val1, val2)
          MATCHING (pk_col1, pk_col2)
          RETURNING col1, col2

        Args:
            table_name: Target table name
            insert_columns: Column names for INSERT
            insert_values: Values to insert
            match_columns: Columns to match for UPDATE
            returning_columns: Optional columns to RETURN

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        all_params = list(insert_values)

        cols_str = ', '.join(self.format_identifier(c) for c in insert_columns)
        val_strs = ', '.join(self.get_parameter_placeholder() for _ in insert_values)
        match_str = ', '.join(self.format_identifier(c) for c in match_columns)

        parts = [
            f"UPDATE OR INSERT INTO {self.format_identifier(table_name)}",
            f"({cols_str})",
            f"VALUES ({val_strs})",
            f"MATCHING ({match_str})",
        ]

        if returning_columns:
            ret_str = ', '.join(self.format_identifier(c) for c in returning_columns)
            parts.append(f"RETURNING {ret_str}")

        return ' '.join(parts), tuple(all_params)

    def format_execute_block(self, block: str, params: Optional[Dict[str, Any]] = None) -> Tuple[str, tuple]:
        """Format EXECUTE BLOCK for Firebird.

        Syntax:
          EXECUTE BLOCK (param1 TYPE = ?, param2 TYPE = ?)
          AS
          BEGIN
            ...
          END

        Args:
            block: PSQL block body
            params: Optional parameter definitions

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        all_params = []
        if params:
            param_defs = []
            for name, (param_type, value) in params.items():
                param_defs.append(f"{name} {param_type} = ?")
                all_params.append(value)
            sql = f"EXECUTE BLOCK ({', '.join(param_defs)})\nAS\nBEGIN\n{block}\nEND"
        else:
            sql = f"EXECUTE BLOCK\nAS\nBEGIN\n{block}\nEND"
        return sql, tuple(all_params)


class FirebirdLockingMixin:
    """Firebird locking support mixin.

    Firebird supports:
    - SELECT ... FOR UPDATE (pessimistic locking, marks rows)
    - SELECT ... FOR UPDATE WITH LOCK (explicit row-level lock, FB 3.0+)
    - SELECT ... FOR UPDATE SKIP LOCKED (FB 4.0+, MySQL-compatible)
    - SELECT ... WITH LOCK (alternative syntax)
    """

    def format_for_update(self, expr) -> Tuple[str, tuple]:
        """Format FOR UPDATE clause.

        Args:
            expr: ForUpdateClause instance

        Returns:
            Tuple of (SQL string, empty tuple)
        """
        version = getattr(self, 'version', (3, 0, 0))
        parts = ["FOR UPDATE"]

        with_lock = getattr(expr, 'with_lock', False)
        skip_locked = getattr(expr, 'skip_locked', False)
        nowait = getattr(expr, 'nowait', False)

        if with_lock:
            parts.append("WITH LOCK")
        if skip_locked:
            if version >= (4, 0, 0):
                parts.append("SKIP LOCKED")
            else:
                from .dialect import FirebirdDialect
                if not isinstance(version, tuple):
                    version = getattr(self, 'version', (3, 0, 0))
        if nowait:
            parts.append("WITH LOCK")

        return ' '.join(parts), ()

    def supports_for_update_with_lock(self) -> bool:
        """Firebird 3.0+ supports WITH LOCK."""
        version = getattr(self, 'version', (3, 0, 0))
        return version >= (3, 0, 0)

    def supports_skip_locked(self) -> bool:
        """Firebird 4.0+ supports SKIP LOCKED."""
        version = getattr(self, 'version', (3, 0, 0))
        return version >= (4, 0, 0)


class FirebirdTableMixin:
    """Firebird table DDL operations mixin.

    Handles CREATE TABLE with:
    - COMPUTED BY / GENERATED ALWAYS AS (computed columns)
    - IDENTITY columns (FB 3.0+)
    - DEFAULT values
    - CONSTRAINTS (PK, FK, UNIQUE, CHECK)
    - EXTERNAL FILE (file-based tables)
    """

    def format_create_table_statement(self, expr) -> Tuple[str, tuple]:
        """Format CREATE TABLE statement for Firebird.

        Args:
            expr: CreateTableExpression instance

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        all_params: List[Any] = []

        parts = ["CREATE TABLE"]
        if getattr(expr, 'temporary', False):
            parts.append("GLOBAL TEMPORARY")
        if getattr(expr, 'if_not_exists', False):
            parts.append("IF NOT EXISTS")
        parts.append(self.format_identifier(expr.table_name))

        if getattr(expr, 'temporary', False):
            on_commit = getattr(expr, 'on_commit_delete', True)
            if on_commit:
                parts.append("ON COMMIT DELETE ROWS")
            else:
                parts.append("ON COMMIT PRESERVE ROWS")

        column_parts = []
        for col_def in expr.columns:
            col_sql, col_params = self._format_column_definition_firebird(col_def)
            column_parts.append(col_sql)
            all_params.extend(col_params)

        for t_const in expr.table_constraints:
            const_sql, const_params = self._format_table_constraint_firebird(t_const)
            column_parts.append(const_sql)
            all_params.extend(const_params)

        parts.append(f"({', '.join(column_parts)})")

        external_file = getattr(expr, 'external_file', None)
        if external_file:
            parts.append(f"EXTERNAL FILE '{external_file}'")

        return ' '.join(parts), tuple(all_params)

    def _format_column_definition_firebird(self, col_def) -> Tuple[str, List[Any]]:
        """Format a column definition for Firebird.

        Args:
            col_def: ColumnDefinition instance

        Returns:
            Tuple of (SQL string, parameters list)
        """
        from rhosocial.activerecord.backend.expression.statements import ColumnConstraintType

        parts = [self.format_identifier(col_def.name), col_def.data_type]
        params: List[Any] = []

        # IDENTITY column (Firebird 3.0+)
        if getattr(col_def, 'identity', False):
            generated = getattr(col_def, 'identity_generated', 'BY DEFAULT')
            parts.append(f"GENERATED {generated} AS IDENTITY")
            start = getattr(col_def, 'identity_start', None)
            increment = getattr(col_def, 'identity_increment', None)
            if start is not None or increment is not None:
                id_parts = []
                if start is not None:
                    id_parts.append(f"START WITH {start}")
                if increment is not None:
                    id_parts.append(f"INCREMENT BY {increment}")
                parts.append(f"({' '.join(id_parts)})")

        # COMPUTED BY (Firebird computed columns)
        computed_by = getattr(col_def, 'computed_by', None)
        if computed_by:
            parts.append(f"COMPUTED BY ({computed_by})")

        # Constraints
        constraint_parts = []
        for constraint in col_def.constraints:
            if constraint.constraint_type == ColumnConstraintType.PRIMARY_KEY:
                constraint_parts.append("PRIMARY KEY")
            elif constraint.constraint_type == ColumnConstraintType.NOT_NULL:
                constraint_parts.append("NOT NULL")
            elif constraint.constraint_type == ColumnConstraintType.UNIQUE:
                constraint_parts.append("UNIQUE")
            elif constraint.constraint_type == ColumnConstraintType.NULL:
                constraint_parts.append("NULL")
            elif constraint.constraint_type == ColumnConstraintType.DEFAULT:
                if constraint.default_value is not None:
                    from rhosocial.activerecord.backend.expression import bases
                    if isinstance(constraint.default_value, bases.BaseExpression):
                        default_sql, default_params = constraint.default_value.to_sql()
                        constraint_parts.append(f"DEFAULT {default_sql}")
                        params.extend(default_params)
                    elif isinstance(constraint.default_value, str):
                        escaped = constraint.default_value.replace("'", "''")
                        constraint_parts.append(f"DEFAULT '{escaped}'")
                    else:
                        constraint_parts.append(f"DEFAULT {constraint.default_value}")

        if constraint_parts:
            parts.append(' '.join(constraint_parts))

        # COLLATE clause
        collation = getattr(col_def, 'collation', None)
        if collation:
            parts.append(f"COLLATE {collation}")

        return ' '.join(parts), params

    def _format_table_constraint_firebird(self, t_const) -> Tuple[str, List[Any]]:
        """Format a table-level constraint for Firebird.

        Args:
            t_const: TableConstraint instance

        Returns:
            Tuple of (SQL string, parameters list)
        """
        from rhosocial.activerecord.backend.expression.statements import (
            ForeignKeyConstraint, ReferentialAction, TableConstraintType
        )

        parts = []
        params: List[Any] = []

        if t_const.name:
            parts.append(f"CONSTRAINT {self.format_identifier(t_const.name)}")

        if t_const.constraint_type == TableConstraintType.PRIMARY_KEY:
            if t_const.columns:
                cols = ', '.join(self.format_identifier(c) for c in t_const.columns)
                parts.append(f"PRIMARY KEY ({cols})")
        elif t_const.constraint_type == TableConstraintType.UNIQUE:
            if t_const.columns:
                cols = ', '.join(self.format_identifier(c) for c in t_const.columns)
                parts.append(f"UNIQUE ({cols})")
        elif t_const.constraint_type == TableConstraintType.FOREIGN_KEY:
            if t_const.columns and t_const.foreign_key_table and t_const.foreign_key_columns:
                cols = ', '.join(self.format_identifier(c) for c in t_const.columns)
                ref_cols = ', '.join(self.format_identifier(c) for c in t_const.foreign_key_columns)
                ref_table = self.format_identifier(t_const.foreign_key_table)
                parts.append(f"FOREIGN KEY ({cols}) REFERENCES {ref_table} ({ref_cols})")
            if isinstance(t_const, ForeignKeyConstraint):
                if t_const.on_delete != ReferentialAction.NO_ACTION:
                    parts.append(f"ON DELETE {t_const.on_delete.value}")
                if t_const.on_update != ReferentialAction.NO_ACTION:
                    parts.append(f"ON UPDATE {t_const.on_update.value}")
        elif t_const.constraint_type == TableConstraintType.CHECK and t_const.check_condition:
            check_sql, check_params = t_const.check_condition.to_sql()
            parts.append(f"CHECK ({check_sql})")
            params.extend(check_params)

        return ' '.join(parts), params

    def supports_computed_by(self) -> bool:
        return True

    def supports_identity_columns(self) -> bool:
        return True


class FirebirdTriggerMixin:
    """Firebird trigger DDL support mixin.

    Firebird triggers support:
    - BEFORE/AFTER INSERT/UPDATE/DELETE
    - POSITION clause (execution order)
    - WHEN condition
    - INACTIVE/ACTIVE state
    """

    def format_create_trigger(self, trigger_name: str, table_name: str,
                               timing: str, events: List[str],
                               body: str, position: int = 0,
                               when_condition: Optional[str] = None,
                               active: bool = True) -> Tuple[str, tuple]:
        """Format CREATE TRIGGER for Firebird.

        Args:
            trigger_name: Trigger name
            table_name: Table name
            timing: BEFORE or AFTER
            events: List of INSERT, UPDATE, DELETE
            body: PSQL trigger body
            position: Execution position (default 0)
            when_condition: Optional WHEN condition
            active: Whether trigger is ACTIVE (default True)

        Returns:
            Tuple of (SQL string, empty tuple)
        """
        parts = ["CREATE TRIGGER"]
        parts.append(self.format_identifier(trigger_name))
        if not active:
            parts.append("INACTIVE")
        parts.append(timing)
        parts.append(' OR '.join(events))
        parts.append("ON")
        parts.append(self.format_identifier(table_name))
        parts.append(f"POSITION {position}")
        if when_condition:
            parts.append(f"WHEN ({when_condition})")
        parts.append("AS")
        parts.append(body)

        return ' '.join(parts), ()


class FirebirdSequenceMixin:
    """Firebird GENERATOR/SEQUENCE support mixin.

    Firebird 3.0+ uses CREATE SEQUENCE (SQL standard).
    Legacy Firebird uses CREATE GENERATOR (still supported in FB 3.0+).
    """

    def format_create_sequence(self, sequence_name: str, start_value: int = 1,
                                increment: int = 1, use_generator: bool = False) -> Tuple[str, tuple]:
        """Format CREATE SEQUENCE or CREATE GENERATOR statement.

        Args:
            sequence_name: Sequence/generator name
            start_value: Initial value
            increment: Increment step
            use_generator: True for CREATE GENERATOR (legacy), False for CREATE SEQUENCE

        Returns:
            Tuple of (SQL string, empty tuple)
        """
        if use_generator:
            return f"CREATE GENERATOR {self.format_identifier(sequence_name)}", ()
        else:
            parts = [f"CREATE SEQUENCE {self.format_identifier(sequence_name)}"]
            if start_value != 1:
                parts.append(f"START WITH {start_value}")
            if increment != 1:
                parts.append(f"INCREMENT BY {increment}")
            return ' '.join(parts), ()

    def format_gen_id(self, generator_name: str, step: int = 1) -> Tuple[str, tuple]:
        """Format GEN_ID function to get next generator value.

        Args:
            generator_name: Generator name
            step: Increment step

        Returns:
            Tuple of (SQL string, parameters tuple)
        """
        return f"GEN_ID({self.format_identifier(generator_name)}, {step})", ()

    def format_next_value_for(self, sequence_name: str) -> Tuple[str, tuple]:
        """Format NEXT VALUE FOR expression (SQL standard, FB 3.0+).

        Args:
            sequence_name: Sequence name

        Returns:
            Tuple of (SQL string, empty tuple)
        """
        return f"NEXT VALUE FOR {self.format_identifier(sequence_name)}", ()


class FirebirdBlobMixin:
    """Firebird BLOB handling mixin.

    Firebird BLOB types:
    - BLOB SUB_TYPE 0 (BINARY): Unstructured binary data
    - BLOB SUB_TYPE 1 (TEXT): Text data with character set
    - BLOB SUB_TYPE 2 (BLR): BLR (Binary Language Representation)
    - BLOB SUB_TYPE 3 (ACL): Access Control List
    - BLOB SUB_TYPE 4 (RANGES): Ranges (delta for system tables)
    - BLOB SUB_TYPE 5 (FORMATTED_TEXT): Formatted text
    """

    def format_blob_column(self, column_name: str, sub_type: int = 0,
                            segment_size: int = 65536,
                            character_set: Optional[str] = None) -> str:
        """Format a BLOB column definition.

        Args:
            column_name: Column name
            sub_type: BLOB sub_type (0=binary, 1=text)
            segment_size: Maximum segment size
            character_set: Character set for SUB_TYPE TEXT

        Returns:
            SQL column definition string
        """
        parts = [f"{self.format_identifier(column_name)} BLOB SUB_TYPE {sub_type}"]
        if sub_type == 1 and character_set:
            parts.append(f"CHARACTER SET {character_set}")
        parts.append(f"SEGMENT SIZE {segment_size}")
        return ' '.join(parts)


class FirebirdIntrospectionMixin:
    """Firebird schema introspection mixin using RDB$ system tables.

    Firebird system tables:
    - RDB$RELATIONS: Tables and views
    - RDB$RELATION_FIELDS: Columns per table
    - RDB$FIELDS: Field type definitions
    - RDB$INDICES: Index definitions
    - RDB$TRIGGERS: Trigger definitions
    - RDB$PROCEDURES: Stored procedure definitions
    - RDB$FUNCTIONS: UDF definitions
    - RDB$GENERATORS: Sequence/generator definitions
    - MON$DATABASE: Database metadata
    """

    INTROSPECTION_QUERIES = {
        'tables': """
            SELECT
                RDB$RELATION_NAME AS TABLE_NAME,
                RDB$VIEW_SOURCE AS VIEW_SOURCE,
                RDB$SYSTEM_FLAG AS SYSTEM_FLAG
            FROM RDB$RELATIONS
            WHERE RDB$SYSTEM_FLAG = 0
            ORDER BY RDB$RELATION_NAME
        """,
        'columns': """
            SELECT
                rf.RDB$FIELD_NAME AS COLUMN_NAME,
                f.RDB$FIELD_TYPE AS FIELD_TYPE,
                f.RDB$FIELD_SUB_TYPE AS FIELD_SUB_TYPE,
                f.RDB$CHARACTER_LENGTH AS CHAR_LENGTH,
                f.RDB$FIELD_PRECISION AS PRECISION,
                f.RDB$FIELD_SCALE AS SCALE,
                rf.RDB$NULL_FLAG AS NULL_FLAG,
                rf.RDB$DEFAULT_SOURCE AS DEFAULT_SOURCE,
                rf.RDB$POSITION AS POSITION,
                rf.RDB$COMPUTED_SOURCE AS COMPUTED_SOURCE
            FROM RDB$RELATION_FIELDS rf
            JOIN RDB$FIELDS f ON rf.RDB$FIELD_SOURCE = f.RDB$FIELD_NAME
            WHERE rf.RDB$RELATION_NAME = ?
            ORDER BY rf.RDB$POSITION
        """,
        'indices': """
            SELECT
                i.RDB$INDEX_NAME AS INDEX_NAME,
                i.RDB$UNIQUE_FLAG AS UNIQUE_FLAG,
                i.RDB$INDEX_TYPE AS INDEX_TYPE,
                i.RDB$INDEX_INACTIVE AS INACTIVE,
                isg.RDB$FIELD_NAME AS FIELD_NAME,
                isg.RDB$FIELD_POSITION AS FIELD_POSITION
            FROM RDB$INDICES i
            JOIN RDB$INDEX_SEGMENTS isg ON i.RDB$INDEX_NAME = isg.RDB$INDEX_NAME
            WHERE i.RDB$RELATION_NAME = ?
            ORDER BY i.RDB$INDEX_NAME, isg.RDB$FIELD_POSITION
        """,
        'triggers': """
            SELECT
                RDB$TRIGGER_NAME AS TRIGGER_NAME,
                RDB$RELATION_NAME AS TABLE_NAME,
                RDB$TRIGGER_TYPE AS TRIGGER_TYPE,
                RDB$TRIGGER_SOURCE AS SOURCE,
                RDB$TRIGGER_INACTIVE AS INACTIVE,
                RDB$TRIGGER_SEQUENCE AS SEQUENCE
            FROM RDB$TRIGGERS
            WHERE RDB$RELATION_NAME IS NOT NULL
            ORDER BY RDB$TRIGGER_NAME
        """,
        'generators': """
            SELECT
                RDB$GENERATOR_NAME AS GENERATOR_NAME,
                RDB$GENERATOR_ID AS GENERATOR_ID,
                RDB$SYSTEM_FLAG AS SYSTEM_FLAG
            FROM RDB$GENERATORS
            WHERE RDB$SYSTEM_FLAG = 0
            ORDER BY RDB$GENERATOR_NAME
        """,
        'procedures': """
            SELECT
                RDB$PROCEDURE_NAME AS PROCEDURE_NAME,
                RDB$PROCEDURE_INPUTS AS INPUT_PARAMS,
                RDB$PROCEDURE_OUTPUTS AS OUTPUT_PARAMS,
                RDB$PROCEDURE_SOURCE AS SOURCE
            FROM RDB$PROCEDURES
            WHERE RDB$SYSTEM_FLAG = 0
            ORDER BY RDB$PROCEDURE_NAME
        """,
    }


__all__ = [
    "FIREBIRD_VERSION_BOUNDARIES",
    "FirebirdTransactionMixin",
    "FirebirdBackendMixin",
    "FirebirdConcurrencyMixin",
    "FirebirdDMLOperationMixin",
    "FirebirdLockingMixin",
    "FirebirdTableMixin",
    "FirebirdTriggerMixin",
    "FirebirdSequenceMixin",
    "FirebirdBlobMixin",
    "FirebirdIntrospectionMixin",
]