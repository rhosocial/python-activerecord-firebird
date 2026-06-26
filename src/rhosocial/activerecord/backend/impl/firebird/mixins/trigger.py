# src/rhosocial/activerecord/backend/impl/firebird/mixins/trigger.py
"""Firebird trigger DDL mixin."""

from typing import List, Optional, Tuple


class FirebirdTriggerMixin:

    def format_create_trigger(
        self,
        trigger_name: str,
        table_name: str,
        timing: str,
        events: List[str],
        body: str,
        position: int = 0,
        when_condition: Optional[str] = None,
        active: bool = True,
    ) -> Tuple[str, tuple]:
        parts = ["CREATE TRIGGER"]
        parts.append(self.format_identifier(trigger_name))
        if not active:
            parts.append("INACTIVE")
        parts.append(timing)
        parts.append(' OR '.join(events))
        parts.append("ON")
        parts.append(self.format_identifier(table_name))
        parts.append(f"POSITION {position}")
        if when_condition:
            parts.append(f"WHEN ({when_condition})")
        parts.append("AS")
        parts.append(body)

        return ' '.join(parts), ()