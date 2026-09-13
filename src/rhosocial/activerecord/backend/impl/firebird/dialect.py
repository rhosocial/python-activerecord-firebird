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

from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

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
    TableMixin,
    ConstraintMixin,
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
from .reserved_words import FIREBIRD_RESERVED_WORDS
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
    FirebirdDomainMixin,
    FirebirdExceptionMixin,
    FirebirdRoutineMixin,
    FirebirdPackageMixin,
    FirebirdExternalFunctionMixin,
    FirebirdRoleMixin,
    FirebirdUserMixin,
    FirebirdCommentMixin,
    FirebirdDatabaseMixin,
    FirebirdTransactionMixin,
    FirebirdExpressionMixin,
    FirebirdWindowFunctionMixin,
    FirebirdDateTimeMixin,
    FirebirdDQLMixin,
    FirebirdCollationMixin,
    FirebirdIdentifierMixin,
    FirebirdCTEMixin,
    FirebirdReturningMixin,
    FirebirdFilterClauseMixin,
    FirebirdUpsertMixin,
    FirebirdGroupingMixin,
    FirebirdArrayMixin,
    FirebirdExplainMixin,
    FirebirdGeneratedColumnMixin,
    FirebirdFunctionMixin,
    FirebirdTruncateMixin,
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
    PredicateMixin,
    ExpressionMixin,
    DateTimeMixin,
    DQLMixin,
    FirebirdAlterTableModifierMixin,  # Before DDLColumnMixin to override format_*_action
    DDLColumnMixin,
    TransactionControlMixin,
    # Firebird-specific overrides (before generic mixins to take precedence)
    FirebirdDMLOperationMixin,  # Must be before DMLMixin
    FirebirdLockingMixin,       # Must be before LockingMixin
    FirebirdTableMixin,         # Must be before TableMixin
    TableMixin,
    ConstraintMixin,
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
    FirebirdTransactionMixin,
    # New Firebird-specific mixins (before generic mixins to take precedence)
    FirebirdExpressionMixin,    # Must be before ExpressionMixin
    FirebirdWindowFunctionMixin, # Must be before WindowFunctionMixin
    FirebirdDateTimeMixin,      # Must be before DateTimeMixin
    FirebirdDQLMixin,           # Must be before DQLMixin
    FirebirdCollationMixin,     # Must be before CollationMixin
    FirebirdIdentifierMixin,    # Must be before IdentifierMixin
    FirebirdCTEMixin,           # Must be before CTEMixin
    FirebirdReturningMixin,     # Must be before ReturningMixin
    FirebirdFilterClauseMixin,  # Must be before FilterClauseMixin
    FirebirdUpsertMixin,        # Must be before UpsertMixin
    FirebirdGroupingMixin,      # Must be before AdvancedGroupingMixin
    FirebirdArrayMixin,         # Must be before ArrayMixin
    FirebirdExplainMixin,       # Must be before ExplainMixin
    FirebirdGeneratedColumnMixin, # Must be before GeneratedColumnMixin
    FirebirdFunctionMixin,      # Must be before FunctionMixin
    FirebirdTruncateMixin,      # Must be before TruncateMixin
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
        self._reserved_words = FIREBIRD_RESERVED_WORDS
        if version is not None:
            self.version = version

    # region Version-based feature detection

    def supports_window_functions(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_window_frame_clause(self) -> bool:
        return _norm_version(self.version) >= (3, 0, 0)

    def supports_merge_statement(self) -> bool:
        return True

    def supports_for_update_skip_locked(self) -> bool:
        return self.supports_skip_locked()

    def supports_lateral_join(self) -> bool:
        """Firebird 4.0 introduced joins with LATERAL derived tables."""
        return _norm_version(self.version) >= (4, 0, 0)



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

    def supports_for_update(self) -> bool:
        """C3 re-bind: DQLMixin precedes FirebirdLockingMixin in the base
        list, so its empty ``supports_for_update()`` stub would shadow the
        concrete FB3+ gate; delegate to the locking mixin explicitly."""
        return FirebirdLockingMixin.supports_for_update(self)

    def supports_snapshot_isolation(self) -> bool:
        return True

    def supports_table_stability(self) -> bool:
        return True

    def supports_wait_option(self) -> bool:
        return True

    def supports_lock_timeout(self) -> bool:
        return True

    # FirebirdTableMixin overrides the table/column formatters, but it is
    # composed after DDLColumnMixin/TableMixin in the MRO; bridge explicitly
    # so the Firebird implementations (e.g. IDENTITY auto-increment) win.
    def format_create_table_statement(self, expr) -> Tuple[str, tuple]:
        return FirebirdTableMixin.format_create_table_statement(self, expr)

    def format_column_definition(self, col_def) -> Tuple[str, tuple]:
        return FirebirdTableMixin.format_column_definition(self, col_def)

    def format_table_constraint(self, expr) -> Tuple[str, tuple]:
        return FirebirdTableMixin.format_table_constraint(self, expr)

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



    def supports_context_variables(self) -> bool:
        return True

    # endregion

    # region Unsupported feature formatting

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


    def supports_table_tablespace(self) -> bool:
        return False

    def supports_create_index(self) -> bool:
        return True

    def supports_drop_index(self) -> bool:
        return True

    def supports_unique_index(self) -> bool:
        return True




    def supports_functional_index(self) -> bool:
        return True








    def supports_generated_columns(self) -> bool:
        return True









    def supports_or_replace_view(self) -> bool:
        return True




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