# tests/rhosocial/activerecord_firebird_test/feature/backend/dialect/test_dql_capabilities.py
"""Firebird DQL capability tests: NULLS ordering and WITH TIES fail-fast."""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression import (
    Column,
    LimitOffsetClause,
    OrderByClause,
    OrderByExpression,
)
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect(version=(5, 0, 0))


def test_nulls_first_last_supported(dialect):
    assert dialect.supports_nulls_first_last() is True
    sql, _ = OrderByClause(
        dialect,
        expressions=[OrderByExpression(dialect, Column(dialect, "name"), nulls_first=True)],
    ).to_sql()
    assert "NULLS FIRST" in sql


def test_fetch_with_ties_unsupported(dialect):
    assert dialect.supports_fetch_with_ties() is False
    with pytest.raises(UnsupportedFeatureError, match="WITH TIES"):
        dialect.format_limit_offset_clause(LimitOffsetClause(dialect, limit=5, with_ties=True))
