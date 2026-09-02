# tests/rhosocial/activerecord_firebird_test/feature/backend/test_merge_statement.py
"""Tests for the Firebird-specific MERGE statement formatter.

Firebird supports MERGE since 2.1, ``WHEN MATCHED THEN DELETE`` / the
SQL:2008 multi-WHEN form since 3.0, and ``WHEN NOT MATCHED BY SOURCE``
since 5.0. DELETE is only legal in the ``WHEN MATCHED`` and ``WHEN NOT
MATCHED BY SOURCE`` branches; the ``WHEN NOT MATCHED`` branch may only
INSERT. All tests are pure construction — no database connection.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import Column, TableExpression
from rhosocial.activerecord.backend.expression.statements import (
    MergeAction,
    MergeActionType,
    MergeExpression,
)
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.mixins.dml import FirebirdDMLOperationMixin


def _make_merge(dialect, when_matched=None, when_not_matched=None, by_source=None):
    """Build a MERGE expression over a simple two-column target/source pair."""
    return MergeExpression(
        dialect,
        target="tgt",
        source=TableExpression(dialect, "src"),
        on_condition=Column(dialect, "id", "tgt") == Column(dialect, "id", "src"),
        when_matched=when_matched or [],
        when_not_matched=when_not_matched or [],
        when_not_matched_by_source=by_source or [],
    )


def _update_action(dialect, **assignments):
    return MergeAction(
        MergeActionType.UPDATE,
        assignments={
            col: Column(dialect, col, "src") for col in assignments
        },
    )


def _insert_action(dialect, **assignments):
    return MergeAction(
        MergeActionType.INSERT,
        assignments={
            col: Column(dialect, col, "src") for col in assignments
        },
    )


class TestMergeResolution:
    def test_format_merge_statement_resolves_to_firebird_mixin(self):
        dialect = FirebirdDialect((5, 0, 0))
        resolved = type(dialect).format_merge_statement
        assert resolved == FirebirdDMLOperationMixin.format_merge_statement

    def test_merge_support_declared(self):
        dialect = FirebirdDialect((5, 0, 0))
        assert dialect.supports_merge_statement() is True
        assert dialect.supports_merge() is True


class TestMergeMatchedBranches:
    def test_matched_update(self):
        dialect = FirebirdDialect((5, 0, 0))
        expr = _make_merge(
            dialect,
            when_matched=[_update_action(dialect, name=True, price=True)],
        )
        sql, params = expr.to_sql()
        assert sql == (
            'MERGE INTO "TGT" USING "SRC" ON "TGT"."ID" = "SRC"."ID" '
            'WHEN MATCHED THEN UPDATE SET "NAME" = "SRC"."NAME", '
            '"PRICE" = "SRC"."PRICE"'
        )
        assert params == ()

    def test_matched_update_with_condition(self):
        dialect = FirebirdDialect((5, 0, 0))
        action = _update_action(dialect, name=True)
        action.condition = Column(dialect, "active", "src") == True  # noqa: E712
        expr = _make_merge(dialect, when_matched=[action])
        sql, params = expr.to_sql()
        assert sql == (
            'MERGE INTO "TGT" USING "SRC" ON "TGT"."ID" = "SRC"."ID" '
            'WHEN MATCHED AND "SRC"."ACTIVE" = ? THEN UPDATE SET '
            '"NAME" = "SRC"."NAME"'
        )
        assert params == (True,)

    def test_matched_delete_fb3(self):
        dialect = FirebirdDialect((3, 0, 0))
        expr = _make_merge(
            dialect,
            when_matched=[MergeAction(MergeActionType.DELETE)],
        )
        sql, params = expr.to_sql()
        assert sql == (
            'MERGE INTO "TGT" USING "SRC" ON "TGT"."ID" = "SRC"."ID" '
            'WHEN MATCHED THEN DELETE'
        )
        assert params == ()

    def test_matched_delete_fb2_5_raises(self):
        dialect = FirebirdDialect((2, 5, 0))
        expr = _make_merge(
            dialect,
            when_matched=[MergeAction(MergeActionType.DELETE)],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()


class TestMergeNotMatchedBranches:
    def test_not_matched_insert(self):
        dialect = FirebirdDialect((5, 0, 0))
        expr = _make_merge(
            dialect,
            when_not_matched=[_insert_action(dialect, id=True, name=True)],
        )
        sql, params = expr.to_sql()
        assert sql == (
            'MERGE INTO "TGT" USING "SRC" ON "TGT"."ID" = "SRC"."ID" '
            'WHEN NOT MATCHED THEN INSERT ("ID", "NAME") VALUES '
            '("SRC"."ID", "SRC"."NAME")'
        )
        assert params == ()

    def test_not_matched_delete_raises(self):
        dialect = FirebirdDialect((5, 0, 0))
        expr = _make_merge(
            dialect,
            when_not_matched=[MergeAction(MergeActionType.DELETE)],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_not_matched_insert_default_values_raises(self):
        dialect = FirebirdDialect((5, 0, 0))
        expr = _make_merge(
            dialect,
            when_not_matched=[MergeAction(MergeActionType.INSERT)],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()


class TestMergeBySource:
    def test_by_source_update_fb5(self):
        dialect = FirebirdDialect((5, 0, 0))
        expr = _make_merge(
            dialect,
            by_source=[_update_action(dialect, name=True)],
        )
        sql, params = expr.to_sql()
        assert sql == (
            'MERGE INTO "TGT" USING "SRC" ON "TGT"."ID" = "SRC"."ID" '
            'WHEN NOT MATCHED BY SOURCE THEN UPDATE SET "NAME" = "SRC"."NAME"'
        )
        assert params == ()

    def test_by_source_delete_fb5(self):
        dialect = FirebirdDialect((5, 0, 0))
        expr = _make_merge(
            dialect,
            by_source=[MergeAction(MergeActionType.DELETE)],
        )
        sql, params = expr.to_sql()
        assert sql == (
            'MERGE INTO "TGT" USING "SRC" ON "TGT"."ID" = "SRC"."ID" '
            'WHEN NOT MATCHED BY SOURCE THEN DELETE'
        )
        assert params == ()

    def test_by_source_fb3_raises(self):
        dialect = FirebirdDialect((3, 0, 0))
        expr = _make_merge(
            dialect,
            by_source=[MergeAction(MergeActionType.DELETE)],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_by_source_fb2_5_raises(self):
        dialect = FirebirdDialect((2, 5, 0))
        expr = _make_merge(
            dialect,
            by_source=[MergeAction(MergeActionType.DELETE)],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()


class TestMergeVersionBoundaries:
    def test_full_merge_fb5(self):
        dialect = FirebirdDialect((5, 0, 0))
        expr = _make_merge(
            dialect,
            when_matched=[
                _update_action(dialect, name=True),
                MergeAction(MergeActionType.DELETE),
            ],
            when_not_matched=[_insert_action(dialect, id=True, name=True)],
            by_source=[MergeAction(MergeActionType.DELETE)],
        )
        sql, params = expr.to_sql()
        assert sql == (
            'MERGE INTO "TGT" USING "SRC" ON "TGT"."ID" = "SRC"."ID" '
            'WHEN MATCHED THEN UPDATE SET "NAME" = "SRC"."NAME" '
            'WHEN MATCHED THEN DELETE '
            'WHEN NOT MATCHED THEN INSERT ("ID", "NAME") VALUES '
            '("SRC"."ID", "SRC"."NAME") '
            'WHEN NOT MATCHED BY SOURCE THEN DELETE'
        )
        assert params == ()

    def test_fb2_5_delete_branch_raises_before_by_source(self):
        dialect = FirebirdDialect((2, 5, 0))
        expr = _make_merge(
            dialect,
            when_matched=[MergeAction(MergeActionType.DELETE)],
            when_not_matched=[_insert_action(dialect, id=True)],
            by_source=[MergeAction(MergeActionType.DELETE)],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_fb3_delete_ok_by_source_raises(self):
        dialect = FirebirdDialect((3, 0, 0))
        expr = _make_merge(
            dialect,
            when_matched=[MergeAction(MergeActionType.DELETE)],
            when_not_matched=[_insert_action(dialect, id=True)],
            by_source=[MergeAction(MergeActionType.DELETE)],
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_update_or_insert_unaffected(self):
        dialect = FirebirdDialect((2, 5, 0))
        sql, params = dialect.format_update_or_insert(
            table="products",
            insert_columns=["id", "name", "price"],
            insert_values=[1, "Product A", 19.99],
            match_columns=["id"],
            returning_columns=["id"],
        )
        assert sql.startswith("UPDATE OR INSERT INTO \"PRODUCTS\"")
        assert "MATCHING" in sql
        assert params == (1, "Product A", 19.99)
