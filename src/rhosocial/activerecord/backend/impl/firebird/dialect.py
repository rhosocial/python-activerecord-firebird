# src/rhosocial/activerecord/backend/impl/firebird/dialect.py
"""Firebird SQL dialect implementation.

Firebird SQL dialect features and version support:
  - Window functions (FB 3.0+)
  - CTE (FB 3.0+)
  - RETURNING clause (FB 3.0+)
  - BOOLEAN type (FB 3.0+)
  - IDENTITY columns (FB 3.0+)
  - SEQUENCE (FB 3.0+)
  - SKIP LOCKED (FB 4.0+)
  - OFFSET/FETCH (FB 4.0+)
  - DECFLOAT (FB 4.0+)
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.base import SQLDialectBase
from rhosocial.activerecord.backend.dialect.protocols import (
    CollationSupport,
    CTESupport,
    WindowFunctionSupport,
    JSONSupport,
    ReturningSupport,
    SetOperationSupport,
    SequenceSupport,
    UpsertSupport,
    LockingSupport,
    ExplainSupport,
    JoinSupport,
    WildcardSupport,
    ILIKESupport,
    FilterClauseSupport,
    AdvancedGroupingSupport,
    ArraySupport,
    LateralJoinSupport,
    MergeSupport,
    TemporalTableSupport,
    QualifyClauseSupport,
    OrderedSetAggregationSupport,
    GraphSupport,
    TableSupport,
    TruncateSupport,
    SchemaSupport,
    IndexSupport,
    TriggerSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TransactionControlSupport,
    GeneratedColumnSupport,
    ViewSupport,
    FunctionSupport,
)
from rhosocial.activerecord.backend.dialect.mixins import (
    CollationMixin,
    CTEMixin,
    WindowFunctionMixin,
    JSONMixin,
    ReturningMixin,
    SetOperationMixin,
    SequenceMixin,
    UpsertMixin,
    LockingMixin,
    ExplainMixin,
    JoinMixin,
    ILIKEMixin,
    FilterClauseMixin,
    AdvancedGroupingMixin,
    ArrayMixin,
    LateralJoinMixin,
    MergeMixin,
    TemporalTableMixin,
    QualifyClauseMixin,
    OrderedSetAggregationMixin,
    GraphMixin,
    TableMixin,
    TruncateMixin,
    SchemaMixin,
    IndexMixin,
    TriggerMixin,
    GeneratedColumnMixin,
    ViewMixin,
    FunctionMixin,
    IntrospectionMixin,
)
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from .collation import validate_firebird_collation_name
from .mixins import (
    FirebirdDMLOperationMixin,
    FirebirdLockingMixin,
    FirebirdTableMixin,
    FirebirdTriggerMixin,
    FirebirdSequenceMixin,
    FirebirdBlobMixin,
    FirebirdIntrospectionMixin,
)
from .protocols import (
    FirebirdDMLOperationSupport,
    FirebirdGeneratorSupport,
    FirebirdBlobSupport,
    FirebirdLockingSupport,
    FirebirdTransactionSupport,
    FirebirdTableSupport,
    FirebirdTriggerSupport,
    FirebirdReturningSupport,
    FirebirdIntrospectionSupport,
    FirebirdExecuteBlockSupport,
    FirebirdExplainSupport,
    FirebirdFunctionSupport,
    FirebirdBooleanSupport,
    FirebirdDecFloatSupport,
    FirebirdPaginationSupport,
    FirebirdDatabaseTriggerSupport,
    FirebirdWindowFunctionSupport,
    FirebirdCTESupport,
    FirebirdFullTextSearchSupport,
    FirebirdUDFSupport,
    FirebirdPackageSupport,
    FirebirdGlobalMappingSupport,
    FirebirdMonitoringSupport,
    FirebirdRoleSupport,
    FirebirdCursorSupport,
    FirebirdCollationSupport,
    FirebirdExceptionSupport,
    FirebirdContextVariableSupport,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression import bases
    from rhosocial.activerecord.backend.expression.collation import CollateExpression
    from rhosocial.activerecord.backend.expression.statements import ReturningClause, CreateTableExpression

_SUGGESTION_ARRAY = "Firebird does not support array types. Use separate tables or BLOB."
_SUGGESTION_GRAPH_MATCH = "Firebird does not support graph MATCH clause."
_SUGGESTION_ORDERED_SET_AGG = "Firebird does not support ordered-set aggregate functions (WITHIN GROUP)."
_SUGGESTION_QUALIFY = "Firebird does not support QUALIFY clause. Use subquery or CTE."
_SUGGESTION_MERGE = "Firebird does not support MERGE with standard SQL merge syntax. Use UPDATE OR INSERT instead."
_SUGGESTION_JSON = "Firebird does not support native JSON type. Use BLOB SUB_TYPE TEXT with JSON content."
_SUGGESTION_FULLTEXT = "Firebird does not support native full-text search indexes. Use LIKE or external search."
_SUGGESTION_ILIIKE = "Firebird does not support ILIKE. Use UPPER(column) LIKE UPPER(pattern)."
_SUGGESTION_TEMPORAL = "Firebird does not support temporal tables."


class FirebirdDialect(
    SQLDialectBase,
    FirebirdDMLOperationMixin,
    FirebirdLockingMixin,
    FirebirdTableMixin,
    FirebirdTriggerMixin,
    FirebirdSequenceMixin,
    FirebirdBlobMixin,
    FirebirdIntrospectionMixin,
    CollationMixin,
    CTEMixin,
    WindowFunctionMixin,
    JSONMixin,
    ReturningMixin,
    SetOperationMixin,
    SequenceMixin,
    UpsertMixin,
    LockingMixin,
    ExplainMixin,
    JoinMixin,
    ILIKEMixin,
    FilterClauseMixin,
    AdvancedGroupingMixin,
    ArrayMixin,
    LateralJoinMixin,
    MergeMixin,
    TemporalTableMixin,
    QualifyClauseMixin,
    OrderedSetAggregationMixin,
    GraphMixin,
    TableMixin,
    TruncateMixin,
    SchemaMixin,
    IndexMixin,
    TriggerMixin,
    GeneratedColumnMixin,
    ViewMixin,
    FunctionMixin,
    IntrospectionMixin,
    CollationSupport,
    CTESupport,
    WindowFunctionSupport,
    JSONSupport,
    ReturningSupport,
    SetOperationSupport,
    SequenceSupport,
    UpsertSupport,
    LockingSupport,
    ExplainSupport,
    JoinSupport,
    WildcardSupport,
    ILIKESupport,
    FilterClauseSupport,
    AdvancedGroupingSupport,
    ArraySupport,
    LateralJoinSupport,
    MergeSupport,
    TemporalTableSupport,
    QualifyClauseSupport,
    OrderedSetAggregationSupport,
    GraphSupport,
    TableSupport,
    TruncateSupport,
    SchemaSupport,
    IndexSupport,
    TriggerSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TransactionControlSupport,
    GeneratedColumnSupport,
    ViewSupport,
    FunctionSupport,
    FirebirdDMLOperationSupport,
    FirebirdGeneratorSupport,
    FirebirdBlobSupport,
    FirebirdLockingSupport,
    FirebirdTransactionSupport,
    FirebirdTableSupport,
    FirebirdTriggerSupport,
    FirebirdReturningSupport,
    FirebirdIntrospectionSupport,
    FirebirdExecuteBlockSupport,
    FirebirdExplainSupport,
    FirebirdFunctionSupport,
    FirebirdBooleanSupport,
    FirebirdDecFloatSupport,
    FirebirdPaginationSupport,
    FirebirdDatabaseTriggerSupport,
    FirebirdWindowFunctionSupport,
    FirebirdCTESupport,
    FirebirdFullTextSearchSupport,
    FirebirdUDFSupport,
    FirebirdPackageSupport,
    FirebirdGlobalMappingSupport,
    FirebirdMonitoringSupport,
    FirebirdRoleSupport,
    FirebirdCursorSupport,
    FirebirdCollationSupport,
    FirebirdExceptionSupport,
    FirebirdContextVariableSupport,
):
    """Firebird dialect implementation that adapts to Firebird version.

    Firebird version-specific features:
    - Window functions (FB 3.0+)
    - CTE (FB 3.0+)
    - RETURNING (FB 3.0+)
    - IDENTITY columns (FB 3.0+)
    - BOOLEAN type (FB 3.0+)
    - Packages (FB 3.0+)
    - SKIP LOCKED (FB 4.0+)
    - OFFSET/FETCH (FB 4.0+)
    - DECFLOAT (FB 4.0+)
    - EXECUTE BLOCK (FB 2.5+)
    - ROWS syntax (FB 2.5+)
    """

    def __init__(self, version: Optional[Tuple[int, int, int]] = None):
        super().__init__()
        if version is not None:
            self.version = version

    def get_parameter_placeholder(self, position: int = 0) -> str:
        """Firebird uses ? as positional parameter placeholder."""
        return "?"

    def format_extract_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        source_sql, source_params = expr.source.to_sql()
        sql = f"EXTRACT({expr.field.value.upper()} FROM {source_sql})"
        return self._apply_value_expression_modifiers(sql, source_params, expr)

    def format_date_part_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        return self.format_extract_expression(expr)

    def format_date_trunc_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        source_sql, source_params = expr.source.to_sql()
        if expr.field.value == "year":
            sql = f"CAST(EXTRACT(YEAR FROM {source_sql}) || '-01-01 00:00:00' AS TIMESTAMP)"
        elif expr.field.value == "month":
            sql = (
                f"CAST(EXTRACT(YEAR FROM {source_sql}) || '-' || "
                f"EXTRACT(MONTH FROM {source_sql}) || '-01 00:00:00' AS TIMESTAMP)"
            )
        elif expr.field.value == "day":
            sql = f"CAST(CAST({source_sql} AS DATE) AS TIMESTAMP)"
        elif expr.field.value == "hour":
            sql = (
                f"DATEADD(EXTRACT(MINUTE FROM {source_sql}) * -1 MINUTE TO "
                f"DATEADD(EXTRACT(SECOND FROM {source_sql}) * -1 SECOND TO {source_sql}))"
            )
        elif expr.field.value == "minute":
            sql = f"DATEADD(EXTRACT(SECOND FROM {source_sql}) * -1 SECOND TO {source_sql})"
        elif expr.field.value == "second":
            sql = source_sql
        else:
            raise UnsupportedFeatureError(self.name, f"date_trunc({expr.field.value})")
        return self._apply_value_expression_modifiers(sql, source_params, expr)

    def format_interval_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        raise UnsupportedFeatureError(
            self.name,
            "standalone INTERVAL expression",
            "Use date_add() or date_sub() for Firebird date arithmetic.",
        )

    def format_datetime_add_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        value = expr.interval.value * 7 if unit == "WEEK" else expr.interval.value
        unit = "DAY" if unit == "WEEK" else unit
        sql = f"DATEADD(? {unit} TO {source_sql})"
        return self._apply_value_expression_modifiers(sql, (value,) + source_params, expr)

    def format_datetime_subtract_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        source_sql, source_params = expr.source.to_sql()
        unit = expr.interval.unit.value.upper()
        value = expr.interval.value * 7 if unit == "WEEK" else expr.interval.value
        unit = "DAY" if unit == "WEEK" else unit
        sql = f"DATEADD(? {unit} TO {source_sql})"
        return self._apply_value_expression_modifiers(sql, (-value,) + source_params, expr)

    def format_datetime_diff_expression(self, expr: "Any") -> Tuple[str, Tuple]:
        start_sql, start_params = expr.start.to_sql()
        end_sql, end_params = expr.end.to_sql()
        unit = "DAY" if expr.unit.value == "week" else expr.unit.value.upper()
        sql = f"DATEDIFF({unit} FROM {start_sql} TO {end_sql})"
        if expr.unit.value == "week":
            sql = f"({sql} / 7)"
        return self._apply_value_expression_modifiers(sql, start_params + end_params, expr)

    def supports_collate_expression(self) -> bool:
        """Firebird supports expression-level COLLATE."""
        return True

    def validate_collation_name(self, expr: "CollateExpression") -> str:
        """Validate Firebird collation names and return their SQL representation."""
        if expr.collation_options:
            unsupported = ", ".join(sorted(expr.collation_options))
            raise UnsupportedFeatureError(self.name, f"COLLATE options: {unsupported}")
        return validate_firebird_collation_name(expr.collation_name, getattr(self, "version", None))

    def format_identifier(self, identifier: str) -> str:
        """Format identifier using Firebird's double-quote quoting.

        Firebird by default folds identifiers to uppercase unless quoted.
        This uppercases the identifier so that quoted and unquoted references
        are consistent with Firebird's default behavior.
        """
        escaped = identifier.upper().replace('"', '""')
        return f'"{escaped}"'

    # region Version-based feature detection

    def supports_basic_cte(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_recursive_cte(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_materialized_cte(self) -> bool:
        return False

    def supports_window_functions(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_window_frame_clause(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_returning_insert(self) -> bool:
        return True

    def supports_returning_update(self) -> bool:
        return True

    def supports_returning_delete(self) -> bool:
        return True

    def supports_json_type(self) -> bool:
        return False

    def supports_json_table(self) -> bool:
        return False

    def supports_filter_clause(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_intersect(self) -> bool:
        return True

    def supports_except(self) -> bool:
        return True

    def supports_sequence(self) -> bool:
        return True

    def supports_create_sequence(self) -> bool:
        return True

    def supports_alter_sequence(self) -> bool:
        return True

    def supports_upsert(self) -> bool:
        return True

    def get_upsert_syntax_type(self) -> str:
        return "UPDATE OR INSERT"

    def supports_explain_analyze(self) -> bool:
        return False

    def supports_explain_format(self, format_type: str) -> bool:
        return False

    def supports_rollup(self) -> bool:
        return True

    def supports_cube(self) -> bool:
        return False

    def supports_grouping_sets(self) -> bool:
        return False

    def supports_array_type(self) -> bool:
        return True

    def supports_array_constructor(self) -> bool:
        return False

    def supports_array_access(self) -> bool:
        return False

    def supports_graph_match(self) -> bool:
        return False

    def supports_ordered_set_aggregation(self) -> bool:
        return False

    def supports_qualify_clause(self) -> bool:
        return False

    def supports_merge_statement(self) -> bool:
        return True

    def supports_for_update_skip_locked(self) -> bool:
        return self.version >= (4, 0, 0)

    def supports_lateral_join(self) -> bool:
        return False

    def supports_ilike(self) -> bool:
        return False

    def supports_temporal_tables(self) -> bool:
        return False

    # endregion

    # region Firebird protocol implementations

    def supports_update_or_insert(self) -> bool:
        return True

    def supports_returning(self) -> bool:
        return True

    def supports_merge(self) -> bool:
        return True

    def supports_execute_block(self) -> bool:
        return True

    def supports_create_sequence(self) -> bool:
        return True

    def supports_create_generator(self) -> bool:
        return True

    def supports_alter_sequence(self) -> bool:
        return True

    def supports_blob(self) -> bool:
        return True

    def supports_blob_sub_type(self, sub_type: int) -> bool:
        return sub_type in (0, 1, 2, 3, 4, 5)

    def supports_for_update_with_lock(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_skip_locked(self) -> bool:
        return self.version >= (4, 0, 0)

    def supports_snapshot_isolation(self) -> bool:
        return True

    def supports_table_stability(self) -> bool:
        return True

    def supports_wait_option(self) -> bool:
        return True

    def supports_lock_timeout(self) -> bool:
        return True

    def supports_computed_by(self) -> bool:
        return True

    def supports_generated_always(self) -> bool:
        return True

    def supports_identity_columns(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_external_file(self) -> bool:
        return True

    def supports_trigger_position(self) -> bool:
        return True

    def supports_returning_into(self) -> bool:
        return True

    def supports_mon_tables(self) -> bool:
        return True

    def supports_explain_plan(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_list_function(self) -> bool:
        return True

    def supports_replace_function(self) -> bool:
        return True

    def supports_position_function(self) -> bool:
        return True

    def supports_char_length_function(self) -> bool:
        return True

    def supports_bit_functions(self) -> bool:
        return True

    def supports_date_time_functions(self) -> bool:
        return True

    def supports_string_functions(self) -> bool:
        return True

    def supports_gen_uid(self) -> bool:
        return True

    def supports_boolean_type(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_decfloat(self) -> bool:
        return self.version >= (4, 0, 0)

    def supports_rows_syntax(self) -> bool:
        return True

    def supports_offset_fetch(self) -> bool:
        return self.version >= (4, 0, 0)

    def supports_database_triggers(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_window_functions(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_cte(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_recursive_cte(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_fulltext_index(self) -> bool:
        return False

    def supports_udf(self) -> bool:
        return True

    def supports_declare_external_function(self) -> bool:
        return True

    def supports_packages(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_create_package(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_create_package_body(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_global_temporary_table(self) -> bool:
        return True

    def supports_on_commit_delete_rows(self) -> bool:
        return True

    def supports_on_commit_preserve_rows(self) -> bool:
        return True

    def supports_monitoring(self) -> bool:
        return True

    def supports_roles(self) -> bool:
        return True

    def supports_create_role(self) -> bool:
        return True

    def supports_autonomous_transaction(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_for_cursor(self) -> bool:
        return True

    def supports_as_cursor(self) -> bool:
        return self.version >= (3, 0, 0)

    def supports_collation(self) -> bool:
        return True

    def supports_character_set(self) -> bool:
        return True

    def supports_exception(self) -> bool:
        return True

    def supports_create_exception(self) -> bool:
        return True

    def supports_context_variables(self) -> bool:
        return True

    # endregion

    # region Unsupported feature formatting

    def format_array_expression(self, _expr: "bases.BaseExpression") -> Tuple[str, Tuple]:
        raise UnsupportedFeatureError(self.name, "Array operations", _SUGGESTION_ARRAY)

    def format_match_clause(self, _clause) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(self.name, "graph MATCH clause", _SUGGESTION_GRAPH_MATCH)

    def format_ordered_set_aggregation(self, _aggregation) -> Tuple[str, Tuple]:
        raise UnsupportedFeatureError(self.name, "ordered-set aggregate functions", _SUGGESTION_ORDERED_SET_AGG)

    def format_qualify_clause(self, clause) -> Tuple[str, tuple]:
        raise UnsupportedFeatureError(self.name, "QUALIFY clause", _SUGGESTION_QUALIFY)

    # endregion

    # region DDL Support

    def supports_create_table(self) -> bool:
        return True

    def supports_drop_table(self) -> bool:
        return True

    def supports_alter_table(self) -> bool:
        return True

    def supports_temporary_table(self) -> bool:
        return True

    def supports_if_not_exists_table(self) -> bool:
        return False

    def supports_if_exists_table(self) -> bool:
        return False

    def supports_rename_table(self) -> bool:
        return True

    def supports_rename_column(self) -> bool:
        return True

    def supports_drop_column(self) -> bool:
        return True

    def supports_table_partitioning(self) -> bool:
        return False

    def supports_table_tablespace(self) -> bool:
        return False

    def supports_create_index(self) -> bool:
        return True

    def supports_drop_index(self) -> bool:
        return True

    def supports_unique_index(self) -> bool:
        return True

    def supports_index_if_exists(self) -> bool:
        return False

    def supports_index_if_not_exists(self) -> bool:
        return False

    def supports_partial_index(self) -> bool:
        return False

    def supports_functional_index(self) -> bool:
        return True

    def supports_concurrent_index(self) -> bool:
        return False

    def supports_index_type(self) -> bool:
        return False

    def supports_index_tablespace(self) -> bool:
        return False

    def supports_fulltext_index(self) -> bool:
        return False

    def supports_fulltext_boolean_mode(self) -> bool:
        return False

    def supports_fulltext_parser(self) -> bool:
        return False

    def supports_fulltext_query_expansion(self) -> bool:
        return False

    def supports_index_include(self) -> bool:
        return False

    def supports_generated_columns(self) -> bool:
        return True

    def supports_stored_generated_columns(self) -> bool:
        return False

    def supports_virtual_generated_columns(self) -> bool:
        return False

    def supports_truncate(self) -> bool:
        return True

    def supports_truncate_table_keyword(self) -> bool:
        return True

    def supports_truncate_restart_identity(self) -> bool:
        return False

    def supports_truncate_cascade(self) -> bool:
        return False

    def supports_create_view(self) -> bool:
        return True

    def supports_drop_view(self) -> bool:
        return True

    def supports_or_replace_view(self) -> bool:
        return True

    def supports_temporary_view(self) -> bool:
        return False

    def supports_materialized_view(self) -> bool:
        return False

    def supports_if_exists_view(self) -> bool:
        return False

    def supports_view_check_option(self) -> bool:
        return True

    def supports_cascade_view(self) -> bool:
        return True

    def supports_trigger(self) -> bool:
        return True

    def supports_create_trigger(self) -> bool:
        return True

    def supports_drop_trigger(self) -> bool:
        return True

    def supports_instead_of_trigger(self) -> bool:
        return True

    def supports_statement_trigger(self) -> bool:
        return False

    def supports_trigger_referencing(self) -> bool:
        return True

    def supports_trigger_when(self) -> bool:
        return True

    def supports_trigger_if_not_exists(self) -> bool:
        return False

    def supports_create_schema(self) -> bool:
        return False

    def supports_drop_schema(self) -> bool:
        return False

    def supports_function(self) -> bool:
        return True

    def supports_create_function(self) -> bool:
        return True

    def supports_drop_function(self) -> bool:
        return True

    def supports_function_or_replace(self) -> bool:
        return True

    def supports_function_parameters(self) -> bool:
        return True

    # endregion

    # region ConstraintSupport

    def supports_primary_key_constraint(self) -> bool:
        return True

    def supports_unique_constraint(self) -> bool:
        return True

    def supports_not_null_constraint(self) -> bool:
        return True

    def supports_check_constraint(self) -> bool:
        return True

    def supports_foreign_key_constraint(self) -> bool:
        return True

    def supports_fk_on_delete(self) -> bool:
        return True

    def supports_fk_on_update(self) -> bool:
        return True

    def supports_fk_match(self) -> bool:
        return False

    def supports_deferrable_constraint(self) -> bool:
        return False

    def supports_constraint_enforced(self) -> bool:
        return True

    def supports_add_constraint(self) -> bool:
        return True

    def supports_drop_constraint(self) -> bool:
        return True

    # endregion

    # region TransactionControlSupport

    def supports_transaction_mode(self) -> bool:
        return True

    def supports_isolation_level_in_begin(self) -> bool:
        return True

    def supports_read_only_transaction(self) -> bool:
        return True

    def supports_deferrable_transaction(self) -> bool:
        return False

    def supports_savepoint(self) -> bool:
        return True

    def format_begin_transaction(self, expr) -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.transaction import IsolationLevel
        level_map = {
            IsolationLevel.READ_UNCOMMITTED: "READ COMMITTED",
            IsolationLevel.READ_COMMITTED: "READ COMMITTED",
            IsolationLevel.REPEATABLE_READ: "SNAPSHOT",
            IsolationLevel.SERIALIZABLE: "SNAPSHOT TABLE STABILITY",
        }

        parts = ["SET TRANSACTION"]
        if expr._isolation_level is not None:
            fb_level = level_map.get(expr._isolation_level, "READ COMMITTED")
            parts.append(f"ISOLATION LEVEL {fb_level}")

        from rhosocial.activerecord.backend.transaction import TransactionMode
        if expr._mode == TransactionMode.READ_ONLY:
            parts.append("READ ONLY")
        elif expr._mode == TransactionMode.READ_WRITE:
            parts.append("READ WRITE")
        else:
            parts.append("READ WRITE")

        parts.append("WAIT")
        return " ".join(parts), ()

    def format_set_transaction(self, expr) -> Tuple[str, tuple]:
        from rhosocial.activerecord.backend.transaction import IsolationLevel, TransactionMode

        parts = ["SET TRANSACTION"]
        if expr._isolation_level is not None:
            level_map = {
                IsolationLevel.READ_UNCOMMITTED: "READ COMMITTED",
                IsolationLevel.READ_COMMITTED: "READ COMMITTED",
                IsolationLevel.REPEATABLE_READ: "SNAPSHOT",
                IsolationLevel.SERIALIZABLE: "SNAPSHOT TABLE STABILITY",
            }
            fb_level = level_map.get(expr._isolation_level, "READ COMMITTED")
            parts.append(f"ISOLATION LEVEL {fb_level}")
        if expr._mode == TransactionMode.READ_ONLY:
            parts.append("READ ONLY")
        elif expr._mode == TransactionMode.READ_WRITE:
            parts.append("READ WRITE")
        return " ".join(parts), ()

    # endregion

    # region Explain

    def format_explain_statement(self, expr) -> Tuple[str, tuple]:
        statement_sql, statement_params = expr.statement.to_sql()
        return f"EXPLAIN PLAN FOR {statement_sql}", statement_params

    # endregion

    # region Function support

    _FIREBIRD_FUNCTION_VERSIONS = {
        "gen_uuid": ((2, 5, 0), None),
        "uuid_to_char": ((3, 0, 0), None),
        "char_to_uuid": ((3, 0, 0), None),
        "list": ((2, 5, 0), None),
        "dateadd": ((2, 5, 0), None),
        "datediff": ((2, 5, 0), None),
        "replace": ((2, 5, 0), None),
        "position": ((2, 5, 0), None),
        "iif": ((2, 5, 0), None),
        "decode": ((2, 5, 0), None),
        "lpad": ((2, 5, 0), None),
        "rpad": ((2, 5, 0), None),
    }

    def supports_functions(self) -> Dict[str, bool]:
        from rhosocial.activerecord.backend.expression.functions import __all__ as core_functions
        expression_constructors = {
            "xmlagg",
            "xmlattributes",
            "xmlcomment",
            "xmlconcat",
            "xmlelement",
            "xmlexists",
            "xmlforest",
            "xmlparse",
            "xmlpi",
            "xmlquery",
            "xmlroot",
            "xmlserialize",
            "xmltable",
        }
        result = {}
        for func_name in core_functions:
            if func_name not in expression_constructors:
                result[func_name] = True
        for func_name, (min_ver, max_ver) in self._FIREBIRD_FUNCTION_VERSIONS.items():
            result[func_name] = self._is_firebird_function_supported(func_name)
        return result

    def _is_firebird_function_supported(self, func_name: str) -> bool:
        version_range = self._FIREBIRD_FUNCTION_VERSIONS.get(func_name)
        if version_range is None:
            return True
        min_version, max_version = version_range
        if min_version is not None and self.version < min_version:
            return False
        if max_version is not None and self.version > max_version:
            return False
        return True

    # endregion

    # region Pagination

    def format_limit_offset(self, limit: Optional[int] = None,
                             offset: Optional[int] = None) -> Tuple[str, tuple]:
        """Format LIMIT/OFFSET for Firebird.

        Firebird 2.5+: ROWS m TO n
        Firebird 4.0+: OFFSET m ROWS FETCH NEXT n ROWS ONLY
        """
        if limit is None and offset is None:
            return "", ()

        if self.version >= (4, 0, 0):
            parts = []
            if offset is not None and offset > 0:
                parts.append(f"OFFSET {offset} ROWS")
            if limit is not None:
                parts.append(f"FETCH NEXT {limit} ROWS ONLY")
            return " ".join(parts), ()
        else:
            if limit is not None:
                if offset is not None and offset > 0:
                    return f"ROWS {offset + 1} TO {offset + limit}", ()
                return f"ROWS 1 TO {limit}", ()
            if offset is not None and offset > 0:
                return f"ROWS {offset + 1} TO {999999999}", ()
            return "", ()

    # endregion

    # region Returning clause

    def format_returning_clause(self, clause: "ReturningClause") -> Tuple[str, tuple]:
        all_params = []
        expr_parts = []
        for expr in clause.expressions:
            expr_sql, expr_params = expr.to_sql()
            expr_parts.append(expr_sql)
            all_params.extend(expr_params)
        returning_sql = f"RETURNING {', '.join(expr_parts)}"
        return returning_sql, tuple(all_params)

    # endregion

    # region Generator/Sequence formatting

    def format_gen_id(self, generator_name: str, step: int = 1) -> Tuple[str, tuple]:
        return f"GEN_ID({self.format_identifier(generator_name)}, {step})", ()

    def format_next_value_for(self, sequence_name: str) -> Tuple[str, tuple]:
        return f"NEXT VALUE FOR {self.format_identifier(sequence_name)}", ()

    # endregion

    # region Blob formatting

    def format_blob_literal(self, value: bytes, sub_type: int = 0) -> Tuple[str, tuple]:
        escaped = value.hex()
        return f"X'{escaped}'", ()

    # endregion

    # region DML overrides

    def format_insert_statement(self, expr) -> Tuple[str, tuple]:
        return FirebirdDMLOperationMixin.format_insert_statement(self, expr)

    def format_update_statement(self, expr) -> Tuple[str, tuple]:
        return FirebirdDMLOperationMixin.format_update_statement(self, expr)

    def format_delete_statement(self, expr) -> Tuple[str, tuple]:
        return FirebirdDMLOperationMixin.format_delete_statement(self, expr)

    def format_limit_offset_clause(self, clause) -> Tuple[str, tuple]:
        """Format LIMIT/OFFSET clause for Firebird using ROWS/FETCH syntax."""
        all_params = []
        if clause.limit is None and clause.offset is None:
            return "", ()

        if self.version >= (4, 0, 0):
            parts = []
            if clause.offset is not None:
                parts.append(f"OFFSET {clause.offset} ROWS")
            if clause.limit is not None:
                parts.append(f"FETCH NEXT {clause.limit} ROWS ONLY")
            return " ".join(parts), tuple(all_params)
        else:
            limit = clause.limit or 999999999
            if clause.offset is not None and clause.offset > 0:
                return f"ROWS {clause.offset + 1} TO {clause.offset + limit}", tuple(all_params)
            return f"ROWS 1 TO {limit}", tuple(all_params)

    # endregion

    # region CREATE TABLE override

    def format_create_table_statement(self, expr: "CreateTableExpression") -> Tuple[str, tuple]:
        return FirebirdTableMixin.format_create_table_statement(self, expr)

    def _format_column_definition_firebird(self, col_def) -> Tuple[str, List[Any]]:
        return FirebirdTableMixin._format_column_definition_firebird(self, col_def)

    def _format_table_constraint_firebird(self, t_const) -> Tuple[str, List[Any]]:
        return FirebirdTableMixin._format_table_constraint_firebird(self, t_const)

    # endregion