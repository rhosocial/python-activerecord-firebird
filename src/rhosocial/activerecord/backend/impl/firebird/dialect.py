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

from typing import Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.base import SQLDialectBase
from rhosocial.activerecord.backend.dialect.protocols import (
    CollationSupport,
    CTESupport,
    WindowFunctionSupport,
    JSONSupport,
    ReturningSupport,
    SetOperationSupport,
    SequenceObjectSupport,
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
    TableObjectSupport,
    TruncateSupport,
    IndexObjectSupport,
    TriggerObjectSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TransactionControlSupport,
    GeneratedColumnSupport,
    IdentityColumnSupport,
    AutoIncrementColumnSupport,
    ViewObjectSupport,
    RoutineObjectSupport,
    CreateTableSupport,
    DropTableSupport,
    AlterTableSupport,
    CreateViewSupport,
    DropViewSupport,
    CreateIndexSupport,
    DropIndexSupport,
    CreateTriggerSupport,
    DropTriggerSupport,
    CreateRoutineSupport,
    DropRoutineSupport,
    CreateSequenceSupport,
    AlterSequenceSupport,
    DropSequenceSupport,
    CreateDomainSupport,
    AlterDomainSupport,
    DropDomainSupport,
    CreateTypeSupport,
    AlterTypeSupport,
    DropTypeSupport,
    TypeObjectSupport,
    CreateSchemaSupport,
    DropSchemaSupport,
    CommentSupport,
)
from rhosocial.activerecord.backend.dialect.mixins import (
    CollationMixin,
    NamespaceMixin,
    CTEMixin,
    WindowFunctionMixin,
    JSONMixin,
    SetOperationMixin,
    TableMixin,
    ConstraintMixin,
    UpsertMixin,
    ExplainMixin,
    JoinMixin,
    ILIKEMixin,

    ArrayMixin,
    LateralJoinMixin,
    MergeMixin,
    TemporalTableMixin,

    GraphMixin,
    PartitionMixin,
    TruncateMixin,
    SchemaMixin,
    IndexMixin,
    SequenceMixin,
    TriggerMixin,
    GeneratedColumnMixin,
    IdentityColumnMixin,
    AutoIncrementMixin,
    ViewMixin,
    FunctionMixin,
    IntrospectionMixin,
    # Object naming: one mixin per object kind the dialect can spell, plus the
    # NamespaceMixin they all reach through. See the note on the class bases.
    TableNameMixin,
    ViewNameMixin,
    IndexNameMixin,
    SequenceNameMixin,
    TriggerNameMixin,
    FunctionNameMixin,
    ProcedureNameMixin,
    DomainNameMixin,
    TypeNameMixin,
    DatabaseNameMixin,
    SchemaNameMixin,
    NamespaceMixin,
    # Core infrastructure mixins (shared by all modern backends)
    PredicateMixin,
    ExpressionMixin,
    DateTimeMixin,
    DQLMixin,
    DMLMixin,
    DDLColumnMixin,
    UserDefinedTypeMixin,
    TransactionControlMixin,
)

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
    FirebirdNamespaceMixin,
    FirebirdCTEMixin,
    FirebirdReturningMixin,
    FirebirdFilterClauseMixin,
    FirebirdUpsertMixin,
    FirebirdGroupingMixin,
    FirebirdArrayMixin,
    FirebirdExplainMixin,
    FirebirdGeneratedColumnMixin,
    FirebirdIdentityColumnMixin,
    FirebirdFunctionMixin,
    FirebirdTruncateMixin,
    FirebirdUnsupportedFeaturesMixin,
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
    FirebirdDomainSupport,
)

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements import (
        ColumnDefinition,
        TableConstraint,
    )

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
    # Firebird-specific mixins MUST precede their generic counterparts so that
    # the C3 linearization resolves the overrides to the Firebird versions.
    #
    # SQLDialectBase sits after every implementation mixin rather than first.
    # It defines ``format_identifier`` -- the one primitive Firebird overrides,
    # by upper-casing the identifier and doubling any inner quote -- and listed
    # first it would shadow FirebirdIdentifierMixin, forcing a second copy of
    # that method onto this class. It stays *before* the Protocol bases on
    # purpose: a runtime_checkable Protocol defines ``__init__``, so putting
    # SQLDialectBase after them would let ``super().__init__()`` land on a
    # Protocol and skip the base constructor entirely.
    FirebirdTransactionMixin,    # Before TransactionControlMixin
    FirebirdExpressionMixin,     # Before ExpressionMixin
    FirebirdWindowFunctionMixin, # Before WindowFunctionMixin
    FirebirdDateTimeMixin,       # Before DateTimeMixin
    FirebirdDQLMixin,            # Before DQLMixin
    FirebirdCollationMixin,      # Before CollationMixin
    FirebirdIdentifierMixin,     # Before IdentifierMixin
    FirebirdNamespaceMixin,      # Before RelationSourceMixin; spells one level, refuses the rest
    FirebirdCTEMixin,            # Before CTEMixin
    FirebirdReturningMixin,
    FirebirdFilterClauseMixin,   # Before FilterClauseMixin
    FirebirdUpsertMixin,         # Before UpsertMixin
    FirebirdGroupingMixin,       # Before AdvancedGroupingMixin
    FirebirdArrayMixin,          # Before ArrayMixin
    FirebirdExplainMixin,        # Before ExplainMixin
    FirebirdGeneratedColumnMixin, # Before GeneratedColumnMixin
    FirebirdIdentityColumnMixin, # Before IdentityColumnMixin and AutoIncrementMixin
    FirebirdFunctionMixin,       # Before FunctionMixin
    FirebirdTruncateMixin,       # Before TruncateMixin
    FirebirdUnsupportedFeaturesMixin,  # Before Array/Graph/OrderedSet/Qualify mixins
    # Core infrastructure mixins (shared by all modern backends)
    PredicateMixin,
    ExpressionMixin,
    DateTimeMixin,
    FirebirdLockingMixin,       # Before DQLMixin to override format_for_update_clause
    DQLMixin,
    FirebirdAlterTableModifierMixin,  # Before DDLColumnMixin to override format_*_action
    DDLColumnMixin,
    UserDefinedTypeMixin,
    TransactionControlMixin,
    # Firebird-specific overrides (before generic mixins to take precedence)
    FirebirdDMLOperationMixin,  # Must be before DMLMixin
    FirebirdTableMixin,         # Must be before TableMixin
    FirebirdCommentMixin,       # Must be before TableMixin (supports_comment_on/format_comment_statement)
    TableMixin,
    ConstraintMixin,
    FirebirdTriggerMixin,       # Must be before TriggerMixin
    TriggerMixin,
    FirebirdSequenceMixin,      # Must be before SequenceMixin
    SequenceMixin,
    FirebirdBlobMixin,
    FirebirdIntrospectionMixin, # Must be before IntrospectionMixin
    FirebirdDomainMixin,
    FirebirdExceptionMixin,
    FirebirdRoutineMixin,       # Must be before FunctionMixin (format_create_function_statement)
    FirebirdPackageMixin,
    FirebirdExternalFunctionMixin,
    FirebirdRoleMixin,
    FirebirdUserMixin,
    FirebirdDatabaseMixin,
    # Core feature mixins (no duplicates)
    DMLMixin,
    CollationMixin,
    CTEMixin,
    WindowFunctionMixin,
    JSONMixin,
    SetOperationMixin,
    UpsertMixin,
    ExplainMixin,
    JoinMixin,
    ILIKEMixin,

    ArrayMixin,
    LateralJoinMixin,
    MergeMixin,
    TemporalTableMixin,

    GraphMixin,
    PartitionMixin,
    TruncateMixin,
    SchemaMixin,
    IndexMixin,
    GeneratedColumnMixin,
    # The identity clause and the parameterless AUTO_INCREMENT marker are
    # separate mechanisms with separate protocols; Firebird declares the
    # identity formatter by inheriting IdentityColumnMixin and answers the
    # auto-increment marker through AutoIncrementMixin's False gate. Neither
    # renders SQL the server rejects: the identity probes are measured and the
    # marker is refused by name.
    IdentityColumnMixin,
    AutoIncrementMixin,
    ViewMixin,
    FunctionMixin,
    IntrospectionMixin,
    # Object naming, one mixin per object kind the dialect can spell, plus the
    # NamespaceMixin they all reach through.
    #
    # These have to *precede* the matching *ObjectSupport protocols further down
    # for the same reason FirebirdTableMixin re-binds
    # format_drop_table_statement: C3 resolves to whichever base comes first, so
    # a mixin listed after a Protocol loses to the Protocol's `...` stub and
    # every object renders as None. NamespaceMixin precedes NamespaceSupport for
    # the same reason -- without it the three naming switches return None rather
    # than False, and the core's validate_namespace reads None as "no
    # qualification", which happens to be Firebird's answer but by accident
    # rather than by decision. A test asserts the resolution rather than trusting
    # it.
    #
    # Firebird declares no materialized view, foreign table, synonym or property
    # graph, so those formatters are absent and a statement holding one is
    # refused rather than silently rendered.
    TableNameMixin,
    ViewNameMixin,
    IndexNameMixin,
    SequenceNameMixin,
    TriggerNameMixin,
    FunctionNameMixin,
    ProcedureNameMixin,
    DomainNameMixin,
    TypeNameMixin,
    DatabaseNameMixin,
    SchemaNameMixin,
    NamespaceMixin,
    # Last of the implementation mixins, first of the declarations: see the
    # class comment for why SQLDialectBase cannot lead the list.
    SQLDialectBase,
    CollationSupport,
    CTESupport,
    WindowFunctionSupport,
    JSONSupport,
    ReturningSupport,
    SetOperationSupport,
    SequenceObjectSupport,
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
    TableObjectSupport,
    TruncateSupport,
    # The DDL protocols for schemas stay in, and they now split per statement:
    # CreateSchemaSupport / DropSchemaSupport replace the single umbrella.
    # They are satisfied by SchemaMixin (above) with every switch False, which
    # is Firebird's answer rather than an omission -- there is no CREATE
    # SCHEMA to render.
    IndexObjectSupport,
    TriggerObjectSupport,
    ConstraintSupport,
    IntrospectionSupport,
    TransactionControlSupport,
    GeneratedColumnSupport,
    # IdentityColumnSupport is satisfied by the core IdentityColumnMixin with
    # Firebird's measured probes; AutoIncrementColumnSupport by the core
    # AutoIncrementMixin with Firebird's False answer. Both switches being
    # reachable by name is the point -- a capability question should be
    # answerable before rendering, not only as a side effect of a refusal.
    IdentityColumnSupport,
    AutoIncrementColumnSupport,
    ViewObjectSupport,
    RoutineObjectSupport,
    CreateTableSupport,
    DropTableSupport,
    AlterTableSupport,
    CreateViewSupport,
    DropViewSupport,
    CreateIndexSupport,
    DropIndexSupport,
    CreateTriggerSupport,
    DropTriggerSupport,
    CreateRoutineSupport,
    DropRoutineSupport,
    CreateSequenceSupport,
    AlterSequenceSupport,
    DropSequenceSupport,
    CreateTypeSupport,
    AlterTypeSupport,
    DropTypeSupport,
    TypeObjectSupport,
    CreateSchemaSupport,
    DropSchemaSupport,
    CommentSupport,
    # FirebirdDomainSupport subclasses the three core DOMAIN DDL protocols, so
    # it has to precede them in this list: C3 puts a subclass ahead of its base.
    FirebirdDomainSupport,
    CreateDomainSupport,
    AlterDomainSupport,
    DropDomainSupport,
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

    Namespaces: **none**. Firebird has no ``CREATE SCHEMA``, relation names
    cannot be qualified, and the ``RDB$`` system tables are ordinary relations
    with a naming convention rather than a namespace. The naming switches
    ``supports_catalog_qualification()`` and
    ``supports_schema_qualification()`` therefore answer ``False``, which is
    what the core ``validate_namespace`` reads before spelling a name: a name
    carrying a namespace slot raises ``UnsupportedFeatureError`` rather than
    being rendered as a qualification Firebird's parser rejects. The same answer
    is available directly from ``validate_schema_name()`` and
    ``validate_catalog_name()`` under the names callers reach for, so a caller
    can ask before rendering rather than having to render to find out.
    See :mod:`..protocols.namespace` for the full argument.
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

    def supports_skip_locked(self) -> bool:
        """SKIP LOCKED was introduced in Firebird 4.0; single source of
        truth for both this gate and FirebirdLockingMixin's rendering."""
        return _norm_version(self.version) >= (4, 0, 0)

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

    # ``format_identifier`` needs no bridge: SQLDialectBase is listed last in
    # the bases, so FirebirdIdentifierMixin -- the one and only definition of
    # that primitive in this backend -- wins outright.

    def supports_explain_plan(self) -> bool:
        return FirebirdExplainMixin.supports_explain_plan(self)

    # DDLColumnMixin precedes FirebirdTableMixin in the MRO, so the column and
    # constraint formatters need a bridge; the Firebird versions carry
    # IDENTITY auto-increment and the Firebird-only constraint refusals.
    def format_column_definition(self, col_def: "ColumnDefinition") -> Tuple[str, tuple]:
        return FirebirdTableMixin.format_column_definition(self, col_def)

    def format_table_constraint(self, expr: "TableConstraint") -> Tuple[str, tuple]:
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

    def supports_drop_index_on_table(self) -> bool:
        return False

    def supports_unique_index(self) -> bool:
        return True




    def supports_functional_index(self) -> bool:
        # Expression (computed) indexes need Firebird's ``COMPUTED BY`` syntax,
        # which is not implemented yet; declaring support would let the generic
        # renderer emit invalid SQL.
        return False








    # supports_generated_columns is provided by FirebirdGeneratedColumnMixin









    def supports_or_replace_view(self) -> bool:
        # Firebird has no ``CREATE OR REPLACE VIEW``. Firebird 4.0 added
        # ``CREATE OR ALTER VIEW``, which is a different statement: OR ALTER
        # also alters the columns and the definition of an existing view,
        # where OR REPLACE only replaces the definition. Substituting one for
        # the other behind a capability switch would make the switch lie about
        # what runs, so it is declared False and
        # ``supports_create_or_replace_view()`` (which the generic renderer
        # actually gates on) refuses ``replace=True``.
        return False

    def supports_view_check_option(self) -> bool:
        # Firebird views are updatable unconditionally and the grammar has no
        # ``WITH [LOCAL|CASCADED] CHECK OPTION`` clause, so there is nothing
        # to render. Declaring support produced a clause the parser rejects.
        return False

    def supports_cascade_view(self) -> bool:
        # Firebird's DROP VIEW has no CASCADE clause.
        return False

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
        """Firebird has no DEFERRABLE / INITIALLY ... constraint attributes.

        Measured on Firebird 5.0.4 and 6.0.0: ``DEFERRABLE``, ``NOT
        DEFERRABLE``, ``INITIALLY DEFERRED`` and ``INITIALLY IMMEDIATE`` are
        all answered with ``Token unknown`` on table and column constraints
        alike. The formatter refuses a requested spelling by name.
        """
        return False

    def supports_constraint_enforced(self) -> bool:
        """Firebird has no ENFORCED / NOT ENFORCED constraint control.

        Measured on Firebird 5.0.4 and 6.0.0: ``CHECK (...) ENFORCED`` and
        ``CHECK (...) NOT ENFORCED`` are answered with ``Token unknown -
        ENFORCED`` / ``Token unknown - NOT``, and so are the FOREIGN KEY and
        column-constraint forms. The formatter refuses a requested spelling by
        name rather than dropping it.
        """
        return False

    def supports_add_constraint(self) -> bool:
        return True

    def supports_drop_constraint(self) -> bool:
        return True

    # endregion