# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/ddl/test_alter_table_multi_action.py
"""One expression renders one action, on every dialect.

Firebird's grammar happens to accept a comma-separated list of operations, and
that is exactly why this test exists: the formatter must not take the engine's
permission as its own. A statement carrying two actions fails fast, because the
second action would otherwise be invisible to the caller's plan -- its own
phase, permission and destructive check. The caller emits one
``AlterTableStatement`` per action and orders them.

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


def _add_email(dialect):
    return AddColumnAction(dialect, ColumnDefinition(dialect, "email", TextType(dialect)))


def _add_age(dialect):
    return AddColumnAction(dialect, ColumnDefinition(dialect, "age", IntegerType(dialect)))


def _statement(dialect, *actions):
    return AlterTableStatement(dialect, Table(dialect, "users"), list(actions))


def test_two_actions_are_refused_even_though_firebird_accepts_them():
    dialect = FirebirdDialect((5, 0, 0))
    with pytest.raises(UnsupportedFeatureError, match="multiple actions"):
        _statement(dialect, _add_email(dialect), _add_age(dialect)).to_sql()


def test_each_action_renders_its_own_statement():
    dialect = FirebirdDialect((5, 0, 0))
    email_sql, email_params = _statement(dialect, _add_email(dialect)).to_sql()
    age_sql, age_params = _statement(dialect, _add_age(dialect)).to_sql()

    assert email_sql == 'ALTER TABLE "USERS" ADD COLUMN "EMAIL" BLOB SUB_TYPE TEXT'
    assert age_sql == 'ALTER TABLE "USERS" ADD COLUMN "AGE" INTEGER'
    assert email_sql.count("ALTER TABLE") == 1
    assert age_sql.count("ALTER TABLE") == 1
    assert ";" not in email_sql + age_sql
    assert email_params == age_params == ()
