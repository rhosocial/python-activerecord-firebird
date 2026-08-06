# tests/rhosocial/activerecord_firebird_test/feature/backend/test_alter_table_if_exists.py
"""Tests for Firebird ALTER TABLE IF [NOT] EXISTS guarding.

Firebird <= 5.0.4 does not support ``ADD COLUMN IF NOT EXISTS``,
``DROP COLUMN IF EXISTS`` or ``DROP CONSTRAINT IF EXISTS``. Requesting
any of these modifiers must raise ``UnsupportedFeatureError``.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.statements import ColumnDefinition
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddColumn,
    DropColumn,
    DropTableConstraint,
)
from rhosocial.activerecord.backend.expression.types import TextType
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect()


class TestFirebirdAlterTableModifierCapabilities:
    def test_supports_switches(self, dialect):
        assert dialect.supports_add_column_if_not_exists() is False
        assert dialect.supports_drop_column_if_exists() is False
        assert dialect.supports_drop_constraint_if_exists() is False


class TestFirebirdGuardRaises:
    def test_add_column_if_not_exists_raises(self, dialect):
        action = AddColumn(
            dialect, ColumnDefinition("content", TextType()), if_not_exists=True
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_drop_column_if_exists_raises(self, dialect):
        action = DropColumn(dialect, column_name="x", if_exists=True)
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_drop_constraint_if_exists_raises(self, dialect):
        action = DropTableConstraint(dialect, constraint_name="fk", if_exists=True)
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()


class TestFirebirdPlainForms:
    def test_add_column_plain(self, dialect):
        action = AddColumn(dialect, ColumnDefinition("content", TextType()))
        sql, params = action.to_sql()
        assert sql.startswith("ADD COLUMN")
        assert "IF NOT EXISTS" not in sql
        assert params == ()

    def test_drop_column_plain(self, dialect):
        action = DropColumn(dialect, column_name="x")
        sql, params = action.to_sql()
        assert sql.startswith("DROP COLUMN")
        assert "IF EXISTS" not in sql
        assert params == ()