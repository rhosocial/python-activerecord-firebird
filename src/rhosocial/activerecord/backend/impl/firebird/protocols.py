# src/rhosocial/activerecord/backend/impl/firebird/protocols.py
"""Firebird dialect-specific protocol definitions.

This module defines protocols for features specific to Firebird.

Firebird version reference:
  - FB 2.5: Basic SQL, ROWS syntax, EXECUTE BLOCK, GENERATORS
  - FB 3.0: WINDOW functions, CTE, IDENTITY columns, BOOLEAN, SEQUENCE
  - FB 4.0: OFFSET/FETCH, SKIP LOCKED, COMPUTED BY improvements
  - FB 5.0: Additional improvements
"""

from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class FirebirdDMLOperationSupport(Protocol):
    """Firebird-specific DML operations protocol.

    Firebird DML features:
    - UPDATE OR INSERT: UPSERT operation
    - INSERT ... RETURNING: Insert and return values
    - UPDATE ... RETURNING: Update and return values
    - DELETE ... RETURNING: Delete and return values
    - MERGE: Standard SQL MERGE
    - EXECUTE BLOCK: Anonymous PSQL block
    """

    def supports_update_or_insert(self) -> bool:
        """Whether UPDATE OR INSERT is supported."""
        ...

    def supports_returning(self) -> bool:
        """Whether RETURNING clause is supported for all DML."""
        ...

    def supports_merge(self) -> bool:
        """Whether MERGE statement is supported."""
        ...

    def supports_execute_block(self) -> bool:
        """Whether EXECUTE BLOCK is supported."""
        ...

    def format_update_or_insert(self, expr: Any) -> Tuple[str, tuple]:
        """Format UPDATE OR INSERT statement."""
        ...

    def format_execute_block(self, expr: Any) -> Tuple[str, tuple]:
        """Format EXECUTE BLOCK statement."""
        ...


@runtime_checkable
class FirebirdGeneratorSupport(Protocol):
    """Firebird GENERATOR/SEQUENCE support protocol.

    Firebird 3+ supports CREATE SEQUENCE (SQL standard name),
    while older versions use CREATE GENERATOR (Firebird legacy).
    """

    def supports_create_sequence(self) -> bool:
        """Whether CREATE SEQUENCE (FB 3+) is supported."""
        ...

    def supports_create_generator(self) -> bool:
        """Whether CREATE GENERATOR (FB 2.5 legacy) is supported."""
        ...

    def supports_alter_sequence(self) -> bool:
        """Whether ALTER SEQUENCE is supported."""
        ...

    def format_gen_id(self, generator_name: str, step: int = 1) -> Tuple[str, tuple]:
        """Format GEN_ID function call."""
        ...

    def format_next_value_for(self, sequence_name: str) -> Tuple[str, tuple]:
        """Format NEXT VALUE FOR expression."""
        ...


@runtime_checkable
class FirebirdBlobSupport(Protocol):
    """Firebird BLOB support protocol.

    Firebird has BLOB SUB_TYPE TEXT and BLOB SUB_TYPE BINARY.
    """

    def supports_blob(self) -> bool:
        """Whether BLOB type is supported."""
        ...

    def supports_blob_sub_type(self, sub_type: int) -> bool:
        """Whether specific BLOB sub_type is supported."""
        ...

    def format_blob_literal(self, value: bytes, sub_type: int = 0) -> Tuple[str, tuple]:
        """Format BLOB literal."""
        ...


@runtime_checkable
class FirebirdLockingSupport(Protocol):
    """Firebird locking support protocol.

    Firebird uses:
    - FOR UPDATE WITH LOCK: Explicit row-level locking
    - FOR UPDATE: Standard pessimistic locking
    - SKIP LOCKED: FB 4.0+
    """

    def supports_for_update_with_lock(self) -> bool:
        """Whether FOR UPDATE WITH LOCK is supported."""
        ...

    def supports_skip_locked(self) -> bool:
        """Whether SKIP LOCKED clause (FB 4.0+) is supported."""
        ...


@runtime_checkable
class FirebirdTransactionSupport(Protocol):
    """Firebird transaction support protocol.

    Firebird supports:
    - READ COMMITTED (default)
    - SNAPSHOT (REPEATABLE READ equivalent)
    - SNAPSHOT TABLE STABILITY (SERIALIZABLE equivalent)
    - READ ONLY / READ WRITE
    - WAIT / NO WAIT
    - LOCK TIMEOUT
    """

    def supports_snapshot_isolation(self) -> bool:
        """Whether SNAPSHOT isolation level is supported."""
        ...

    def supports_table_stability(self) -> bool:
        """Whether SNAPSHOT TABLE STABILITY is supported."""
        ...

    def supports_wait_option(self) -> bool:
        """Whether WAIT/NO WAIT is supported."""
        ...

    def supports_lock_timeout(self) -> bool:
        """Whether LOCK TIMEOUT is supported."""
        ...


@runtime_checkable
class FirebirdTableSupport(Protocol):
    """Firebird table-specific features protocol."""

    def supports_computed_by(self) -> bool:
        """Whether COMPUTED BY columns are supported."""
        ...

    def supports_generated_always(self) -> bool:
        """Whether GENERATED ALWAYS AS identity columns are supported."""
        ...

    def supports_identity_columns(self) -> bool:
        """Whether IDENTITY columns (FB 3.0+) are supported."""
        ...

    def supports_external_file(self) -> bool:
        """Whether external file tables are supported."""
        ...


@runtime_checkable
class FirebirdTriggerSupport(Protocol):
    """Firebird trigger-specific protocol.

    Firebird triggers can be BEFORE/AFTER INSERT/UPDATE/DELETE,
    with optional POSITION clause for execution order.
    """

    def supports_trigger_position(self) -> bool:
        """Whether trigger POSITION clause is supported."""
        ...


@runtime_checkable
class FirebirdReturningSupport(Protocol):
    """Firebird RETURNING clause support.

    Firebird supports RETURNING for INSERT, UPDATE, DELETE, and
    UPDATE OR INSERT. The INTO clause is optional in DSQL (FB 3.0+).
    """

    def supports_returning_into(self) -> bool:
        """Whether RETURNING ... INTO is supported."""
        ...


@runtime_checkable
class FirebirdIntrospectionSupport(Protocol):
    """Firebird introspection protocol.

    Firebird system tables/database:
    - RDB$RELATIONS: Tables
    - RDB$RELATION_FIELDS: Columns
    - RDB$FIELDS: Field types
    - RDB$INDICES: Indexes
    - RDB$TRIGGERS: Triggers
    - RDB$PROCEDURES: Stored procedures
    - RDB$FUNCTIONS: UDF functions
    - RDB$GENERATORS: Sequences/generators
    - MON$ tables: Performance monitoring tables (FB 2.5+)
    """

    def supports_mon_tables(self) -> bool:
        """Whether MON$ monitoring tables are available."""
        ...


@runtime_checkable
class FirebirdExecuteBlockSupport(Protocol):
    """Firebird EXECUTE BLOCK support.

    EXECUTE BLOCK allows executing anonymous PSQL blocks.
    """

    def supports_execute_block(self) -> bool:
        """Whether EXECUTE BLOCK is supported."""
        ...

    def format_execute_block(self, block: Any) -> Tuple[str, tuple]:
        """Format anonymous PSQL block."""
        ...


@runtime_checkable
class FirebirdExplainSupport(Protocol):
    """Firebird EXPLAIN plan support.

    Firebird uses:
    - EXPLAIN PLAN FOR: Show query plan (FB 3.0+)
    - `SELECT ... PLAN`: Use optimizer plan hint
    """

    def supports_explain_plan(self) -> bool:
        """Whether EXPLAIN PLAN is supported."""
        ...


@runtime_checkable
class FirebirdFunctionSupport(Protocol):
    """Firebird built-in function support protocol.

    Firebird has extensive built-in SQL functions.
    """

    def supports_list_function(self) -> bool:
        """Whether LIST() aggregate function is supported."""
        ...

    def supports_replace_function(self) -> bool:
        """Whether REPLACE() function is supported."""
        ...

    def supports_position_function(self) -> bool:
        """Whether POSITION() function is supported."""
        ...

    def supports_char_length_function(self) -> bool:
        """Whether CHAR_LENGTH() / CHARACTER_LENGTH() is supported."""
        ...

    def supports_bit_functions(self) -> bool:
        """Whether BIN_AND, BIN_OR, BIN_XOR, BIN_NOT are supported."""
        ...

    def supports_date_time_functions(self) -> bool:
        """Whether DATEADD, DATEDIFF, EXTRACT are supported."""
        ...

    def supports_string_functions(self) -> bool:
        """Whether string functions (TRIM, SUBSTRING, UPPER, LOWER) are supported."""
        ...

    def supports_gen_uid(self) -> bool:
        """Whether GEN_UUID() function is supported."""
        ...


@runtime_checkable
class FirebirdBooleanSupport(Protocol):
    """Firebird BOOLEAN type support (FB 3.0+)."""

    def supports_boolean_type(self) -> bool:
        """Whether native BOOLEAN type is supported."""
        ...


@runtime_checkable
class FirebirdDecFloatSupport(Protocol):
    """Firebird DECFLOAT type support (FB 4.0+)."""

    def supports_decfloat(self) -> bool:
        """Whether DECFLOAT type (FB 4.0+) is supported."""
        ...


@runtime_checkable
class FirebirdPaginationSupport(Protocol):
    """Firebird pagination support.

    FB 2.5+: ROWS m TO n
    FB 4.0+: OFFSET m ROWS FETCH NEXT n ROWS ONLY
    """

    def supports_rows_syntax(self) -> bool:
        """Whether ROWS m TO n syntax is supported."""
        ...

    def supports_offset_fetch(self) -> bool:
        """Whether OFFSET/FETCH NEXT syntax (FB 4.0+) is supported."""
        ...


@runtime_checkable
class FirebirdDatabaseTriggerSupport(Protocol):
    """Firebird database-level trigger support (FB 3.0+).

    Database triggers: ON CONNECT, ON DISCONNECT, ON TRANSACTION START
    """

    def supports_database_triggers(self) -> bool:
        """Whether database-level triggers are supported."""
        ...


@runtime_checkable
class FirebirdWindowFunctionSupport(Protocol):
    """Firebird window function support (FB 3.0+).

    Firebird 3.0+ supports standard window functions including:
    - ROW_NUMBER(), RANK(), DENSE_RANK(), NTILE()
    - LEAD(), LAG(), FIRST_VALUE(), LAST_VALUE()
    - SUM(), COUNT(), AVG() OVER(...)
    """

    def supports_window_functions(self) -> bool:
        """Whether window functions (FB 3.0+) are supported."""
        ...


@runtime_checkable
class FirebirdCTESupport(Protocol):
    """Firebird CTE support (FB 3.0+).

    Firebird 3.0+ supports non-recursive and recursive CTEs.
    """

    def supports_cte(self) -> bool:
        """Whether CTE (FB 3.0+) is supported."""
        ...

    def supports_recursive_cte(self) -> bool:
        """Whether recursive CTE is supported."""
        ...


@runtime_checkable
class FirebirdFullTextSearchSupport(Protocol):
    """Firebird full-text search support.

    Firebird does not have native full-text search.
    External tools (e.g., Sphinx) or LIKE/containing are used.
    """

    def supports_fulltext_index(self) -> bool:
        """Whether native full-text search is supported."""
        ...


@runtime_checkable
class FirebirdUDFSupport(Protocol):
    """Firebird UDF/External Function support.

    Firebird supports external functions (UDFs) loaded from shared libraries.
    """

    def supports_udf(self) -> bool:
        """Whether UDF (external function modules) is supported."""
        ...

    def supports_declare_external_function(self) -> bool:
        """Whether DECLARE EXTERNAL FUNCTION is supported."""
        ...


@runtime_checkable
class FirebirdPackageSupport(Protocol):
    """Firebird package support (FB 3.0+).

    Firebird 3.0+ supports packages (header + body).
    """

    def supports_packages(self) -> bool:
        """Whether packages (FB 3.0+) are supported."""
        ...

    def supports_create_package(self) -> bool:
        """Whether CREATE PACKAGE is supported."""
        ...

    def supports_create_package_body(self) -> bool:
        """Whether CREATE PACKAGE BODY is supported."""
        ...


@runtime_checkable
class FirebirdGlobalMappingSupport(Protocol):
    """Firebird global temporary table mapping (FB 3.0+)."""

    def supports_global_temporary_table(self) -> bool:
        """Whether GLOBAL TEMPORARY TABLE is supported."""
        ...

    def supports_on_commit_delete_rows(self) -> bool:
        """Whether ON COMMIT DELETE ROWS is supported."""
        ...

    def supports_on_commit_preserve_rows(self) -> bool:
        """Whether ON COMMIT PRESERVE ROWS is supported."""
        ...


@runtime_checkable
class FirebirdMonitoringSupport(Protocol):
    """Firebird monitoring table support (FB 2.5+)."""

    def supports_monitoring(self) -> bool:
        """Whether MON$ monitoring tables are supported."""
        ...


@runtime_checkable
class FirebirdRoleSupport(Protocol):
    """Firebird role-based security support."""

    def supports_roles(self) -> bool:
        """Whether database roles are supported."""
        ...

    def supports_create_role(self) -> bool:
        """Whether CREATE ROLE is supported."""
        ...

    def supports_autonomous_transaction(self) -> bool:
        """Whether autonomous transactions (FB 3.0+) are supported."""
        ...


@runtime_checkable
class FirebirdCursorSupport(Protocol):
    """Firebird cursor support.

    Firebird supports cursors in PSQL and DSQL.
    """

    def supports_for_cursor(self) -> bool:
        """Whether FOR cursor loops in PSQL are supported."""
        ...

    def supports_as_cursor(self) -> bool:
        """Whether cursors in DSQL (FB 3.0+) are supported."""
        ...


@runtime_checkable
class FirebirdCollationSupport(Protocol):
    """Firebird collation and character set support."""

    def supports_collation(self) -> bool:
        """Whether collation clauses are supported."""
        ...

    def supports_character_set(self) -> bool:
        """Whether CHARACTER SET clause is supported."""
        ...


@runtime_checkable
class FirebirdExceptionSupport(Protocol):
    """Firebird exception handling support.

    Firebird supports EXCEPTION objects that can be raised in PSQL.
    """

    def supports_exception(self) -> bool:
        """Whether CREATE/DROP EXCEPTION is supported."""
        ...

    def supports_create_exception(self) -> bool:
        """Whether CREATE EXCEPTION is supported."""
        ...


@runtime_checkable
class FirebirdContextVariableSupport(Protocol):
    """Firebird context variable support.

    Firebird supports RDB$GET_CONTEXT() and RDB$SET_CONTEXT()
    for namespace-based context variables.
    """

    def supports_context_variables(self) -> bool:
        """Whether RDB$GET_CONTEXT/SET_CONTEXT is supported."""
        ...


__all__ = [
    "FirebirdDMLOperationSupport",
    "FirebirdGeneratorSupport",
    "FirebirdBlobSupport",
    "FirebirdLockingSupport",
    "FirebirdTransactionSupport",
    "FirebirdTableSupport",
    "FirebirdTriggerSupport",
    "FirebirdReturningSupport",
    "FirebirdIntrospectionSupport",
    "FirebirdExecuteBlockSupport",
    "FirebirdExplainSupport",
    "FirebirdFunctionSupport",
    "FirebirdBooleanSupport",
    "FirebirdDecFloatSupport",
    "FirebirdPaginationSupport",
    "FirebirdDatabaseTriggerSupport",
    "FirebirdWindowFunctionSupport",
    "FirebirdCTESupport",
    "FirebirdFullTextSearchSupport",
    "FirebirdUDFSupport",
    "FirebirdPackageSupport",
    "FirebirdGlobalMappingSupport",
    "FirebirdMonitoringSupport",
    "FirebirdRoleSupport",
    "FirebirdCursorSupport",
    "FirebirdCollationSupport",
    "FirebirdExceptionSupport",
    "FirebirdContextVariableSupport",
]