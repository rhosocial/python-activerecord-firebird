# tests/rhosocial/activerecord_firebird_test/feature/backend/dialect/test_returning_capabilities.py
"""Firebird RETURNING capability tests."""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.core import Column
from rhosocial.activerecord.backend.expression.statements import ReturningClause
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

pytestmark = [pytest.mark.feature, pytest.mark.backend]


@pytest.fixture
def dialect():
    return FirebirdDialect(version=(5, 0, 0))


class TestFirebirdReturningCapabilities:
    def test_dml_returning_supported(self, dialect):
        assert dialect.supports_returning_insert() is True
        assert dialect.supports_returning_update() is True
        assert dialect.supports_returning_delete() is True

    def test_alias_unsupported(self, dialect):
        assert dialect.supports_returning_alias() is False

    def test_single_row(self, dialect):
        assert dialect.supports_returning_single_row() is True


class TestFirebirdReturningFormatting:
    def test_column_renders(self, dialect):
        clause = ReturningClause(dialect, expressions=[Column(dialect, "id")])
        sql, _ = dialect.format_returning_clause(clause)
        assert "RETURNING" in sql

    def test_alias_rejected(self, dialect):
        clause = ReturningClause(dialect, expressions=[Column(dialect, "id")], alias="r")
        with pytest.raises(UnsupportedFeatureError, match="alias in RETURNING"):
            dialect.format_returning_clause(clause)
