# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/ddl/test_alter_table_multi_action.py
"""ALTER TABLE action-combination rules on the Firebird dialect.

Firebird accepts comma-separated operations in one ALTER TABLE statement, so
the real dialect combines actions. The formatter must still refuse a
multi-action statement on a dialect that reports the capability as False: one
expression renders one executable SQL statement, never a semicolon-joined pair.
All tests are pure construction -- no database connection.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import (
    AlterTableStatement,
    ColumnDefinition,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import AddColumnAction
from rhosocial.activerecord.backend.expression.types import IntegerType, TextType
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


class SingleActionFirebirdDialect(FirebirdDialect):
    """Firebird SQL with the multi-action capability switched off for the guard test."""

    def supports_multi_action_alter_table(self) -> bool:
        return False


def _add_email(dialect):
    return AddColumnAction(dialect, ColumnDefinition(dialect, "email", TextType(dialect)))


def _add_age(dialect):
    return AddColumnAction(dialect, ColumnDefinition(dialect, "age", IntegerType(dialect)))


def _statement(dialect, *actions):
    return AlterTableStatement(dialect, Table(dialect, "users"), list(actions))


def test_firebird_combines_actions_with_commas():
    dialect = FirebirdDialect((5, 0, 0))
    assert dialect.supports_multi_action_alter_table() is True
    sql, params = _statement(dialect, _add_email(dialect), _add_age(dialect)).to_sql()
    assert sql == (
        'ALTER TABLE "USERS" ADD COLUMN "EMAIL" BLOB SUB_TYPE TEXT, '
        'ADD COLUMN "AGE" INTEGER'
    )
    assert sql.count("ALTER TABLE") == 1
    assert ";" not in sql
    assert params == ()


def test_two_actions_fail_fast_when_dialect_cannot_combine():
    dialect = SingleActionFirebirdDialect((5, 0, 0))
    with pytest.raises(UnsupportedFeatureError, match="multiple actions"):
        _statement(dialect, _add_email(dialect), _add_age(dialect)).to_sql()


def test_single_action_still_renders_when_dialect_cannot_combine():
    dialect = SingleActionFirebirdDialect((5, 0, 0))
    sql, params = _statement(dialect, _add_email(dialect)).to_sql()
    assert sql == 'ALTER TABLE "USERS" ADD COLUMN "EMAIL" BLOB SUB_TYPE TEXT'
    assert sql.count("ALTER TABLE") == 1
    assert ";" not in sql
    assert params == ()
