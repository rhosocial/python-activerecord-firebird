# tests/rhosocial/activerecord_firebird_test/feature/backend/ddl/test_drop_table_cascade.py
"""Tests for DROP TABLE ... CASCADE/RESTRICT gating on Firebird.

Firebird has no CASCADE/RESTRICT keyword on DROP TABLE; both protocol
switches return False and the generic helper raises UnsupportedFeatureError.
"""

import pytest

from rhosocial.activerecord.backend.dialect import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import DropTableExpression
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect(version=(4, 0, 0))


class TestFirebirdDropTableCascade:
    def test_capability_switches(self, dialect):
        assert dialect.supports_drop_table_cascade() is False
        assert dialect.supports_drop_table_restrict() is False

    def test_cascade_rejected(self, dialect):
        expr = DropTableExpression(dialect, table="users", cascade=True)
        with pytest.raises(UnsupportedFeatureError, match="DROP TABLE ... CASCADE"):
            expr.to_sql()

    def test_restrict_rejected(self, dialect):
        expr = DropTableExpression(dialect, table="users", cascade=False)
        with pytest.raises(UnsupportedFeatureError, match="DROP TABLE ... RESTRICT"):
            expr.to_sql()

    def test_cascade_none_renders_plain(self, dialect):
        expr = DropTableExpression(dialect, table="users", cascade=None)
        sql, params = expr.to_sql()
        assert "CASCADE" not in sql
        assert "RESTRICT" not in sql
        assert params == ()
