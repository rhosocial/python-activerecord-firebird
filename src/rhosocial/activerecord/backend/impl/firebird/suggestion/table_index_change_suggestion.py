# src/rhosocial/activerecord/backend/impl/firebird/suggestion/table_index_change_suggestion.py
"""Firebird's table-index change answer.

Firebird spells index creation and removal as standalone ``CREATE INDEX`` and
``DROP INDEX`` statements. Its ``ALTER TABLE`` grammar (Firebird 5.0 Language
Reference, 5.4.2) lists ADD COLUMN, ADD <tconstraint>, DROP COLUMN,
DROP CONSTRAINT, ALTER COLUMN and the security/publication clauses -- there is
no ADD INDEX or DROP INDEX action. The dialect's
``supports_alter_table_index_actions()`` probe is False, so the core
``AddIndexAction`` / ``DropIndexAction`` nodes are never used here; only the
real ``CreateIndexStatement`` / ``DropIndexStatement`` nodes are returned.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from rhosocial.activerecord.backend.suggestion import TableIndexChangeSuggestion

from ._change_points import answer, declaration_params, projection

__all__ = ["FirebirdTableIndexChangeSuggestionMixin"]


def _named(values: Tuple[Any, ...]) -> Optional[Dict[str, Any]]:
    """Index declared indexes by name, or None if a name is missing."""
    named: Dict[str, Any] = {}
    for value in values or ():
        params = declaration_params(value)
        name = params.get("name") if params else None
        if not isinstance(name, str) or not name:
            return None
        named[name] = value
    return named


class FirebirdTableIndexChangeSuggestionMixin:
    """Answer an index change with standalone CREATE/DROP INDEX statements."""

    def suggest_table_index_change(
        self, point: TableIndexChangeSuggestion
    ) -> TableIndexChangeSuggestion:
        """Return real Firebird index statements, never ALTER TABLE index actions.

        Drops come first, then creates, one statement per operation. A frozen
        declaration projection keeps plain column names and flags; it loses
        expression columns and a partial-index predicate. Firebird has neither
        functional nor partial indexes (``supports_functional_index()`` and
        ``supports_partial_index()`` are False), so a declaration needing
        those cannot be rebuilt honestly and the answer is ``False``.
        """
        from rhosocial.activerecord.backend.expression.objects import Index, Table
        from rhosocial.activerecord.backend.expression.statements import (
            CreateIndexStatement,
            DropIndexStatement,
        )

        if not (self.supports_create_index() and self.supports_drop_index()):
            return answer(point, False)

        old = _named(point.old_indexes)
        new = _named(point.new_indexes)
        if old is None or new is None:
            return answer(point, False)

        removed = [
            name for name, value in old.items()
            if name not in new or projection(value) != projection(new[name])
        ]
        added = [
            name for name, value in new.items()
            if name not in old or projection(value) != projection(old[name])
        ]
        if not removed and not added:
            return answer(point, None)

        table = Table(self, point.table_name)
        chain = []
        for name in removed:
            params = declaration_params(old[name]) or {}
            if_exists = bool(params.get("if_exists", False))
            concurrent = bool(params.get("concurrent", False))
            if if_exists and not self.supports_index_if_exists():
                return answer(point, False)
            if concurrent and not self.supports_concurrent_index():
                return answer(point, False)
            chain.append(DropIndexStatement(self, Index(self, name)))

        for name in added:
            params = declaration_params(new[name])
            if params is None:
                return answer(point, False)
            columns = params.get("columns") or ()
            # Firebird has no COMPUTED BY / functional index node, so a column
            # expression could not be rendered (supports_functional_index False).
            if not columns or not all(isinstance(column, str) for column in columns):
                return answer(point, False)
            if params.get("partial_condition") is not None and not self.supports_partial_index():
                return answer(point, False)
            include = params.get("include_columns")
            if include is not None and not self.supports_index_include():
                return answer(point, False)
            tablespace = params.get("tablespace")
            if tablespace and not self.supports_index_tablespace():
                return answer(point, False)
            if_not_exists = bool(params.get("if_not_exists", False))
            if if_not_exists and not self.supports_index_if_not_exists():
                return answer(point, False)
            concurrent = bool(params.get("concurrent", False))
            if concurrent and not self.supports_concurrent_index():
                return answer(point, False)
            index_type = params.get("type")
            if index_type and not self.supports_index_type():
                return answer(point, False)
            chain.append(
                CreateIndexStatement(
                    self,
                    Index(self, name),
                    table,
                    list(columns),
                    unique=bool(params.get("unique", False)),
                )
            )
        return answer(point, tuple(chain))
