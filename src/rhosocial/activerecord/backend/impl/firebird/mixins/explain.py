# src/rhosocial/activerecord/backend/impl/firebird/mixins/explain.py
"""Firebird EXPLAIN mixin."""

from typing import Optional, Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.dialect.exceptions import UnsupportedFeatureError

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.explain import ExplainStatement


class FirebirdExplainMixin:
    """Firebird answers every EXPLAIN capability switch with False.

    ``EXPLAIN PLAN FOR`` is an isql client command, not a DSQL statement: the
    engine rejects it with SQLSTATE -104 ("Token unknown - EXPLAIN"). There is
    therefore no DSQL EXPLAIN to plan, and no ``FORMAT``/``ANALYZE``/option
    grammar either, so every per-format and per-option switch is closed. The
    renderer still emits the isql-only text for a caller that wants the client
    command, but an option it cannot honor is refused by name rather than
    silently dropped.
    """

    def supports_explain_plan(self) -> bool:
        # ``EXPLAIN PLAN FOR`` is an isql client command, not a valid DSQL
        # statement. Firebird's engine rejects it with SQLSTATE -104 "Token
        # unknown - EXPLAIN", so plan extraction is not available in DSQL.
        return False

    def supports_explain_analyze(self) -> bool:
        return False

    def supports_explain_verbose(self) -> bool:
        return False

    def supports_explain_costs(self) -> bool:
        return False

    def supports_explain_buffers(self) -> bool:
        return False

    def supports_explain_timing(self) -> bool:
        return False

    def supports_explain_settings(self) -> bool:
        return False

    def supports_explain_wal(self) -> bool:
        return False

    def supports_explain_format_text(self) -> bool:
        return False

    def supports_explain_format_json(self) -> bool:
        return False

    def supports_explain_format_xml(self) -> bool:
        return False

    def supports_explain_format_yaml(self) -> bool:
        return False

    def supports_explain_format_tree(self) -> bool:
        return False

    def supports_explain_format_traditional(self) -> bool:
        return False

    def format_explain_statement(self, expr: "ExplainStatement") -> Tuple[str, tuple]:
        """Render the isql-only ``EXPLAIN PLAN FOR`` text.

        Raises:
            UnsupportedFeatureError: An option (ANALYZE, FORMAT, COSTS,
                BUFFERS, TIMING, VERBOSE, SETTINGS, WAL) was requested.
                Firebird has no DSQL EXPLAIN grammar for any of them, and
                dropping the option silently would misreport what was asked.
        """
        if expr.options is not None:
            requested = self._requested_explain_option(expr.options)
            if requested is not None:
                raise UnsupportedFeatureError(self.name, requested)
        statement_sql, statement_params = expr.statement.to_sql()
        return f"EXPLAIN PLAN FOR {statement_sql}", statement_params

    def _requested_explain_option(self, options) -> Optional[str]:
        """The EXPLAIN clause *options* asks for, or None if none is set.

        Mirrors the core formatter's conditions: ``costs`` defaults to True,
        so only ``costs=False`` is a request.
        """
        from rhosocial.activerecord.backend.expression.statements.explain import (
            ExplainType,
        )

        if options.type == ExplainType.ANALYZE or options.analyze:
            return "EXPLAIN ANALYZE"
        if options.format:
            return f"EXPLAIN FORMAT {options.format.value}"
        if not options.costs:
            return "EXPLAIN COSTS"
        if options.buffers:
            return "EXPLAIN BUFFERS"
        if options.timing and options.analyze:
            return "EXPLAIN TIMING"
        if options.verbose:
            return "EXPLAIN VERBOSE"
        if options.settings:
            return "EXPLAIN SETTINGS"
        if options.wal:
            return "EXPLAIN WAL"
        return None


__all__ = ["FirebirdExplainMixin"]
