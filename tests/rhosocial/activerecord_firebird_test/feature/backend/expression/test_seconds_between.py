# tests/rhosocial/activerecord_firebird_test/feature/backend/expression/test_seconds_between.py
"""Firebird's spelling for ``seconds_between``.

The node from core asks one question -- signed seconds from ``start`` to
``end`` -- and Firebird answers it with ``DATEDIFF``: the unit is a keyword of
the call, not a bind value, and ``MILLISECOND`` is the finest unit the engine
keeps. These tests pin the rendered text, the order of the bind parameters,
the alias, and the operand the node keeps. They need no connection; what the
spelling *means* on a server is measured in
``feature/basic/ddl/test_firebird_seconds_between_live.py``.
"""

from datetime import datetime

from rhosocial.activerecord.backend.expression import (
    Column,
    Literal,
    QueryStatement,
    seconds_between,
)
from rhosocial.activerecord.backend.expression.datetime import (
    SecondsBetweenExpression,
)
from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect


class TestSpelling:
    """The SQL Firebird writes for the node."""

    def test_columns_spell_milliseconds_and_thousandths(self):
        dialect = FirebirdDialect()
        sql, params = seconds_between(
            dialect,
            Column(dialect, "queued_at"),
            Column(dialect, "started_at"),
        ).to_sql()
        assert sql == (
            '(DATEDIFF(MILLISECOND FROM "QUEUED_AT" TO "STARTED_AT") * 0.001)'
        )
        assert params == ()

    def test_the_surrounding_select_and_alias(self):
        dialect = FirebirdDialect()
        elapsed = seconds_between(
            dialect,
            Column(dialect, "queued_at"),
            Column(dialect, "started_at"),
        ).as_("queue_seconds")
        sql, params = QueryStatement(dialect, select=[elapsed]).to_sql()
        assert sql == (
            'SELECT (DATEDIFF(MILLISECOND FROM "QUEUED_AT" TO "STARTED_AT") '
            '* 0.001) AS "QUEUE_SECONDS"'
        )
        assert params == ()

    def test_alias_survives_on_the_bare_node(self):
        dialect = FirebirdDialect()
        sql, params = seconds_between(
            dialect,
            Literal(dialect, datetime(2026, 6, 4, 10, 0, 0)),
            Literal(dialect, datetime(2026, 6, 4, 11, 0, 0)),
        ).as_("elapsed").to_sql()
        assert sql == '(DATEDIFF(MILLISECOND FROM ? TO ?) * 0.001) AS "ELAPSED"'
        assert params == (datetime(2026, 6, 4, 10, 0, 0), datetime(2026, 6, 4, 11, 0, 0))


class TestBindOrder:
    """Placeholders are bound in the order they appear in the SQL."""

    def test_start_precedes_end_because_the_sql_says_so(self):
        dialect = FirebirdDialect()
        start = datetime(2026, 6, 4, 10, 0, 0)
        end = datetime(2026, 6, 4, 11, 0, 0)
        sql, params = seconds_between(
            dialect,
            Literal(dialect, start),
            Literal(dialect, end),
        ).to_sql()
        assert sql == '(DATEDIFF(MILLISECOND FROM ? TO ?) * 0.001)'
        assert params == (start, end)

    def test_distinct_values_prove_the_order_is_not_reversed(self):
        dialect = FirebirdDialect()
        start = datetime(2026, 1, 31, 23, 59, 59, 900_000)
        end = datetime(2026, 2, 1, 0, 0, 0, 100_000)
        _sql, params = seconds_between(
            dialect,
            Literal(dialect, start),
            Literal(dialect, end),
        ).to_sql()
        assert params[0] == start
        assert params[1] == end

    def test_columns_add_no_parameters(self):
        dialect = FirebirdDialect()
        _sql, params = seconds_between(
            dialect,
            Column(dialect, "started_at"),
            Column(dialect, "ended_at"),
        ).to_sql()
        assert params == ()


class TestNode:
    """The node is core's, and the receiver keeps both operands."""

    def test_start_and_end_are_the_operands_given(self):
        dialect = FirebirdDialect()
        start = Column(dialect, "started_at")
        end = Column(dialect, "ended_at")
        expr = seconds_between(dialect, start, end)
        assert isinstance(expr, SecondsBetweenExpression)
        assert expr.start is start
        assert expr.end is end

    def test_it_dispatches_to_the_seconds_between_formatter(self):
        dialect = FirebirdDialect()
        expr = seconds_between(
            dialect,
            Column(dialect, "started_at"),
            Column(dialect, "ended_at"),
        )
        assert expr.format_method == "format_seconds_between_expression"
