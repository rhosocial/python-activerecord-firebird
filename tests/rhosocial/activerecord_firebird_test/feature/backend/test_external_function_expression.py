# tests/rhosocial/activerecord_firebird_test/feature/backend/test_external_function_expression.py
"""Tests for Firebird DECLARE/ALTER/DROP EXTERNAL FUNCTION expressions.

UDF declarations are an ancient Firebird feature gated at ``(2, 5, 0)``.
All tests are pure construction — no database connection.
"""

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import (
    FirebirdAlterExternalFunctionExpression,
    FirebirdCreateExternalFunctionExpression,
    FirebirdDropExternalFunctionExpression,
)


class TestDeclareExternalFunction:
    def test_declare_external_function_by_value(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateExternalFunctionExpression(
            dialect,
            "efunc",
            params=["INT"],
            returns="INT",
            by_value=True,
            entry_point="my_func",
            module_name="my_udf",
        )
        sql, params = expr.to_sql()
        assert sql == (
            'DECLARE EXTERNAL FUNCTION "EFUNC" (INT) RETURNS INT BY VALUE '
            "ENTRY_POINT 'my_func' MODULE_NAME 'my_udf'"
        )
        assert params == ()

    def test_declare_external_function_by_reference(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateExternalFunctionExpression(
            dialect,
            "add_day",
            params=["TIMESTAMP", "INT"],
            returns="TIMESTAMP",
            entry_point="addDay",
            module_name="fbudf",
        )
        sql, params = expr.to_sql()
        assert sql == (
            'DECLARE EXTERNAL FUNCTION "ADD_DAY" '
            "(TIMESTAMP, INT) RETURNS TIMESTAMP "
            "ENTRY_POINT 'addDay' MODULE_NAME 'fbudf'"
        )
        assert params == ()

    def test_declare_external_function_free_it(self):
        dialect = FirebirdDialect((4, 0, 0))
        expr = FirebirdCreateExternalFunctionExpression(
            dialect,
            "efunc",
            params=["INT"],
            returns="INT",
            by_value=True,
            entry_point="my_func",
            module_name="my_udf",
            free_it=True,
        )
        sql, params = expr.to_sql()
        assert sql == (
            'DECLARE EXTERNAL FUNCTION "EFUNC" (INT) RETURNS INT BY VALUE '
            "FREE_IT ENTRY_POINT 'my_func' MODULE_NAME 'my_udf'"
        )
        assert params == ()


class TestAlterExternalFunction:
    def test_alter_entry_point(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdAlterExternalFunctionExpression(
            dialect, "efunc", entry_point="new_func"
        ).to_sql()
        assert sql == "ALTER EXTERNAL FUNCTION \"EFUNC\" ENTRY_POINT 'new_func'"
        assert params == ()

    def test_alter_module_name(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdAlterExternalFunctionExpression(
            dialect, "efunc", module_name="fbudf2"
        ).to_sql()
        assert sql == "ALTER EXTERNAL FUNCTION \"EFUNC\" MODULE_NAME 'fbudf2'"
        assert params == ()

    def test_alter_both(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdAlterExternalFunctionExpression(
            dialect, "efunc", entry_point="new_func", module_name="new_mod"
        ).to_sql()
        assert sql == (
            "ALTER EXTERNAL FUNCTION \"EFUNC\" "
            "ENTRY_POINT 'new_func' MODULE_NAME 'new_mod'"
        )
        assert params == ()


class TestDropExternalFunction:
    def test_drop_external_function(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdDropExternalFunctionExpression(dialect, "efunc").to_sql()
        assert sql == 'DROP EXTERNAL FUNCTION "EFUNC"'
        assert params == ()


class TestExternalFunctionDispatch:
    def test_expression_to_sql_delegates_to_dialect(self):
        from rhosocial.activerecord.backend.impl.firebird.mixins.external_function import (
            FirebirdExternalFunctionMixin,
        )

        dialect = FirebirdDialect((4, 0, 0))
        assert (
            type(dialect).format_create_external_function_statement
            == FirebirdExternalFunctionMixin.format_create_external_function_statement
        )
        assert (
            type(dialect).format_alter_external_function_statement
            == FirebirdExternalFunctionMixin.format_alter_external_function_statement
        )
        assert (
            type(dialect).format_drop_external_function_statement
            == FirebirdExternalFunctionMixin.format_drop_external_function_statement
        )


class TestExternalFunctionVersionGating:
    def test_declare_external_function_ok_on_fb2_5(self):
        dialect = FirebirdDialect((2, 5, 0))
        sql, params = FirebirdCreateExternalFunctionExpression(
            dialect,
            "efunc",
            params=["INT"],
            returns="INT",
            entry_point="my_func",
            module_name="my_udf",
        ).to_sql()
        assert sql.startswith("DECLARE EXTERNAL FUNCTION")
        assert params == ()

    def test_supports_declare_external_function_true(self):
        assert FirebirdDialect((2, 5, 0)).supports_udf() is True
        assert FirebirdDialect((2, 5, 0)).supports_declare_external_function() is True
        assert FirebirdDialect((5, 0, 0)).supports_declare_external_function() is True
