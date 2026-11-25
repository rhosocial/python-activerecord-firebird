# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/ddl/test_alter_table_guard.py
"""Tests for Firebird ALTER TABLE IF [NOT] EXISTS guarding.

Firebird <= 5.0.4 does not support ``ADD COLUMN IF NOT EXISTS``,
``DROP COLUMN IF EXISTS`` or ``DROP CONSTRAINT IF EXISTS``. Requesting
any of these modifiers must raise ``UnsupportedFeatureError``.

The same formatter also refuses a constraint dropped *by kind*: Firebird
spells no ``DROP PRIMARY KEY`` / ``DROP CHECK``, so a
``DropTableConstraintAction`` addressed only by its declaration is refused
by name as ``DROP CONSTRAINT by kind``. The name-only form is untouched.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.statements import (
    ColumnDefinition,
    TableConstraint,
    TableUniqueConstraint,
)
from rhosocial.activerecord.backend.expression.statements.ddl_alter import (
    AddColumnAction,
    DropColumnAction,
    DropTableConstraintAction,
)
from rhosocial.activerecord.backend.expression.types import TextType
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect()


class TestAlterTableModifierCapabilities:
    def test_supports_switches(self, dialect):
        assert dialect.supports_add_column_if_not_exists() is False
        assert dialect.supports_drop_column_if_exists() is False
        assert dialect.supports_drop_constraint_if_exists() is False

    def test_drop_constraint_by_kind_is_not_advertised(self, dialect):
        """Firebird drops by name only, so the by-kind probe stays ``False``."""
        assert dialect.supports_drop_constraint_by_kind() is False


class TestGuardRaises:
    def test_add_column_if_not_exists_is_refused(self, dialect):
        action = AddColumnAction(
            dialect, ColumnDefinition(dialect, "content", TextType(dialect)), if_not_exists=True
        )
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_drop_column_if_exists_is_refused(self, dialect):
        action = DropColumnAction(dialect, column_name="x", if_exists=True)
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()

    def test_drop_constraint_if_exists_is_refused(self, dialect):
        action = DropTableConstraintAction(dialect, constraint_name="fk", if_exists=True)
        with pytest.raises(UnsupportedFeatureError):
            action.to_sql()


def _unique(dialect):
    """A declaration the by-kind drop would have spelled ``DROP UNIQUE (a)``."""
    return TableConstraint(dialect, branch=TableUniqueConstraint(dialect, ["a"]), name="uq")


class TestDropByKindIsRefusedByName:
    """Firebird has no kind-addressed drop; the refusal has to say so.

    ``DROP PRIMARY KEY`` and ``DROP CHECK`` are both ``-104 Token unknown`` on
    Firebird 5.0.4, and the primary key has no namespace of its own: every
    constraint is dropped by the name ``RDB$RELATION_CONSTRAINTS`` records.
    A declaration-only action therefore has nothing this server can address,
    and the formatter must refuse it **by name** rather than reach the core
    formatter's generic answer or emit SQL the server rejects.
    """

    def test_declaration_only_is_refused_by_name(self, dialect):
        action = DropTableConstraintAction(dialect, constraint=_unique(dialect))
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            action.to_sql()
        assert "DROP CONSTRAINT by kind" in str(excinfo.value)

    def test_name_and_declaration_together_are_still_refused_by_kind(self, dialect):
        """The declaration guard sits first, so a name does not launder it."""
        action = DropTableConstraintAction(
            dialect, constraint_name="uq", constraint=_unique(dialect)
        )
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            action.to_sql()
        assert "DROP CONSTRAINT by kind" in str(excinfo.value)


class TestPlainForms:
    def test_add_column_plain(self, dialect):
        action = AddColumnAction(dialect, ColumnDefinition(dialect, "content", TextType(dialect)))
        sql, params = action.to_sql()
        assert sql.startswith("ADD COLUMN")
        assert "IF NOT EXISTS" not in sql
        assert params == ()

    def test_drop_column_plain(self, dialect):
        action = DropColumnAction(dialect, column_name="x")
        sql, params = action.to_sql()
        assert sql.startswith("DROP COLUMN")
        assert "IF EXISTS" not in sql
        assert params == ()

    def test_drop_constraint_plain_is_unchanged(self, dialect):
        """The by-kind refusal must not move the name-only rendering by a byte."""
        action = DropTableConstraintAction(dialect, constraint_name="fk")
        sql, params = action.to_sql()
        assert sql == 'DROP CONSTRAINT "FK"'
        assert params == ()
