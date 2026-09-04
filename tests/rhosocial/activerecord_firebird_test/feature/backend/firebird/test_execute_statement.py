# tests/rhosocial/activerecord_firebird_test/feature/backend/firebird/test_execute_statement.py
"""Tests for Firebird EXECUTE STATEMENT / autonomous transactions and the
LATERAL declaration.

``EXECUTE STATEMENT`` with ``WITH {AUTONOMOUS | COMMON} TRANSACTION`` and
``WITH CALLER PRIVILEGES`` requires Firebird 3.0 (the bare form exists
since 1.5 but is gated uniformly at 3.0). LATERAL derived tables require
Firebird 4.0. All tests are pure construction — no database connection.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect
from rhosocial.activerecord.backend.impl.firebird.expression import FirebirdExecuteStatementExpression


class TestExecuteStatement:
    def test_execute_statement_literal(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdExecuteStatementExpression(
            dialect, "UPDATE t SET c = 1"
        ).to_sql()
        assert sql == "EXECUTE STATEMENT 'UPDATE t SET c = 1'"
        assert params == ()

    def test_execute_statement_autonomous_transaction(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdExecuteStatementExpression(
            dialect, "UPDATE t SET c = 1", transaction="AUTONOMOUS"
        ).to_sql()
        assert sql == "EXECUTE STATEMENT 'UPDATE t SET c = 1' WITH AUTONOMOUS TRANSACTION"
        assert params == ()

    def test_execute_statement_common_transaction_and_caller_privileges(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdExecuteStatementExpression(
            dialect,
            "UPDATE t SET c = 1",
            transaction="COMMON",
            caller_privileges=True,
        ).to_sql()
        assert sql == (
            "EXECUTE STATEMENT 'UPDATE t SET c = 1' "
            "WITH COMMON TRANSACTION WITH CALLER PRIVILEGES"
        )
        assert params == ()

    def test_execute_statement_with_params(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdExecuteStatementExpression(
            dialect, "UPDATE t SET c = ?", params=[1]
        ).to_sql()
        assert sql == "EXECUTE STATEMENT 'UPDATE t SET c = ?' (?)"
        assert params == (1,)

    def test_execute_statement_variable_sql(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = FirebirdExecuteStatementExpression(
            dialect, ":sql_param", caller_privileges=True
        ).to_sql()
        assert sql == "EXECUTE STATEMENT :sql_param WITH CALLER PRIVILEGES"
        assert params == ()


class TestAutonomousTransactionDo:
    def test_autonomous_transaction_do_wraps_block(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = dialect.format_autonomous_transaction_do(
            "EXECUTE PROCEDURE do_thing;"
        )
        assert sql == "IN AUTONOMOUS TRANSACTION DO BEGIN\nEXECUTE PROCEDURE do_thing;\nEND"
        assert params == ()

    def test_autonomous_transaction_do_preserves_begin(self):
        dialect = FirebirdDialect((4, 0, 0))
        sql, params = dialect.format_autonomous_transaction_do(
            "BEGIN\n  EXECUTE PROCEDURE do_thing;\nEND"
        )
        assert sql == "IN AUTONOMOUS TRANSACTION DO BEGIN\n  EXECUTE PROCEDURE do_thing;\nEND"
        assert params == ()


class TestExecuteStatementVersionGating:
    def test_execute_statement_raises_on_fb2_5(self):
        dialect = FirebirdDialect((2, 5, 0))
        expr = FirebirdExecuteStatementExpression(
            dialect, "UPDATE t SET c = 1", transaction="AUTONOMOUS"
        )
        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_autonomous_transaction_do_raises_on_fb2_5(self):
        dialect = FirebirdDialect((2, 5, 0))
        with pytest.raises(UnsupportedFeatureError):
            dialect.format_autonomous_transaction_do("EXECUTE PROCEDURE do_thing;")

    def test_execute_statement_ok_on_fb3(self):
        dialect = FirebirdDialect((3, 0, 0))
        sql, params = FirebirdExecuteStatementExpression(
            dialect, "UPDATE t SET c = 1", transaction="AUTONOMOUS"
        ).to_sql()
        assert sql == "EXECUTE STATEMENT 'UPDATE t SET c = 1' WITH AUTONOMOUS TRANSACTION"
        assert params == ()

    def test_supports_autonomous_transaction_gated(self):
        assert FirebirdDialect((3, 0, 0)).supports_autonomous_transaction() is True
        assert FirebirdDialect((2, 5, 0)).supports_autonomous_transaction() is False


class TestExecuteStatementDispatch:
    def test_format_execute_statement_resolves_to_dml_mixin(self):
        from rhosocial.activerecord.backend.impl.firebird.mixins.dml import FirebirdDMLOperationMixin

        dialect = FirebirdDialect((4, 0, 0))
        mixin = FirebirdDMLOperationMixin
        assert type(dialect).format_execute_statement == mixin.format_execute_statement
        assert type(dialect).format_autonomous_transaction_do == mixin.format_autonomous_transaction_do


class TestLateralDeclaration:
    def test_lateral_join_fb4(self):
        assert FirebirdDialect((4, 0, 0)).supports_lateral_join() is True
        assert FirebirdDialect((5, 0, 0)).supports_lateral_join() is True

    def test_lateral_join_fb3(self):
        assert FirebirdDialect((3, 0, 0)).supports_lateral_join() is False
        assert FirebirdDialect((2, 5, 0)).supports_lateral_join() is False
