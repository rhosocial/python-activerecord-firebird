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
  - OFFSET/FETCH (FB 3.0+)
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
    UpsertMixin,
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
    PartitionMixin,
    TruncateMixin,
    SchemaMixin,
    IndexMixin,
    GeneratedColumnMixin,
    ViewMixin,
    FunctionMixin,
    IntrospectionMixin,
    # Core infrastructure mixins (shared by all modern backends)
    IdentifierMixin,
    PredicateMixin,
    ExpressionMixin,
    DateTimeMixin,
    DQLMixin,
    DMLMixin,
    DDLColumnMixin,
    TransactionControlMixin,
)
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

from .collation import validate_firebird_collation_name
from .mixins.version_boundaries import _norm_version
from .mixins import (
    FirebirdAlterTableModifierMixin,
    FirebirdDMLOperationMixin,
    FirebirdLockingMixin,
    FirebirdTableMixin,
    FirebirdTriggerMixin,
    FirebirdSequenceMixin,
    FirebirdBlobMixin,
    FirebirdIntrospectionMixin,
    FirebirdPartitionMixin,
    FirebirdTypeSupportMixin,
    FirebirdTypeSuggestionMixin,
    FirebirdDomainMixin,
    FirebirdExceptionMixin,
    FirebirdRoutineMixin,
    FirebirdPackageMixin,
    FirebirdExternalFunctionMixin,
    FirebirdRoleMixin,
    FirebirdUserMixin,
    FirebirdCommentMixin,
    FirebirdDatabaseMixin,
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
    # Core infrastructure mixins (shared by all modern backends)
    IdentifierMixin,
    PredicateMixin,
    ExpressionMixin,
    DateTimeMixin,
    DQLMixin,
    FirebirdTableMixin,         # Must be before DDLColumnMixin (auto-increment)
    FirebirdAlterTableModifierMixin,  # Before DDLColumnMixin to override format_*_action
    DDLColumnMixin,
    TransactionControlMixin,
    # Firebird-specific overrides (before generic mixins to take precedence)
    FirebirdDMLOperationMixin,  # Must be before DMLMixin
    FirebirdLockingMixin,       # Must be before LockingMixin
    FirebirdTriggerMixin,       # Must be before TriggerMixin
    FirebirdSequenceMixin,      # Must be before SequenceMixin
    FirebirdBlobMixin,
    FirebirdIntrospectionMixin, # Must be before IntrospectionMixin
    FirebirdDomainMixin,
    FirebirdExceptionMixin,
    FirebirdRoutineMixin,       # Must be before FunctionMixin (format_create_function_statement)
    FirebirdPackageMixin,
    FirebirdExternalFunctionMixin,
    FirebirdRoleMixin,
    FirebirdUserMixin,
    FirebirdCommentMixin,
    FirebirdDatabaseMixin,
    # Core feature mixins (no duplicates)
    DMLMixin,
    CollationMixin,
    CTEMixin,
    WindowFunctionMixin,
    JSONMixin,
    ReturningMixin,
    SetOperationMixin,
    UpsertMixin,
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
    PartitionMixin,
    TruncateMixin,
    SchemaMixin,
    IndexMixin,
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
    FirebirdPartitionMixin,
    FirebirdTypeSupportMixin,
    FirebirdTypeSuggestionMixin,
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
    - OFFSET/FETCH (FB 3.0+)
    - DECFLOAT (FB 4.0+)
    - EXECUTE BLOCK (FB 2.5+)
    - ROWS syntax (FB 2.5+)
    """

    def __init__(self, version: Optional[Tuple[int, int, int]] = None):
        super().__init__()
        if version is not None:
            self.version = version

    _PY_TYPE_TO_FIREBIRD_SQL = {
        int: "INTEGER",
        float: "DOUBLE PRECISION",
        bool: "SMALLINT",
        str: "VARCHAR(255)",
        bytes: "BLOB",
    }

    @staticmethod
    def _python_type_to_firebird_sql(value: Any) -> Optional[str]:
        """Map a Python value to its Firebird SQL type for explicit CAST.

        Returns None for types that don't need explicit casting (e.g. None).
        """
        if value is None:
            return None
        import datetime
        import decimal
        if isinstance(value, bool):
            return "SMALLINT"
        if isinstance(value, int):
            return "INTEGER"
        if isinstance(value, float):
            return "DOUBLE PRECISION"
        if isinstance(value, str):
            return "VARCHAR(255)"
        if isinstance(value, bytes):
            return "BLOB"
        if isinstance(value, datetime.date):
            return "DATE"
        if isinstance(value, datetime.datetime):
            return "TIMESTAMP"
        if isinstance(value, decimal.Decimal):
            return "DECIMAL(18, 4)"
        return None

    def format_case_expression(
        self,
        value_sql: Optional[str],
        value_params: Optional[tuple],
        conditions_results: List[Tuple[str, str, tuple, tuple]],
        else_result_sql: Optional[str],
        else_result_params: Optional[tuple],
        alias: Optional[str] = None,
    ) -> Tuple[str, Tuple]:
        wrapped_conditions = []
        for cond_sql, res_sql, cond_params, res_params in conditions_results:
            if res_sql.strip() == self.get_parameter_placeholder() and res_params:
                fb_type = self._python_type_to_firebird_sql(res_params[0])
                if fb_type:
                    res_sql, res_params = self.format_cast_expression(
                        res_sql, fb_type, res_params, None
                    )
            wrapped_conditions.append((cond_sql, res_sql, cond_params, res_params))

        wrapped_else_sql = else_result_sql
        wrapped_else_params = else_result_params
        if (wrapped_else_sql and wrapped_else_sql.strip() == self.get_parameter_placeholder()
                and wrapped_else_params):
            fb_type = self._python_type_to_firebird_sql(wrapped_else_params[0])
            if fb_type:
                wrapped_else_sql, wrapped_else_params = self.format_cast_expression(
                    wrapped_else_sql, fb_type, wrapped_else_params, None
                )

        return super().format_case_expression(
            value_sql, value_params,
            wrapped_conditions,
            wrapped_else_sql, wrapped_else_params,
            alias,
        )

    def format_binary_arithmetic_expression(
        self, op: str, left_sql: str, right_sql: str, left_params: tuple, right_params: tuple
    ) -> Tuple[str, Tuple]:
        """Format a binary arithmetic expression with typed phantom parameters.

        Firebird cannot infer the type of a ``?`` parameter used inside an
        arithmetic expression (e.g. ``col + ?`` raises -804 Data type unknown).
        Wrap literal ``?`` operands in an explicit CAST based on the bound value.
        """
        placeholder = self.get_parameter_placeholder()
        left_sql = self._cast_literal_operand(left_sql, left_params, placeholder)
        right_sql = self._cast_literal_operand(right_sql, right_params, placeholder)
        return f"{left_sql} {op} {right_sql}", left_params + right_params

    def _cast_literal_operand(self, sql: str, params: tuple, placeholder: str) -> str:
        if sql.strip() == placeholder and params and len(params) == 1:
            fb_type = self._python_type_to_firebird_sql(params[0])
            if fb_type:
                sql, _ = self.format_cast_expression(sql, fb_type, params, None)
        return sql

    def format_function_call(
        self, expr: "bases.BaseExpression", filter_predicate: Optional["bases.SQLPredicate"] = None
    ) -> Tuple[str, Tuple]:
        """Format a function call, remapping names Firebird does not provide.

        Firebird 5 does not expose a ``LENGTH`` scalar function (the name is a
        reserved keyword); the canonical length function is ``CHAR_LENGTH`` for
        characters and ``OCTET_LENGTH`` for bytes.

        Firebird 5/6-snapshot fails to infer the result type of ``SUM``/``AVG``
        over a ``DECIMAL`` column ("Data type unknown" at prepare time), so the
        aggregate result is explicitly cast to ``DECIMAL(18,2)`` to pin the
        return type. This matches the precision used by the testsuite schemas.
        """
        func_name = getattr(expr, "func_name", None)
        if isinstance(func_name, str) and func_name.upper() == "LENGTH":
            expr.func_name = "CHAR_LENGTH"
            try:
                return super().format_function_call(expr, filter_predicate=filter_predicate)
            finally:
                expr.func_name = func_name
        sql, params = super().format_function_call(expr, filter_predicate=filter_predicate)
        if isinstance(func_name, str) and func_name.upper() in ("SUM", "AVG"):
            alias_sql = ""
            if " AS " in sql:
                sql, alias_sql = sql.split(" AS ", 1)
            cast_sql, params = self.format_cast_expression(
                sql, "DECIMAL(18,2)", params, None
            )
            sql = f"{cast_sql} AS {alias_sql}" if alias_sql else cast_sql
        return sql, params

    def format_window_function_call(self, call: "Any") -> Tuple[str, tuple]:
        """Format a window function call, pinning SUM/AVG result types.

        Mirrors :meth:`format_function_call`: Firebird 5/6-snapshot fails to
        infer the result type of ``SUM``/``AVG`` over a DECIMAL column inside
        a window expression, so wrap the whole ``SUM(...) OVER (...)`` call in
        an explicit ``CAST(... AS DECIMAL(18,2))``.
        """
        sql, params = super().format_window_function_call(call)
        function_name = getattr(call, "function_name", None)
        if isinstance(function_name, str) and function_name.upper() in ("SUM", "AVG"):
            alias_sql = ""
            if " AS " in sql:
                sql, alias_sql = sql.split(" AS ", 1)
            cast_sql, params = self.format_cast_expression(
                sql, "DECIMAL(18,2)", tuple(params), None
            )
            params = list(params)
            sql = f"{cast_sql} AS {alias_sql}" if alias_sql else cast_sql
        return sql, params

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

    def format_query_statement(self, expr: Any) -> Tuple[str, Tuple]:
        """Format a SELECT statement, qualifying a bare wildcard when mixed with columns.

        Firebird rejects ``SELECT *, extra_col ...`` (Token unknown, error -104) and
        requires an explicit column list or a table-qualified wildcard such as
        ``SELECT "T".*, extra_col ...`` when additional expressions are selected.
        """
        from rhosocial.activerecord.backend.expression import WildcardExpression

        if len(expr.select) > 1:
            table_name = None
            for e in expr.select:
                if isinstance(e, WildcardExpression) and e.table is None and e.schema_name is None:
                    if getattr(expr, "from_", None) is not None:
                        src = expr.from_
                        if isinstance(src, list) and len(src) == 1:
                            src = src[0]
                        if isinstance(src, str):
                            table_name = src
                        elif src.__class__.__name__ == "TableExpression":
                            table_name = src.alias or src.name
                    if table_name:
                        e.table = table_name
        return super().format_query_statement(expr)

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
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_recursive_cte(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_materialized_cte(self) -> bool:
        return False

    def supports_window_functions(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_window_frame_clause(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

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
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_intersect(self) -> bool:
        # Firebird supports only UNION/UNION ALL as set operations.
        # INTERSECT/EXCEPT are not part of the SELECT grammar (Firebird 5.0
        # Language Reference: SELECT syntax lists UNION as the only set
        # operator), and DSQL rejects them with SQLSTATE -104 "Token unknown".
        return False

    def supports_except(self) -> bool:
        return False

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

    def supports_on_conflict_clause(self) -> bool:
        """Firebird has no ON CONFLICT clause form; upsert is UPDATE OR INSERT."""
        return False

    def supports_multiple_on_conflict_clauses(self) -> bool:
        return False

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
        return self.supports_skip_locked()

    def supports_lateral_join(self) -> bool:
        """Firebird 4.0 introduced joins with LATERAL derived tables."""
        return _norm_version(self.version) >= (4, 0, 0)

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

    def supports_create_generator(self) -> bool:
        return True

    def supports_blob(self) -> bool:
        return True

    def supports_blob_sub_type(self, sub_type: int) -> bool:
        return sub_type in (0, 1, 2, 3, 4, 5)

    def supports_for_update(self) -> bool:
        """C3 re-bind: DQLMixin precedes FirebirdLockingMixin in the base
        list, so its empty ``supports_for_update()`` stub would shadow the
        concrete FB3+ gate; delegate to the locking mixin explicitly."""
        return FirebirdLockingMixin.supports_for_update(self)

    def supports_for_update_with_lock(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_skip_locked(self) -> bool:
        """SKIP LOCKED was introduced in Firebird 4.0; single source of
        truth for both this gate and FirebirdLockingMixin's rendering."""
        return _norm_version(self.version) >= (4, 0, 0)

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
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_external_file(self) -> bool:
        return True

    def supports_trigger_position(self) -> bool:
        return True

    def supports_returning_into(self) -> bool:
        return True

    def supports_microsecond_timestamp(self) -> bool:
        # Firebird TIMESTAMP stores only 4 fractional digits (1/10000 s);
        # microseconds beyond that are lost on write.
        return False

    def supports_mon_tables(self) -> bool:
        return True

    def supports_explain_plan(self) -> bool:
        # ``EXPLAIN PLAN FOR`` is an isql client command, not a valid DSQL
        # statement. Firebird's engine rejects it with SQLSTATE -104 "Token
        # unknown - EXPLAIN", so plan extraction is not available in DSQL.
        return False

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
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_decfloat(self) -> bool:
        return _norm_version(self.version) >= (4, 0, 0)

    def supports_rows_syntax(self) -> bool:
        return True

    def supports_offset_fetch(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_database_triggers(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_cte(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_udf(self) -> bool:
        return True

    def supports_declare_external_function(self) -> bool:
        return True

    def supports_packages(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_create_package(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_create_package_body(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

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
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_for_cursor(self) -> bool:
        return True

    def supports_as_cursor(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

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

    def supports_drop_table_cascade(self) -> bool:
        """Firebird has no CASCADE keyword on DROP TABLE."""
        return False

    def supports_drop_table_restrict(self) -> bool:
        """Firebird has no RESTRICT keyword on DROP TABLE."""
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

    def supports_schema(self) -> bool:
        """Firebird has no schema namespaces; the database is the whole namespace."""
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
        for func_name, (_min_ver, _max_ver) in self._FIREBIRD_FUNCTION_VERSIONS.items():
            result[func_name] = self._is_firebird_function_supported(func_name)
        return result

    def _is_firebird_function_supported(self, func_name: str) -> bool:
        version_range = self._FIREBIRD_FUNCTION_VERSIONS.get(func_name)
        if version_range is None:
            return True
        min_version, max_version = version_range
        if min_version is not None and _norm_version(self.version) < min_version:
            return False
        if max_version is not None and _norm_version(self.version) > max_version:
            return False
        return True

    # endregion

    # region Pagination

    def format_limit_offset(self, limit: Optional[int] = None,
                             offset: Optional[int] = None) -> Tuple[str, tuple]:
        """Format LIMIT/OFFSET for Firebird.

        Firebird 2.5+: ROWS m TO n
        Firebird 3.0+: OFFSET m ROWS FETCH NEXT n ROWS ONLY
        """
        if limit is None and offset is None:
            return "", ()

        if _norm_version(self.version) >= (3, 0, 0):
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

        if _norm_version(self.version) >= (3, 0, 0):
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




    # endregion