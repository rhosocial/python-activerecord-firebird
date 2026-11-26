# tests/rhosocial/activerecord_firebird_test/feature/query/firebird/test_firebird_explain_deep.py
"""Firebird-local EXPLAIN capability gate tests (deep EXPLAIN is NOT applicable).

Firebird has **no** DSQL statement equivalent to EXPLAIN that returns a plan.
``EXPLAIN PLAN FOR ...`` is an *isql client* command, not something the engine
accepts over the wire: DSQL rejects it with SQLSTATE -104
("Token unknown - EXPLAIN"). There is consequently no plan to interpret -- no
``Seq Scan`` / ``Index Scan`` rows, no cost tree, no partition-pruning evidence,
no ``PLAN_TABLE`` -- so this file deliberately contains **no plan assertions**
and does not copy the core/SQLite deep-EXPLAIN tests (which also pull in the
``aiosqlite`` dependency this backend does not have).

What *is* true and testable locally is the capability contract:

1. ``supports_explain_plan()`` is ``False`` (and the related analyze/format
   probes are closed too). This is the gate the shared testsuite ``test_explain``
   contracts in ``cte/``, ``setop/`` and ``query_integration/`` check: they
   call ``pytest.skip(...)`` before ever running a query, so they SKIP cleanly
   on Firebird instead of failing against the engine's -104 error.

2. EXPLAIN *rendering* only ever emits SQL text -- the isql-only
   ``EXPLAIN PLAN FOR <select>`` command plus the inner statement's params.
   It never fabricates plan rows, and it does not inject unsupported
   ``ANALYZE`` / ``FORMAT`` / ``VERBOSE`` / type clauses (which would be a
   bogus statement Firebird cannot honor). All construction-level, no DB.
"""

import pytest
from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError
from rhosocial.activerecord.backend.dialect.protocols import ExplainSupport
from rhosocial.activerecord.backend.expression import (
    ExplainFormat,
    ExplainOptions,
    Literal,
)
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.sources import NamedRelationRef
from rhosocial.activerecord.backend.expression.statements import (
    ExplainStatement,
    QueryStatement,
)

from rhosocial.activerecord.backend.impl.firebird.dialect import FirebirdDialect

pytestmark = pytest.mark.firebird


def _explain_of(dialect, options=None):
    """Build an EXPLAIN over ``SELECT * FROM "USERS"`` without touching a DB."""
    select = QueryStatement(
        dialect=dialect,
        select=[Literal(dialect, "*")],
        from_=NamedRelationRef(dialect, Table(dialect, "USERS")),
    )
    return ExplainStatement(dialect, statement=select, options=options)


class TestFirebirdExplainCapabilityGate:
    """The capability gate that makes shared ``test_explain`` contracts skip."""

    def test_dialect_advertises_no_explain_plan(self, dialect):
        """Firebird reports no plan-returning EXPLAIN, so shared contracts skip."""
        assert dialect.supports_explain_plan() is False, (
            "Firebird has no DSQL EXPLAIN; if this gate opens, the shared "
            "test_explain contracts will run 'EXPLAIN PLAN FOR' and fail with -104"
        )
        assert isinstance(dialect, ExplainSupport)

    @pytest.mark.parametrize("version", [(2, 5, 0), (3, 0, 0), (4, 0, 0)])
    def test_explain_plan_gate_closed_for_every_version(self, version):
        """The gate is version-independent -- never flip it for newer Firebird."""
        d = FirebirdDialect()
        d.version = version
        assert d.supports_explain_plan() is False

    def test_related_explain_option_gates_are_closed(self, dialect):
        """No ANALYZE / FORMAT / option gates either -- Firebird honors none."""
        assert dialect.supports_explain_analyze() is False
        for probe in (
            "supports_explain_verbose",
            "supports_explain_costs",
            "supports_explain_buffers",
            "supports_explain_timing",
            "supports_explain_settings",
            "supports_explain_wal",
            "supports_explain_format_text",
            "supports_explain_format_json",
            "supports_explain_format_xml",
            "supports_explain_format_yaml",
            "supports_explain_format_tree",
            "supports_explain_format_traditional",
        ):
            assert getattr(dialect, probe)() is False, probe


class TestFirebirdExplainRendering:
    """Rendering yields invalid-DSQL text, never a fabricated plan."""

    def test_render_returns_isql_only_sql_text_not_a_plan(self, dialect):
        """format_explain_statement returns (sql, params); no plan rows exist."""
        result = dialect.format_explain_statement(_explain_of(dialect))

        assert (
            isinstance(result, tuple) and len(result) == 2
        ), "rendering must return (sql, params) text, not a fabricated plan"
        sql, params = result
        assert isinstance(sql, str)
        assert sql.startswith("EXPLAIN PLAN FOR "), (
            "isql-only 'EXPLAIN PLAN FOR' is emitted verbatim; Firebird DSQL "
            "rejects it with -104, so it can never be mistaken for a plan"
        )
        assert 'SELECT ? FROM "USERS"' in sql
        # The inner statement's params are passed through unchanged.
        assert tuple(params) == ("*",)

    def test_to_sql_matches_dialect_renderer(self, dialect):
        """ExplainStatement.to_sql() delegates to the same rendering path."""
        expr = _explain_of(dialect)
        assert expr.to_sql() == dialect.format_explain_statement(expr)

    @pytest.mark.parametrize(
        "options,option",
        [
            (ExplainOptions(analyze=True), "EXPLAIN ANALYZE"),
            (ExplainOptions(format=ExplainFormat.JSON), "EXPLAIN FORMAT JSON"),
            (ExplainOptions(costs=False), "EXPLAIN COSTS"),
            (ExplainOptions(buffers=True), "EXPLAIN BUFFERS"),
            (ExplainOptions(verbose=True), "EXPLAIN VERBOSE"),
            (ExplainOptions(settings=True), "EXPLAIN SETTINGS"),
            (ExplainOptions(wal=True), "EXPLAIN WAL"),
        ],
    )
    def test_unsupported_options_are_refused_by_name(self, dialect, options, option):
        """An option Firebird cannot honor is refused, never silently dropped."""
        with pytest.raises(UnsupportedFeatureError, match=option):
            dialect.format_explain_statement(_explain_of(dialect, options))

    def test_default_options_request_nothing(self, dialect):
        """``costs`` defaults to True, so a default option set asks for no clause."""
        sql, _params = dialect.format_explain_statement(
            _explain_of(dialect, ExplainOptions())
        )
        assert sql == 'EXPLAIN PLAN FOR SELECT ? FROM "USERS"'
