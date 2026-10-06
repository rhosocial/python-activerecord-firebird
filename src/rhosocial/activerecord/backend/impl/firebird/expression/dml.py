# src/rhosocial/activerecord/backend/impl/firebird/expression/dml.py
"""Firebird DML-specific expression classes.

``UpdateOrInsertExpression`` wraps the ``UPDATE OR INSERT INTO … MATCHING …``
statement.  ``AutonomousTransactionDoExpression`` wraps the
``IN AUTONOMOUS TRANSACTION DO …`` block.  ``ExecuteBlockExpression`` wraps the
``EXECUTE BLOCK …`` statement.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class UpdateOrInsertExpression(BaseExpression):
    """``UPDATE OR INSERT INTO table (cols) VALUES (vals) MATCHING (match)
    [RETURNING …]``.

    The target is a table *reference*, not a bare string: ``table`` accepts a
    :class:`~...expression.objects.Table` or a plain name, and the dialect
    renders whichever it is handed through the object layer. A bare
    ``_table_name`` attribute made the string the only thing the formatter could
    read, and hid whatever the caller had actually attached to the target.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        table: Any,
        insert_columns: List[str],
        insert_values: List[Any],
        match_columns: List[str],
        returning_columns: Optional[List[str]] = None,
    ):
        super().__init__(dialect)
        self.table = table
        self._insert_columns = insert_columns
        self._insert_values = insert_values
        self._match_columns = match_columns
        self._returning_columns = returning_columns

    @property
    def table_name(self) -> Any:
        """The target relation reference this statement updates or inserts into."""
        return self.table

    @property
    def format_method(self) -> str:
        return "format_update_or_insert"


class AutonomousTransactionDoExpression(BaseExpression):
    """``IN AUTONOMOUS TRANSACTION DO BEGIN … END``."""

    def __init__(self, dialect: "SQLDialectBase", block: str):
        super().__init__(dialect)
        self._block = block

    @property
    def format_method(self) -> str:
        return "format_autonomous_transaction_do"


class ExecuteBlockExpression(BaseExpression):
    """``EXECUTE BLOCK (…) AS BEGIN … END``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        block: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self._block = block
        self._params = params

    @property
    def format_method(self) -> str:
        return "format_execute_block"


__all__ = [
    "UpdateOrInsertExpression",
    "AutonomousTransactionDoExpression",
    "ExecuteBlockExpression",
]
