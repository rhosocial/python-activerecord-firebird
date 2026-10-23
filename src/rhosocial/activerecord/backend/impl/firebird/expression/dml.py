# src/rhosocial/activerecord/backend/impl/firebird/expression/dml.py
"""Firebird DML-specific expression classes.

``UpdateOrInsertStatement`` wraps the ``UPDATE OR INSERT INTO … MATCHING …``
statement.  ``AutonomousTransactionDoExpression`` wraps the
``IN AUTONOMOUS TRANSACTION DO …`` block.  ``ExecuteBlockStatement`` wraps the
``EXECUTE BLOCK …`` statement.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class UpdateOrInsertStatement(BaseExpression):
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
        # Every constructor argument is stored under its own name: the
        # artifact contract reads a parameter by the name it was declared
        # with, and a private spelling would make the node unwritable and
        # unreadable in the same breath.
        self.table = table
        self.insert_columns = insert_columns
        self.insert_values = insert_values
        self.match_columns = match_columns
        self.returning_columns = returning_columns

    @property
    def table_name(self) -> Any:
        """The target relation reference this statement updates or inserts into."""
        return self.table

    @property
    def format_method(self) -> str:
        return "format_update_or_insert_statement"


class AutonomousTransactionDoExpression(BaseExpression):
    """``IN AUTONOMOUS TRANSACTION DO BEGIN … END``."""

    def __init__(self, dialect: "SQLDialectBase", block: str):
        super().__init__(dialect)
        self.block = block

    @property
    def format_method(self) -> str:
        return "format_autonomous_transaction_do_expression"


class ExecuteBlockStatement(BaseExpression):
    """``EXECUTE BLOCK (…) AS BEGIN … END``."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        block: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(dialect)
        self.block = block
        self.params = params

    @property
    def format_method(self) -> str:
        return "format_execute_block_statement"


__all__ = [
    "UpdateOrInsertStatement",
    "AutonomousTransactionDoExpression",
    "ExecuteBlockStatement",
]
