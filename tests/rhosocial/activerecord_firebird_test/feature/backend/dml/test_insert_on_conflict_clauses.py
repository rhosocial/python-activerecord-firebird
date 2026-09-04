# tests/rhosocial/activerecord_firebird_test/feature/backend/dml/test_insert_on_conflict_clauses.py
"""Tests for Firebird ON CONFLICT clause capability.

Firebird expresses upsert via UPDATE OR INSERT, not the ON CONFLICT
clause form. Covers:
- Capability switches: both on_conflict switches False.
- Any ON CONFLICT clause raises UnsupportedFeatureError instead of being
  silently dropped by format_insert_statement.
"""

import pytest

from rhosocial.activerecord.backend.dialect import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    InsertExpression,
    Literal,
    OnConflictClause,
    ValuesSource,
)
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect(version=(4, 0, 0))


class TestFirebirdOnConflictCapabilities:
    """Capability switch tests."""

    def test_supports_upsert_via_update_or_insert(self, dialect):
        assert dialect.supports_upsert() is True
        assert dialect.get_upsert_syntax_type() == "UPDATE OR INSERT"

    def test_does_not_support_on_conflict_clause(self, dialect):
        assert dialect.supports_on_conflict_clause() is False
        assert dialect.supports_multiple_on_conflict_clauses() is False

    def test_on_conflict_clause_rejected_not_dropped(self, dialect):
        """Regression: on_conflict used to be silently dropped; now it raises."""
        source = ValuesSource(dialect, values_list=[[Literal(dialect, 1)]])
        clause = OnConflictClause(dialect, conflict_target=["id"], do_nothing=True)
        expr = InsertExpression(dialect, into="users", source=source, on_conflict=clause)

        with pytest.raises(UnsupportedFeatureError, match="does not support ON CONFLICT"):
            expr.to_sql()

    def test_multiple_on_conflict_clauses_rejected(self, dialect):
        source = ValuesSource(dialect, values_list=[[Literal(dialect, 1)]])
        clause1 = OnConflictClause(dialect, conflict_target=["a"], do_nothing=True)
        clause2 = OnConflictClause(dialect, conflict_target=["b"], do_nothing=True)
        expr = InsertExpression(dialect, into="t", source=source, on_conflict=[clause1, clause2])

        with pytest.raises(UnsupportedFeatureError):
            expr.to_sql()

    def test_plain_insert_still_works(self, dialect):
        """An INSERT without on_conflict renders normally."""
        source = ValuesSource(dialect, values_list=[[Literal(dialect, 1)]])
        expr = InsertExpression(dialect, into="users", columns=["id"], source=source)
        sql, params = expr.to_sql()
        assert "INSERT INTO" in sql
        assert params == (1,)
