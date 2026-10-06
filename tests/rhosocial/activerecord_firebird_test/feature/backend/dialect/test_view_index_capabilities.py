# tests/rhosocial/activerecord_firebird_test/feature/backend/dialect/test_view_index_capabilities.py
"""Firebird capability accuracy for views and indexes.

Firebird has no ``DROP VIEW ... CASCADE`` clause, no
``CREATE OR REPLACE VIEW``, no ``WITH CHECK OPTION``, and its expression
(computed) indexes use ``COMPUTED BY`` syntax, which the generic index
renderer does not emit. All four capabilities are therefore declared False so
the layer fails fast instead of emitting invalid SQL.
"""

import pytest

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.expression.objects import View
from rhosocial.activerecord.backend.expression.statements import DropViewExpression
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


@pytest.fixture
def dialect():
    return FirebirdDialect(version=(5, 0, 0))


def test_cascade_view_unsupported(dialect):
    assert dialect.supports_cascade_view() is False
    expr = DropViewExpression(dialect, view=View(dialect, "v"), cascade=True)
    with pytest.raises(UnsupportedFeatureError, match="CASCADE"):
        expr.to_sql()


def test_functional_index_unsupported(dialect):
    assert dialect.supports_functional_index() is False


def test_or_replace_view_unsupported(dialect):
    # Firebird 4.0 added CREATE OR ALTER VIEW, which also alters an existing
    # view's columns; it is not the statement CREATE OR REPLACE VIEW names,
    # so the switch stays False rather than standing in for it.
    assert dialect.supports_or_replace_view() is False


def test_view_check_option_unsupported(dialect):
    # Firebird views are updatable unconditionally; the grammar has no
    # WITH [LOCAL|CASCADED] CHECK OPTION clause to render.
    assert dialect.supports_view_check_option() is False


def test_collation_supported(dialect):
    assert dialect.supports_collation() is True


def test_unique_index_supported(dialect):
    assert dialect.supports_unique_index() is True
