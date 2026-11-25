# src/rhosocial/activerecord/backend/impl/firebird/suggestion/column_reorder_suggestion.py
"""Firebird's column-reorder answer.

Unlike most engines, Firebird has a native in-place clause: ``ALTER TABLE ...
ALTER COLUMN ... POSITION n`` (Firebird 5.0 Language Reference, 5.4.2.8 "Changing
the Position of a Column"). The same clause is already in the Firebird 3.0
Language Reference, and this dialect's ``format_set_position_action`` pins the
floor at 3.0. A reorder is therefore a real chain of existing
``SetPositionAction`` nodes -- one ``AlterTableStatement`` per action -- rather
than an explicit "unsupported" answer.

The point carries names only. A position-only chain is possible only when the
column set is unchanged: POSITION moves an existing column; it cannot add or
drop one. A point whose old and new orders hold different columns is declined.
"""
from __future__ import annotations

from typing import List

from rhosocial.activerecord.backend.suggestion import ColumnReorderSuggestion
from rhosocial.activerecord.backend.expression.objects import Table
from rhosocial.activerecord.backend.expression.statements import AlterTableStatement

from ..expression import SetPositionAction
from ._change_points import answer

__all__ = ["FirebirdColumnReorderSuggestionMixin"]

#: POSITION appears in the Firebird 3.0 Language Reference; 2.5 has no clause.
POSITION_VERSION_FLOOR = (3, 0, 0)


class FirebirdColumnReorderSuggestionMixin:
    """Answer a column-reorder point with native Firebird POSITION actions."""

    def suggest_column_reorder(
        self, point: ColumnReorderSuggestion
    ) -> ColumnReorderSuggestion:
        """Return a one-action-per-statement POSITION chain, False or None.

        Positions are chosen by simulating the moves left to right: for each
        final slot, the column that belongs there is moved to that slot only if
        it is not there already. Working from slot 1 upward keeps the already
        placed prefix fixed, so the chain reaches the declared order even when
        several columns move (it does not depend on the order the planner
        listed them in).

        ``None`` means the point states no reorder; ``False`` means this dialect
        cannot claim POSITION (unknown or pre-3.0 server) or the point's column
        set changed and cannot be fixed by repositioning alone.
        """
        old_order = tuple(point.old_order or ())
        new_order = tuple(point.new_order or ())
        if not point.reordered_columns or not old_order or not new_order:
            return answer(point, None)
        if len(old_order) != len(new_order) or set(old_order) != set(new_order):
            # POSITION moves an existing column; ADD/DROP COLUMN are separate
            # statements and are not part of this point's contract.
            return answer(point, False)
        if not self.version_at_least(POSITION_VERSION_FLOOR):
            return answer(point, False)

        current: List[str] = list(old_order)
        chain: List[AlterTableStatement] = []
        table = Table(self, point.table_name)
        for final_position, wanted in enumerate(new_order, start=1):
            if current[final_position - 1] == wanted:
                continue
            chain.append(
                AlterTableStatement(
                    self,
                    table,
                    [SetPositionAction(self, wanted, final_position)],
                )
            )
            at = current.index(wanted)
            current.insert(final_position - 1, current.pop(at))
        if not chain:
            return answer(point, None)
        return answer(point, tuple(chain))
