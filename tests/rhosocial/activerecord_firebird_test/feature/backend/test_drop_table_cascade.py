# tests/rhosocial/activerecord_firebird_test/feature/backend/test_drop_table_cascade.py
"""Tests for DROP TABLE ... CASCADE/RESTRICT gating on Firebird.

Firebird has no CASCADE/RESTRICT keyword on DROP TABLE; both protocol
switches return False and the generic helper raises UnsupportedFeatureError.
"""

import pytest

from rhosocial.activerecord.backend.dialect import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import DropTableExpression
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect(version=(4, 0, 0))


class TestFirebirdDropTableCascade:
    def test_capability_switches(self, dialect):
        assert dialect.supports_drop_table_cascade() is False
        assert dialect.supports_drop_table_restrict() is False

    def test_cascade_rejected(self, dialect):
        expr = DropTableExpression(dialect, table=Table(dialect, "users"), cascade=True)
        with pytest.raises(UnsupportedFeatureError, match="DROP TABLE ... CASCADE"):
            expr.to_sql()

    def test_restrict_rejected(self, dialect):
        """RESTRICT has its own parameter; it is no longer spelled by falsy CASCADE."""
        expr = DropTableExpression(dialect, table=Table(dialect, "users"), restrict=True)
        with pytest.raises(UnsupportedFeatureError, match="DROP TABLE ... RESTRICT"):
            expr.to_sql()

    def test_neither_set_renders_plain(self, dialect):
        expr = DropTableExpression(dialect, table=Table(dialect, "users"))
        sql, params = expr.to_sql()
        assert "CASCADE" not in sql
        assert "RESTRICT" not in sql
        assert params == ()

    def test_both_set_is_refused_at_construction(self, dialect):
        with pytest.raises(
            ValueError, match="cascade and restrict are mutually exclusive options"
        ):
            DropTableExpression(
                dialect, table=Table(dialect, "users"), cascade=True, restrict=True
            )
