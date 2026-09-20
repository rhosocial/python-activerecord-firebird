# tests/rhosocial/activerecord_firebird_test/feature/backend/dialect/test_view_index_capabilities.py
"""Firebird capability accuracy: CASCADE view and functional indexes.

Firebird has no ``DROP VIEW ... CASCADE`` clause and its expression
(computed) indexes use ``COMPUTED BY`` syntax, which the generic index
renderer does not emit. Both capabilities are therefore declared False so
the layer fails fast instead of emitting invalid SQL.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.statements import DropViewExpression
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect(version=(5, 0, 0))


def test_cascade_view_unsupported(dialect):
    assert dialect.supports_cascade_view() is False
    expr = DropViewExpression(dialect, view_name="v", cascade=True)
    with pytest.raises(UnsupportedFeatureError, match="CASCADE"):
        expr.to_sql()


def test_functional_index_unsupported(dialect):
    assert dialect.supports_functional_index() is False
