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
        if not getattr(expr, 'active', True):
            parts.append("INACTIVE")
        parts.append(expr.timing)
        parts.append(' OR '.join(expr.events))
        parts.append("ON")
        parts.append(self.format_identifier(expr.table_name))
        parts.append(f"POSITION {getattr(expr, 'position', 0)}")
        when_condition = getattr(expr, 'when_condition', None)
        if when_condition:
            parts.append(f"WHEN ({when_condition})")
        parts.append("AS")
        parts.append(expr.body)

        return ' '.join(parts), ()