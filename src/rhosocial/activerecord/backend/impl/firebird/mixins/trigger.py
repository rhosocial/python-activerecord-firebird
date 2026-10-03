# src/rhosocial/activerecord/backend/impl/firebird/mixins/trigger.py
"""Firebird trigger DDL mixin."""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_trigger import CreateTriggerExpression


class FirebirdTriggerMixin:

    def format_create_trigger(
        self,
        expr: "CreateTriggerExpression",
    ) -> Tuple[str, tuple]:
        parts = ["CREATE TRIGGER"]
        parts.append(self.format_identifier(expr.trigger_name))
        parts.append(expr.timing.value)
        parts.append(' OR '.join(e.value for e in expr.events))
        parts.append("ON")
        parts.append(expr.table.to_sql()[0])
        if expr.condition is not None:
            condition_sql, _ = expr.condition.to_sql()
            parts.append(f"WHEN ({condition_sql})")
        parts.append("AS")
        parts.append(f"EXECUTE {expr.function.to_sql()[0]}")

        return ' '.join(parts), ()