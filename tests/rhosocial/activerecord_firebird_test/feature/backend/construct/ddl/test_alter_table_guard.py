# tests/rhosocial/activerecord_firebird_test/feature/backend/construct/ddl/test_alter_table_guard.py
"""Tests for Firebird ALTER TABLE IF [NOT] EXISTS guarding.

Firebird <= 5.0.4 does not support ``ADD COLUMN IF NOT EXISTS``,
``DROP COLUMN IF EXISTS`` or ``DROP CONSTRAINT IF EXISTS``. Requesting
any of these modifiers must raise ``UnsupportedFeatureError``.

The same formatter also refuses a constraint dropped *by kind*: Firebird
spells no ``DROP PRIMARY KEY`` / ``DROP CHECK``, so a
``DropTableConstraintAction`` addressed only by its declaration is refused
by name as ``DROP CONSTRAINT by kind``.

A declaration supplied alongside a name is not a second address: it only
**confirms** the name when it carries that same name, and the drop renders
byte-identically to the name-only form. A declaration whose name differs, or
one with no name at all, is an **ambiguous address** and is refused as
``DROP CONSTRAINT address`` -- core's one resolution rule, never a per-backend
preference. The name-only form is untouched.
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


def _unique(dialect, name="uq"):
    """A declaration the by-kind drop would have spelled ``DROP UNIQUE (a)``."""
    return TableConstraint(dialect, branch=TableUniqueConstraint(dialect, ["a"]), name=name)


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
        assert excinfo.value.feature_name == "DROP CONSTRAINT by kind"

    def test_declaration_only_is_still_refused_by_kind(self, dialect):
        """The probe answers ``False``, so the resolver itself refuses kinds.

        The local declaration guard is gone: the refusal now comes from
        ``_resolve_drop_constraint_address``, which reaches the same conclusion
        because this backend advertises no kind spelling.
        """
        action = DropTableConstraintAction(dialect, constraint=_unique(dialect))
        assert dialect.supports_drop_constraint_by_kind() is False
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            dialect._resolve_drop_constraint_address(action)
        assert excinfo.value.feature_name == "DROP CONSTRAINT by kind"


class TestDropConstraintAddress:
    """A declaration beside a name confirms the name, or is an ambiguity.

    The address rule is core's ``_resolve_drop_constraint_address``; this
    formatter only consumes its answer, so the tests pin the formatter's
    behaviour for each answer rather than restating the rule.
    """

    def test_equal_declaration_name_renders(self, dialect):
        action = DropTableConstraintAction(
            dialect, constraint_name="uq", constraint=_unique(dialect, "uq")
        )
        assert dialect._resolve_drop_constraint_address(action) == "name"
        sql, params = action.to_sql()
        assert sql == 'DROP CONSTRAINT "UQ"'
        assert params == ()

    def test_equal_declaration_renders_byte_identically_to_name_only(self, dialect):
        """The confirming declaration adds no second address to the SQL."""
        name_only = DropTableConstraintAction(dialect, constraint_name="uq")
        confirmed = DropTableConstraintAction(
            dialect, constraint_name="uq", constraint=_unique(dialect, "uq")
        )
        assert confirmed.to_sql() == name_only.to_sql()
        assert confirmed.to_sql() == ('DROP CONSTRAINT "UQ"', ())

    def test_differing_declaration_name_is_an_ambiguous_address(self, dialect):
        action = DropTableConstraintAction(
            dialect, constraint_name="uq", constraint=_unique(dialect, "uq_other")
        )
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            action.to_sql()
        assert excinfo.value.feature_name == "DROP CONSTRAINT address"
        message = str(excinfo.value)
        assert "'uq'" in message
        assert "'uq_other'" in message
        assert "ambiguous address is refused" in message

    def test_unnamed_declaration_is_an_ambiguous_address(self, dialect):
        action = DropTableConstraintAction(
            dialect, constraint_name="uq", constraint=_unique(dialect, None)
        )
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            action.to_sql()
        assert excinfo.value.feature_name == "DROP CONSTRAINT address"
        assert "ambiguous address is refused" in str(excinfo.value)

    def test_ambiguous_address_is_reported_before_the_if_exists_guard(self, dialect):
        """Address resolution precedes the modifier guard, as it must."""
        action = DropTableConstraintAction(
            dialect,
            constraint_name="uq",
            constraint=_unique(dialect, "uq_other"),
            if_exists=True,
        )
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            action.to_sql()
        assert excinfo.value.feature_name == "DROP CONSTRAINT address"
        assert "IF EXISTS" not in str(excinfo.value)

    def test_equal_declaration_still_reaches_the_if_exists_guard(self, dialect):
        """A resolved name does not launder an unsupported modifier."""
        action = DropTableConstraintAction(
            dialect, constraint_name="uq", constraint=_unique(dialect, "uq"), if_exists=True
        )
        with pytest.raises(UnsupportedFeatureError) as excinfo:
            action.to_sql()
        assert excinfo.value.feature_name == "DROP CONSTRAINT IF EXISTS"
        assert "IF EXISTS" in str(excinfo.value)

    def test_a_kind_advertising_subclass_has_no_kind_spelling(self):
        """The resolver's ``"kind"`` answer has no spelling in this backend.

        This backend answers ``False`` to the probe, so the branch is only
        reachable through a subclass. It must refuse by name rather than reach
        core's generic answer or emit nothing.
        """

        class KindDropDialect(FirebirdDialect):
            def supports_drop_constraint_by_kind(self) -> bool:
                return True

        kind_dialect = KindDropDialect()
        action = DropTableConstraintAction(kind_dialect, constraint=_unique(kind_dialect, "uq"))
        assert kind_dialect._resolve_drop_constraint_address(action) == "kind"
        with pytest.raises(NotImplementedError, match="no kind spelling"):
            action.to_sql()


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
