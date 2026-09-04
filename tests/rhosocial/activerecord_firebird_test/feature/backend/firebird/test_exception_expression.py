# tests/rhosocial/activerecord_firebird_test/feature/backend/firebird/test_exception_expression.py
"""Tests for Firebird EXCEPTION statement expressions.

Covers ``CREATE EXCEPTION``, ``ALTER EXCEPTION`` and ``DROP EXCEPTION``.
All tests are pure construction — no database connection.
"""

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import (
    FirebirdAlterExceptionExpression,
    FirebirdCreateExceptionExpression,
    FirebirdDropExceptionExpression,
)


class TestCreateException:
    def test_create_exception(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdCreateExceptionExpression(dialect, "e_bad_qty", "库存不足").to_sql()
        assert sql == 'CREATE EXCEPTION "E_BAD_QTY" \'库存不足\''
        assert params == ()

    def test_create_exception_escapes_quote(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdCreateExceptionExpression(dialect, "e_q", "it's bad").to_sql()
        assert sql == "CREATE EXCEPTION \"E_Q\" 'it''s bad'"
        assert params == ()


class TestAlterException:
    def test_alter_exception(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdAlterExceptionExpression(dialect, "e_bad_qty", "新消息").to_sql()
        assert sql == 'ALTER EXCEPTION "E_BAD_QTY" \'新消息\''
        assert params == ()


class TestDropException:
    def test_drop_exception(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdDropExceptionExpression(dialect, "e_bad_qty").to_sql()
        assert sql == 'DROP EXCEPTION "E_BAD_QTY"'
        assert params == ()


class TestExceptionDispatch:
    def test_expression_to_sql_delegates_to_dialect(self):
        from rhosocial.activerecord.backend.impl.firebird.mixins.exception import FirebirdExceptionMixin

        dialect = FirebirdDialect((4, 0, 0))
        mixin = FirebirdExceptionMixin
        assert type(dialect).format_create_exception_statement == mixin.format_create_exception_statement
        assert type(dialect).format_alter_exception_statement == mixin.format_alter_exception_statement
        assert type(dialect).format_drop_exception_statement == mixin.format_drop_exception_statement

    def test_supports_exception_declared(self):
        dialect = FirebirdDialect((4, 0, 0))
        assert dialect.supports_exception() is True
        assert dialect.supports_create_exception() is True
