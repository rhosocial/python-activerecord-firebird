# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/statements/test_change_point_suggestions.py
"""Focused contract tests for Firebird's four migration change-point answers.

No server is required. Each answer is exercised on a real FirebirdDialect with a
frozen point built the way core's change planner builds it, and the returned
operations are real expression nodes that render through the dialect's own
formatters. Exact SQL strings pin the Firebird spelling of every supported
chain; the unsupported answers carry their evidence in the mixin docstrings.
"""
import dataclasses

import pytest
from rhosocial.activerecord.backend.dialect.exceptions import (
    DialectNotAdaptedException,
    UnsupportedFeatureError,
)
from rhosocial.activerecord.backend.expression import Column
from rhosocial.activerecord.backend.expression.bases import BaseExpression
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    AlterTableStatement,
    IndexDefinition,
    PartitionClause,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddIndexAction,
    AddTableConstraintAction,
    DropIndexAction,
    DropTableConstraintAction,
)
from rhosocial.activerecord.backend.expression.statements.ddl_index import (
    CreateIndexStatement,
    DropIndexStatement,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    TableConstraint,
    TableUniqueConstraint,
)
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import FirebirdSetPositionAction
from rhosocial.activerecord.backend.impl.firebird.suggestion.column_reorder_suggestion import (
    POSITION_VERSION_FLOOR,
)
from rhosocial.activerecord.backend.suggestion import (
    ColumnReorderSuggestion,
    PartitionSchemeChangeSuggestion,
    TableConstraintChangeSuggestion,
    TableIndexChangeSuggestion,
)
from rhosocial.activerecord.backend.suggestion.protocols import (
    ColumnReorderSuggestionSupport,
    PartitionSchemeChangeSuggestionSupport,
    TableConstraintChangeSuggestionSupport,
    TableIndexChangeSuggestionSupport,
)
from rhosocial.activerecord.migration.schema_change import _freeze

CASES = [
    (ColumnReorderSuggestionSupport, ColumnReorderSuggestion, "suggest_column_reorder"),
    (
        TableConstraintChangeSuggestionSupport,
        TableConstraintChangeSuggestion,
        "suggest_table_constraint_change",
    ),
    (
        TableIndexChangeSuggestionSupport,
        TableIndexChangeSuggestion,
        "suggest_table_index_change",
    ),
    (
        PartitionSchemeChangeSuggestionSupport,
        PartitionSchemeChangeSuggestion,
        "suggest_partition_scheme_change",
    ),
]


def _dialect(version=(5, 0, 0)):
    return FirebirdDialect(version) if version is not None else FirebirdDialect()


def _constraint(dialect, name="uq_created", column="created_at"):
    return TableConstraint(
        dialect, branch=TableUniqueConstraint(dialect, [column]), name=name
    )


def _index(dialect, name="idx_created", column="created_at", **kwargs):
    return IndexDefinition(dialect, name=name, columns=[column], **kwargs)


def _partition(dialect, word="HASH", column="id"):
    return PartitionClause(dialect, word, [Column(dialect, column)])


def _sql(operations):
    return [operation.to_sql()[0] for operation in operations]


# --------------------------------------------------------------- registration


def test_dialect_satisfies_all_four_change_point_protocols():
    dialect = _dialect()
    for protocol, value_type, method in CASES:
        assert isinstance(dialect, protocol), protocol.__name__
        answer = getattr(dialect, method)(value_type(table_name="events"))
        assert isinstance(answer, value_type), protocol.__name__
        assert answer.label == value_type().label
        assert dataclasses.is_dataclass(answer)
        assert answer.table_name == "events"


# --------------------------------------------------------------- column reorder


def test_column_reorder_chain_renders_native_firebird_position_statements():
    dialect = _dialect()
    point = ColumnReorderSuggestion(
        table_name="events",
        old_order=("id", "created_at", "code"),
        new_order=("created_at", "code", "id"),
        reordered_columns=("id", "created_at", "code"),
    )
    operations = dialect.suggest_column_reorder(point).operations
    assert isinstance(operations, tuple) and len(operations) == 2
    assert all(isinstance(operation, AlterTableStatement) for operation in operations)
    assert all(operation.action is not None for operation in operations)
    assert all(isinstance(operation.action, FirebirdSetPositionAction) for operation in operations)
    # Slots are filled from the left, so each step keeps the prefix fixed.
    assert _sql(operations) == [
        'ALTER TABLE "EVENTS" ALTER COLUMN "CREATED_AT" POSITION 1',
        'ALTER TABLE "EVENTS" ALTER COLUMN "CODE" POSITION 2',
    ]


def test_column_reorder_single_move_uses_one_position_statement():
    dialect = _dialect()
    point = ColumnReorderSuggestion(
        table_name="events",
        old_order=("id", "created_at"),
        new_order=("created_at", "id"),
        reordered_columns=("id", "created_at"),
    )
    answer = dialect.suggest_column_reorder(point)
    assert answer.state == "actions"
    assert _sql(answer.operations) == [
        'ALTER TABLE "EVENTS" ALTER COLUMN "CREATED_AT" POSITION 1'
    ]


@pytest.mark.parametrize("version", [None, (2, 5, 0), (3, 0, 0), (4, 0, 0), (5, 0, 0)])
def test_position_version_floor_is_pinned_at_firebird_3(version):
    """POSITION first appears in FB 3.0; the renderer and the answer agree."""
    assert POSITION_VERSION_FLOOR == (3, 0, 0)
    dialect = _dialect(version)
    point = ColumnReorderSuggestion(
        table_name="events",
        old_order=("id", "created_at"),
        new_order=("created_at", "id"),
        reordered_columns=("id", "created_at"),
    )
    answer = dialect.suggest_column_reorder(point)
    action = FirebirdSetPositionAction(dialect, "created_at", 1)
    if version is not None and version >= POSITION_VERSION_FLOOR:
        assert answer.state == "actions"
        assert action.to_sql() == ('ALTER COLUMN "CREATED_AT" POSITION 1', ())
    else:
        assert answer.operations is False
        assert answer.state == "unaddressable"
        # A pre-3.0 server is refused for the clause; an unadapted dialect has
        # no version to gate against and is refused just as strictly.
        expected = DialectNotAdaptedException if version is None else UnsupportedFeatureError
        with pytest.raises(expected):
            action.to_sql()
    assert "3.0" in dialect.suggest_column_reorder.__doc__


def test_column_reorder_no_action_and_changed_column_set():
    dialect = _dialect()
    same = ColumnReorderSuggestion(
        table_name="events",
        old_order=("id", "created_at"),
        new_order=("id", "created_at"),
        reordered_columns=("id", "created_at"),
    )
    assert dialect.suggest_column_reorder(same).operations is None

    added = ColumnReorderSuggestion(
        table_name="events",
        old_order=("id", "created_at"),
        new_order=("id", "created_at", "code"),
        reordered_columns=("id", "created_at"),
    )
    # POSITION cannot add a column; the planner emits that as its own statement.
    assert dialect.suggest_column_reorder(added).operations is False


# ------------------------------------------------------------------ constraints


def test_constraint_drop_chain_renders_alter_table_drop_constraint():
    dialect = _dialect()
    point = TableConstraintChangeSuggestion(
        table_name="events",
        old_constraints=(_freeze(_constraint(dialect)),),
        new_constraints=(),
    )
    operations = dialect.suggest_table_constraint_change(point).operations
    assert isinstance(operations, tuple) and len(operations) == 1
    statement = operations[0]
    assert isinstance(statement, AlterTableStatement)
    assert statement.action is not None
    assert isinstance(statement.action, DropTableConstraintAction)
    # Firebird has no DROP CONSTRAINT IF EXISTS on any supported release.
    assert dialect.supports_drop_constraint_if_exists() is False
    assert _sql(operations) == ['ALTER TABLE "EVENTS" DROP CONSTRAINT "UQ_CREATED"']


def test_constraint_add_reuses_live_table_constraint_node():
    dialect = _dialect()
    live = _constraint(dialect)
    point = TableConstraintChangeSuggestion(
        table_name="events", old_constraints=(), new_constraints=(live,)
    )
    operations = dialect.suggest_table_constraint_change(point).operations
    assert isinstance(operations, tuple) and len(operations) == 1
    assert isinstance(operations[0].action, AddTableConstraintAction)
    assert operations[0].action.constraint is live
    assert _sql(operations) == [
        'ALTER TABLE "EVENTS" ADD CONSTRAINT "UQ_CREATED" UNIQUE ("CREATED_AT")'
    ]


def test_constraint_change_renders_drop_before_add():
    dialect = _dialect()
    old = _constraint(dialect)
    new = _constraint(dialect, name="uq_code", column="code")
    point = TableConstraintChangeSuggestion(
        table_name="events", old_constraints=(_freeze(old),), new_constraints=(new,)
    )
    assert _sql(dialect.suggest_table_constraint_change(point).operations) == [
        'ALTER TABLE "EVENTS" DROP CONSTRAINT "UQ_CREATED"',
        'ALTER TABLE "EVENTS" ADD CONSTRAINT "UQ_CODE" UNIQUE ("CODE")',
    ]


def test_constraint_add_from_frozen_projection_is_false():
    """A frozen projection cannot distinguish PRIMARY KEY from UNIQUE."""
    dialect = _dialect()
    point = TableConstraintChangeSuggestion(
        table_name="events", old_constraints=(), new_constraints=(_freeze(_constraint(dialect)),)
    )
    answer = dialect.suggest_table_constraint_change(point)
    assert answer.operations is False
    assert answer.state == "unaddressable"
    doc = dialect.suggest_table_constraint_change.__doc__
    assert "PRIMARY KEY" in doc and "UNIQUE" in doc


def test_constraint_change_with_no_difference_is_absent():
    dialect = _dialect()
    frozen = _freeze(_constraint(dialect))
    point = TableConstraintChangeSuggestion(
        table_name="events", old_constraints=(frozen,), new_constraints=(frozen,)
    )
    assert dialect.suggest_table_constraint_change(point).operations is None


def test_constraint_change_without_a_name_is_false():
    dialect = _dialect()
    unnamed = _constraint(dialect)
    unnamed.name = None
    point = TableConstraintChangeSuggestion(
        table_name="events", old_constraints=(_freeze(unnamed),), new_constraints=()
    )
    assert dialect.suggest_table_constraint_change(point).operations is False


def test_constraint_change_is_gated_by_capability_probes():
    class NoConstraintDDL(FirebirdDialect):
        def supports_add_constraint(self) -> bool:
            return False

    dialect = NoConstraintDDL((5, 0, 0))
    point = TableConstraintChangeSuggestion(
        table_name="events", old_constraints=(_freeze(_constraint(dialect)),), new_constraints=()
    )
    assert dialect.suggest_table_constraint_change(point).operations is False


# ---------------------------------------------------------------------- indexes


def test_index_drop_chain_renders_standalone_drop_index():
    dialect = _dialect()
    point = TableIndexChangeSuggestion(
        table_name="events", old_indexes=(_freeze(_index(dialect)),), new_indexes=()
    )
    operations = dialect.suggest_table_index_change(point).operations
    assert isinstance(operations, tuple) and len(operations) == 1
    assert isinstance(operations[0], DropIndexStatement)
    assert _sql(operations) == ['DROP INDEX "IDX_CREATED"']


def test_index_create_chain_renders_standalone_create_index():
    dialect = _dialect()
    point = TableIndexChangeSuggestion(
        table_name="events", old_indexes=(), new_indexes=(_freeze(_index(dialect)),)
    )
    operations = dialect.suggest_table_index_change(point).operations
    assert isinstance(operations, tuple) and len(operations) == 1
    assert isinstance(operations[0], CreateIndexStatement)
    assert isinstance(operations[0].table, Table) and operations[0].table.name == "events"
    assert _sql(operations) == ['CREATE INDEX "IDX_CREATED" ON "EVENTS" ("CREATED_AT")']


def test_index_change_creates_unique_index_in_dialect_format():
    dialect = _dialect()
    point = TableIndexChangeSuggestion(
        table_name="events",
        old_indexes=(),
        new_indexes=(_freeze(_index(dialect, unique=True)),),
    )
    assert _sql(dialect.suggest_table_index_change(point).operations) == [
        'CREATE UNIQUE INDEX "IDX_CREATED" ON "EVENTS" ("CREATED_AT")'
    ]


def test_alter_table_index_actions_are_never_used():
    dialect = _dialect()
    assert dialect.supports_alter_table_index_actions() is False
    point = TableIndexChangeSuggestion(
        table_name="events", old_indexes=(), new_indexes=(_freeze(_index(dialect)),)
    )
    operations = dialect.suggest_table_index_change(point).operations
    assert all(
        not isinstance(op, (AlterTableStatement, AddIndexAction, DropIndexAction))
        for op in operations
    )
    assert all(isinstance(op, BaseExpression) for op in operations)


def test_index_change_with_no_difference_is_absent():
    dialect = _dialect()
    frozen = _freeze(_index(dialect))
    point = TableIndexChangeSuggestion(
        table_name="events", old_indexes=(frozen,), new_indexes=(frozen,)
    )
    assert dialect.suggest_table_index_change(point).operations is None


def test_index_change_with_frozen_expression_column_or_predicate_is_false():
    dialect = _dialect()
    expression_index = IndexDefinition(dialect, "idx_expr", [Column(dialect, "a")])
    partial_index = IndexDefinition(
        dialect, "idx_partial", ["a"], partial_condition=Column(dialect, "a").is_not_null()
    )
    assert dialect.supports_functional_index() is False
    assert dialect.supports_partial_index() is False
    for index in (expression_index, partial_index):
        point = TableIndexChangeSuggestion(
            table_name="events", old_indexes=(), new_indexes=(_freeze(index),)
        )
        assert dialect.suggest_table_index_change(point).operations is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"type": "BTREE"},
        {"include_columns": ["b"]},
        {"tablespace": "fast"},
        {"if_not_exists": True},
        {"if_exists": True},
        {"concurrent": True},
    ],
)
def test_index_options_firebird_cannot_render_are_false(kwargs):
    dialect = _dialect()
    index = _index(dialect, **kwargs)
    field = "old_indexes" if "if_exists" in kwargs or "concurrent" in kwargs else "new_indexes"
    point = TableIndexChangeSuggestion(
        table_name="events", **{field: (_freeze(index),)}
    )
    answer = dialect.suggest_table_index_change(point)
    assert answer.operations is False
    assert answer.state == "unaddressable"


# ------------------------------------------------------------- partition scheme


@pytest.mark.parametrize(
    "old,new",
    [
        (None, _freeze),
        (_freeze, None),
        (_freeze, _freeze),
    ],
)
def test_partition_scheme_change_is_always_unsupported(old, new):
    dialect = _dialect()
    frozen = _freeze(_partition(dialect))
    point = PartitionSchemeChangeSuggestion(
        table_name="events",
        old_partition=old(frozen) if old else None,
        new_partition=new(frozen) if new else None,
    )
    answer = dialect.suggest_partition_scheme_change(point)
    assert answer.operations is False
    assert answer.state == "unaddressable"
    doc = dialect.suggest_partition_scheme_change.__doc__
    assert "partition" in doc.lower()
    assert "PARTITION BY" in doc


def test_partition_scheme_false_is_backed_by_the_eight_lifecycle_answers():
    dialect = _dialect()
    assert dialect.supports_table_partitioning() is False
    assert dialect.supports_partitioned_table_creation() is False
    strategy = _partition(dialect)
    for method in (
        "suggest_partition_build",
        "suggest_partition_table_drop",
        "suggest_partition_table_alter",
        "suggest_partition_add",
        "suggest_partition_drop",
        "suggest_partition_split",
        "suggest_partition_merge",
        "suggest_partition_retention",
    ):
        assert getattr(dialect, method)(strategy, None).operations is False
