# tests/rhosocial/activerecord_firebird_test/feature/backend/ddl/test_create_table_expression_diff.py
"""Firebird CreateTableExpression diff tests (Phase 3).

Mirrors the cross-backend diff test template (class/method names align with
the core library's `test_create_table_expression_diff.py`) so Firebird's
coverage gap is visible against the other backends at a glance.

Firebird capability summary (drives each test's expected path):
- column type change : in place via ``ALTER COLUMN <col> TYPE <type>``
                      (FirebirdAlterTableModifierMixin / AlterColumnType)
- column properties  : in place via ``ALTER COLUMN ... SET/DROP DEFAULT``
                      (FirebirdAlterTableModifierMixin.format_alter_column_action)
- indexes            : NO in-place ADD/DROP INDEX -> RebuildPlan
- primary key change : RebuildPlan
- partition change    : RebuildPlan
"""

import sys
if sys.version_info >= (3, 9):
    from typing import Annotated
else:
    from typing_extensions import Annotated

import pytest

from rhosocial.activerecord.backend.dialect.protocols import CreateTableExpressionDiffSupport
from rhosocial.activerecord.backend.expression import DiffPlan, RebuildPlan
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddColumn,
    AlterColumn,
    ColumnAlterOperation,
    DropColumn,
    RenameTable,
)
from rhosocial.activerecord.backend.expression.statements.ddl_table import (
    ColumnConstraint,
    ColumnConstraintType,
    ColumnDefinition,
    CreateTableExpression,
    IndexDefinition,
    TableConstraint,
    TableConstraintType,
    TableOptions,
)
from rhosocial.activerecord.backend.expression.types import (
    IntegerType,
    TextType,
    VarCharType,
)
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression.alter_table import AlterColumnType


def _col(name, dtype, *constraints):
    return ColumnDefinition(name=name, data_type=dtype, constraints=list(constraints))


def _pk():
    return ColumnConstraint(constraint_type=ColumnConstraintType.PRIMARY_KEY)


def _not_null():
    return ColumnConstraint(constraint_type=ColumnConstraintType.NOT_NULL)


def _expr(dialect, columns, indexes=None, constraints=None, **kwargs):
    return CreateTableExpression(
        dialect=dialect,
        table=kwargs.pop("table", "items"),
        columns=columns,
        indexes=indexes,
        table_constraints=constraints,
        **kwargs,
    )


D = FirebirdDialect


class TestProtocolConformance:

    def test_firebird_dialect_satisfies_protocol(self):
        assert isinstance(D(), CreateTableExpressionDiffSupport)

    def test_mixin_provides_entry_point(self):
        assert hasattr(D, "diff_create_table")


class TestValidation:

    def test_cross_dialect_raises(self):
        from rhosocial.activerecord.backend.impl.dummy.dialect import DummyDialect
        old = _expr(D(), [_col("id", IntegerType(), _pk())])
        new = _expr(DummyDialect(), [_col("id", IntegerType(), _pk())])
        with pytest.raises(ValueError, match="different dialects"):
            old.diff(new)

    def test_cross_table_raises(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk())])
        new = _expr(d, [_col("id", IntegerType(), _pk())], table="other")
        with pytest.raises(ValueError, match="different tables"):
            old.diff(new)


class TestNoChange:

    def test_identical_definitions_empty_plan(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk()), _col("name", TextType())])
        new = _expr(d, [_col("id", IntegerType(), _pk()), _col("name", TextType())])
        plan = old.diff(new)
        assert not plan.has_changes
        assert plan.rebuild is None
        assert plan.alters == []


class TestColumnChanges:

    def test_added_column_yields_add_action(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk())])
        new = _expr(d, [_col("id", IntegerType(), _pk()), _col("bio", TextType())])
        plan = old.diff(new)
        assert plan.rebuild is None and plan.has_changes
        (alter,) = plan.alters
        action = alter.actions[0]
        assert isinstance(action, AddColumn)
        assert action.column.name == "bio"

    def test_removed_column_yields_drop_action(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk()), _col("bio", TextType())])
        new = _expr(d, [_col("id", IntegerType(), _pk())])
        plan = old.diff(new)
        (action,) = plan.alters[0].actions
        assert isinstance(action, DropColumn)
        assert action.column_name == "bio"


class TestColumnPropertyChanges:

    def test_set_default(self):
        d = D()
        old = _expr(d, [_col("status", TextType())])
        new = _expr(d, [_col(
            "status", TextType(),
            ColumnConstraint(constraint_type=ColumnConstraintType.DEFAULT, default_value="ok"),
        )])
        plan = old.diff(new)
        (action,) = plan.alters[0].actions
        assert isinstance(action, AlterColumn)
        assert action.operation == ColumnAlterOperation.SET_DEFAULT

    def test_drop_default(self):
        d = D()
        old = _expr(d, [_col(
            "status", TextType(),
            ColumnConstraint(constraint_type=ColumnConstraintType.DEFAULT, default_value="ok"),
        )])
        new = _expr(d, [_col("status", TextType())])
        plan = old.diff(new)
        (action,) = plan.alters[0].actions
        assert action.operation == ColumnAlterOperation.DROP_DEFAULT

    def test_set_not_null(self):
        d = D()
        old = _expr(d, [_col("name", TextType())])
        new = _expr(d, [_col("name", TextType(), _not_null())])
        plan = old.diff(new)
        (action,) = plan.alters[0].actions
        assert action.operation == ColumnAlterOperation.SET_NOT_NULL

    def test_drop_not_null(self):
        d = D()
        old = _expr(d, [_col("name", TextType(), _not_null())])
        new = _expr(d, [_col("name", TextType())])
        plan = old.diff(new)
        (action,) = plan.alters[0].actions
        assert action.operation == ColumnAlterOperation.DROP_NOT_NULL


class TestTypeChangeRebuild:
    """Firebird: type change is in place via ``ALTER COLUMN ... TYPE``."""

    def test_type_change_yields_alter_column_type_action(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())])
        new = _expr(d, [_col("id", IntegerType(), _pk()), _col("code", TextType())])
        plan = old.diff(new)
        assert plan.rebuild is None
        (alter,) = plan.alters
        action = alter.actions[0]
        assert isinstance(action, AlterColumnType)
        assert action.column_name == "code"

    def test_type_change_renders_alter_column_type_sql(self):
        d = D()
        old = _expr(d, [_col("code", VarCharType(length=50))])
        new = _expr(d, [_col("code", VarCharType(length=100))])
        plan = old.diff(new)
        sql, _ = plan.alters[0].to_sql()
        upper = sql.upper()
        assert "ALTER TABLE" in upper
        assert "ALTER COLUMN" in upper
        assert "TYPE" in upper

    def test_length_change_is_type_change(self):
        d = D()
        old = _expr(d, [_col("name", VarCharType(length=50))])
        new = _expr(d, [_col("name", VarCharType(length=100))])
        assert old.diff(new).rebuild is None  # in-place, not rebuild


class TestIndexChanges:
    """Firebird has no ``ALTER TABLE ADD/DROP INDEX`` -> rebuild."""

    def test_added_index_rebuilds(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk())])
        new = _expr(d, [_col("id", IntegerType(), _pk())],
                    indexes=[IndexDefinition(name="idx_id", columns=["id"])])
        plan = old.diff(new)
        assert plan.alters == []
        assert plan.rebuild is not None
        assert "index change" in plan.rebuild.reason

    def test_removed_index_rebuilds(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk())],
                    indexes=[IndexDefinition(name="idx_id", columns=["id"])])
        new = _expr(d, [_col("id", IntegerType(), _pk())])
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "index change" in plan.rebuild.reason


class TestTableConstraintChanges:

    def test_pk_change_rebuilds(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType()), _col("code", TextType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["id"])])
        new = _expr(d, [_col("id", IntegerType()), _col("code", TextType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.PRIMARY_KEY, columns=["code"])])
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "primary key" in plan.rebuild.reason

    def test_named_unique_constraint_add(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk()), _col("email", TextType())])
        new = _expr(d, [_col("id", IntegerType(), _pk()), _col("email", TextType())],
                    constraints=[TableConstraint(
                        constraint_type=TableConstraintType.UNIQUE,
                        name="uq_email", columns=["email"])])
        plan = old.diff(new)
        (alter,) = plan.alters
        assert len(alter.actions) == 1
        assert type(alter.actions[0]).__name__ == "AddTableConstraint"


class TestStructuralChanges:

    def test_table_options_change_rebuilds(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk())])
        new = _expr(d, [_col("id", IntegerType(), _pk())],
                    table_options=TableOptions(charset="utf8"))
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "structural" in plan.rebuild.reason

    def test_rebuild_plan_shape(self):
        # Firebird: index changes force rebuild (no ALTER TABLE ADD INDEX).
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())])
        new = _expr(d, [_col("id", IntegerType(), _pk()), _col("code", IntegerType())],
                    indexes=[IndexDefinition(name="idx_code", columns=["code"])])
        rp = old.diff(new).rebuild
        assert rp.create.table_name == "items__rebuild__"
        assert rp.drop_old.table.name == "items"
        assert isinstance(rp.rename.actions[0], RenameTable)
        assert rp.rename.actions[0].new_name == "items"
        assert rp.copy_columns == ["id", "code"]


class TestDiffPlanInvariants:

    def test_alters_and_rebuild_mutually_exclusive(self):
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk())])
        new = _expr(d, [_col("id", IntegerType(), _pk()), _col("x", TextType())])
        plan = old.diff(new)
        assert plan.rebuild is None and plan.alters

    def test_plan_rejects_both_fields(self):
        from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
            AlterTableExpression,
        )
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            DropTableExpression,
        )
        d = D()
        rp = RebuildPlan(
            create=_expr(d, [_col("code", TextType())], table="items__rebuild__"),
            drop_old=DropTableExpression(d, "items"),
            rename=AlterTableExpression(
                d, table="items__rebuild__",
                actions=[RenameTable(d, "items__rebuild__", "items")],
            ),
        )
        alter = AlterTableExpression(d, table="t", actions=[])
        with pytest.raises(ValueError, match="mutually exclusive"):
            DiffPlan(alters=[alter], rebuild=rp)


class TestDefectRegressions:
    """Pin defects found during the cross-backend diff rollout."""

    def test_fk_table_constraint_signature_branch(self):
        """Regression: _constraint_signature originally accessed
        ``foreign_key_reference`` (ColumnConstraint-only). A TableConstraint
        carrying ``foreign_key_table`` raised AttributeError when routed
        through the unnamed-constraint signature comparison.
        """
        from rhosocial.activerecord.backend.expression.statements.ddl_table import (
            ForeignKeyConstraint,
        )
        d = D()
        old = _expr(d, [_col("id", IntegerType(), _pk()), _col("uid", IntegerType())])
        new = _expr(
            d, [_col("id", IntegerType(), _pk()), _col("uid", IntegerType())],
            constraints=[ForeignKeyConstraint(
                columns=["uid"], foreign_key_table="users", foreign_key_columns=["id"],
            )],
        )
        plan = old.diff(new)
        assert plan.rebuild is not None
        assert "unnamed" in plan.rebuild.reason
