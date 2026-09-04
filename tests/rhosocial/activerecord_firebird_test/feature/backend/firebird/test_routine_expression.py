# tests/rhosocial/activerecord_firebird_test/feature/backend/firebird/test_routine_expression.py
"""Tests for Firebird PSQL PROCEDURE / FUNCTION / PACKAGE DDL expressions.

Procedures are gated at ``(2, 5, 0)``; stored functions and packages were
introduced in Firebird 3.0. All tests are pure construction — no database
connection.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import (
    FirebirdCreateFunctionExpression,
    FirebirdCreatePackageBodyExpression,
    FirebirdCreatePackageExpression,
    FirebirdCreateProcedureExpression,
    FirebirdDropPackageExpression,
    FirebirdDropRoutineExpression,
    FirebirdRoutineMode,
)


class TestCreateProcedure:
    def test_create_procedure(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateProcedureExpression(
            dialect,
            "p",
            params=[("x", "INT")],
            returns=[("y", "INT")],
            body="BEGIN y = x * 2; END",
        )
        sql, params = expr.to_sql()
        assert sql == (
            'CREATE PROCEDURE "P" (x INT) RETURNS (y INT) '
            "AS BEGIN y = x * 2; END"
        )
        assert params == ()

    def test_create_or_alter_procedure(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateProcedureExpression(
            dialect,
            "p",
            params=[("x", "INT")],
            returns=[("y", "INT")],
            body="BEGIN y = x * 2; END",
            mode=FirebirdRoutineMode.CREATE_OR_ALTER,
        )
        sql, params = expr.to_sql()
        assert sql.startswith('CREATE OR ALTER PROCEDURE "P" (x INT)')
        assert params == ()

    def test_recreate_procedure(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateProcedureExpression(
            dialect,
            "p",
            params=[("x", "INT")],
            body="BEGIN y = x * 2; END",
            mode=FirebirdRoutineMode.RECREATE,
        )
        sql, params = expr.to_sql()
        assert sql == (
            'RECREATE PROCEDURE "P" (x INT) AS BEGIN y = x * 2; END'
        )
        assert params == ()

    def test_procedure_body_wrapped_when_not_begin(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateProcedureExpression(
            dialect,
            "p",
            params=[("x", "INT")],
            body="y = x * 2;",
        )
        sql, params = expr.to_sql()
        assert sql == 'CREATE PROCEDURE "P" (x INT) AS BEGIN\ny = x * 2;\nEND'
        assert params == ()

    def test_procedure_supports_dict_params(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateProcedureExpression(
            dialect,
            "p",
            params=[{"name": "x", "type": "INT"}],
            body="BEGIN END",
        )
        sql, params = expr.to_sql()
        assert sql == 'CREATE PROCEDURE "P" (x INT) AS BEGIN END'
        assert params == ()


class TestCreateFunction:
    def test_create_function(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateFunctionExpression(
            dialect,
            "f",
            params=[("x", "INT")],
            returns="INT",
            body="BEGIN RETURN x + 1; END",
        )
        sql, params = expr.to_sql()
        assert sql == (
            'CREATE FUNCTION "F" (x INT) RETURNS INT AS BEGIN RETURN x + 1; END'
        )
        assert params == ()


class TestDropRoutine:
    def test_drop_procedure(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdDropRoutineExpression(
            dialect, "p", routine_type="PROCEDURE"
        ).to_sql()
        assert sql == 'DROP PROCEDURE "P"'
        assert params == ()

    def test_drop_function(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdDropRoutineExpression(
            dialect, "f", routine_type="FUNCTION"
        ).to_sql()
        assert sql == 'DROP FUNCTION "F"'
        assert params == ()

    def test_recreate_via_drop_routine(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdDropRoutineExpression(
            dialect,
            "p",
            routine_type="PROCEDURE",
            mode=FirebirdRoutineMode.RECREATE,
            params=[("x", "INT")],
            body="BEGIN y = x; END",
        )
        sql, params = expr.to_sql()
        assert sql == 'RECREATE PROCEDURE "P" (x INT) AS BEGIN y = x; END'
        assert params == ()


class TestPackage:
    def test_create_package(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreatePackageExpression(
            dialect, "pk", body="BEGIN PROCEDURE p (x INT); END"
        )
        sql, params = expr.to_sql()
        assert sql == 'CREATE PACKAGE "PK" AS BEGIN PROCEDURE p (x INT); END'
        assert params == ()

    def test_create_package_body(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreatePackageBodyExpression(
            dialect, "pk", body="BEGIN PROCEDURE p (x INT) AS BEGIN END END"
        )
        sql, params = expr.to_sql()
        assert sql == 'CREATE PACKAGE BODY "PK" AS BEGIN PROCEDURE p (x INT) AS BEGIN END END'
        assert params == ()

    def test_drop_package(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdDropPackageExpression(dialect, "pk").to_sql()
        assert sql == 'DROP PACKAGE "PK"'
        assert params == ()

    def test_drop_package_body(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdDropPackageExpression(dialect, "pk", body=True).to_sql()
        assert sql == 'DROP PACKAGE BODY "PK"'
        assert params == ()


class TestRoutineVersionGating:
    def test_procedure_ok_on_fb2_5(self):
        dialect = FirebirdDialect((2, 5, 0))
        expr = FirebirdCreateProcedureExpression(
            dialect, "p", params=[("x", "INT")], body="BEGIN END"
        )
        sql, params = expr.to_sql()
        assert sql == 'CREATE PROCEDURE "P" (x INT) AS BEGIN END'

    def test_function_raises_on_fb2_5(self):
        dialect = FirebirdDialect((2, 5, 0))
        expr = FirebirdCreateFunctionExpression(
            dialect, "f", params=[("x", "INT")], returns="INT", body="BEGIN END"
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_package_raises_on_fb2_5(self):
        dialect = FirebirdDialect((2, 5, 0))
        with pytest.raises(UnsupportedFeatureError):
            FirebirdCreatePackageExpression(dialect, "pk", body="BEGIN END").to_sql()

    def test_drop_function_raises_on_fb2_5(self):
        dialect = FirebirdDialect((2, 5, 0))
        with pytest.raises(UnsupportedFeatureError):
            FirebirdDropRoutineExpression(dialect, "f", routine_type="FUNCTION").to_sql()

    def test_function_and_package_ok_on_fb3(self):
        dialect = FirebirdDialect((3, 0, 0))
        FirebirdCreateFunctionExpression(
            dialect, "f", params=[("x", "INT")], returns="INT", body="BEGIN END"
        ).to_sql()
        FirebirdCreatePackageExpression(dialect, "pk", body="BEGIN END").to_sql()

    def test_supports_packages_gated(self):
        assert FirebirdDialect((3, 0, 0)).supports_packages() is True
        assert FirebirdDialect((2, 5, 0)).supports_packages() is False


class TestRoutineDispatch:
    def test_format_create_function_resolves_to_firebird_mixin(self):
        from rhosocial.activerecord.backend.impl.firebird.mixins.routine import FirebirdRoutineMixin

        dialect = FirebirdDialect((4, 0, 0))
        assert type(dialect).format_create_function_statement == FirebirdRoutineMixin.format_create_function_statement
        assert type(dialect).format_create_procedure_statement == FirebirdRoutineMixin.format_create_procedure_statement
        assert type(dialect).format_drop_routine_statement == FirebirdRoutineMixin.format_drop_routine_statement
