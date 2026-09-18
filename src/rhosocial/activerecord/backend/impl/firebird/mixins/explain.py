# src/rhosocial/activerecord/backend/impl/firebird/mixins/explain.py
"""Firebird EXPLAIN mixin."""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.explain import ExplainExpression


class FirebirdExplainMixin:

    def supports_explain_plan(self) -> bool:
        # ``EXPLAIN PLAN FOR`` is an isql client command, not a valid DSQL
        # statement. Firebird's engine rejects it with SQLSTATE -104 "Token
        # unknown - EXPLAIN", so plan extraction is not available in DSQL.
        return False

    def format_explain_statement(self, expr: "ExplainExpression") -> Tuple[str, tuple]:
        statement_sql, statement_params = expr.statement.to_sql()
        return f"EXPLAIN PLAN FOR {statement_sql}", statement_params
