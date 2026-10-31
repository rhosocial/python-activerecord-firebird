# src/rhosocial/activerecord/backend/impl/firebird/mixins/trigger.py
"""Firebird trigger DDL mixin."""

from typing import Tuple, TYPE_CHECKING

from rhosocial.activerecord.backend.expression.objects import Table, Trigger

if TYPE_CHECKING:
    from rhosocial.activerecord.backend.expression.statements.ddl_trigger import CreateTriggerStatement


class FirebirdTriggerMixin:

    def format_create_trigger(
        self,
        expr: "CreateTriggerStatement",
    ) -> Tuple[str, tuple]:
        """Render CREATE TRIGGER over the two objects the statement names.

        Nothing dispatches here today: :class:`CreateTriggerStatement` names
        ``format_create_trigger_statement`` and that resolves to the core
        ``TriggerMixin`` renderer, whose SQL:1999 shape is what this backend
        currently emits. The method is kept in step with the statement's
        declared contract rather than deleted, so the day this backend grows
        its own trigger DDL it starts from a renderer that reads real fields.

        Raises:
            TypeError: ``CreateTriggerStatement.trigger`` is not a Trigger, or
                ``CreateTriggerStatement.table`` is not a Table. Either object
                renders by its own kind's formatter, so a wrong kind would put a
                table's name after CREATE TRIGGER or a trigger's name after ON,
                and both read as valid SQL.
        """
        if not isinstance(expr.trigger, Trigger):
            raise TypeError(
                f"CreateTriggerStatement.trigger must be a Trigger, "
                f"got {type(expr.trigger).__name__}"
            )
        if not isinstance(expr.table, Table):
            raise TypeError(
                f"CreateTriggerStatement.table must be a Table, "
                f"got {type(expr.table).__name__}"
            )
        parts = ["CREATE TRIGGER"]
        # Both objects on the statement -- the trigger and the relation it fires
        # on -- render themselves, so a namespace slot either carries is
        # reported rather than dropped.
        parts.append(expr.trigger.to_sql()[0])
        parts.append(expr.timing.value)
        parts.append(' OR '.join(e.value for e in expr.events))
        parts.append("ON")
        parts.append(expr.table.to_sql()[0])
        # ``condition`` is the statement's WHEN clause -- the only condition
        # field the contract declares, so it is the only one read. The former
        # ``active`` / ``position`` / ``when_condition`` / ``body`` reads
        # probed fields no node carries: their getattr defaults answered
        # "absent" for every instance, so those branches never rendered.
        if expr.condition is not None:
            condition_sql, _ = expr.condition.to_sql()
            parts.append(f"WHEN ({condition_sql})")
        parts.append("AS")
        parts.append(f"EXECUTE {expr.function.to_sql()[0]}")

        return ' '.join(parts), ()
