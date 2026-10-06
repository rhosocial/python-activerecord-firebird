# src/rhosocial/activerecord/backend/impl/firebird/mixins/trigger.py
"""Firebird trigger DDL mixin."""

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.objects import Table, Trigger

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_trigger import CreateTriggerExpression


class FirebirdTriggerMixin:

    def format_create_trigger(
        self,
        expr: "CreateTriggerExpression",
    ) -> Tuple[str, tuple]:
        """Render CREATE TRIGGER over the two objects the statement names.

        Raises:
            TypeError: ``CreateTriggerExpression.trigger`` is not a Trigger, or
                ``CreateTriggerExpression.table`` is not a Table. Either object
                renders by its own kind's formatter, so a wrong kind would put a
                table's name after CREATE TRIGGER or a trigger's name after ON,
                and both read as valid SQL.
        """
        if not isinstance(expr.trigger, Trigger):
            raise TypeError(
                f"CreateTriggerExpression.trigger must be a Trigger, "
                f"got {type(expr.trigger).__name__}"
            )
        if not isinstance(expr.table, Table):
            raise TypeError(
                f"CreateTriggerExpression.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
        parts = ["CREATE TRIGGER"]
        # Both objects on the statement -- the trigger and the relation it fires
        # on -- render themselves, so a namespace slot either carries is
        # reported rather than dropped.
        parts.append(expr.trigger.to_sql()[0])
        if not getattr(expr, 'active', True):
            parts.append("INACTIVE")
        parts.append(expr.timing)
        parts.append(' OR '.join(expr.events))
        parts.append("ON")
        parts.append(expr.table.to_sql()[0])
        parts.append(f"POSITION {getattr(expr, 'position', 0)}")
        when_condition = getattr(expr, 'when_condition', None)
        if when_condition:
            parts.append(f"WHEN ({when_condition})")
        parts.append("AS")
        parts.append(expr.body)

        return ' '.join(parts), ()