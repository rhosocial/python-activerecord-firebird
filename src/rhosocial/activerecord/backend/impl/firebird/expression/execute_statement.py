# src/rhosocial/activerecord/backend/impl/firebird/expression/execute_statement.py
"""Firebird EXECUTE STATEMENT expression.

``EXECUTE STATEMENT`` runs dynamic SQL inside PSQL.  The bare form has
existed since Firebird 1.5, but the ``WITH {AUTONOMOUS | COMMON}
TRANSACTION`` and ``WITH CALLER PRIVILEGES`` clauses were added in
Firebird 3.0, so the whole expression is gated at ``(3, 0, 0)``.

The ``sql`` argument is either a literal SQL string (inlined as a quoted
literal, or passed through unquoted when it starts with ``:`` to reference
a PSQL variable such as ``:sql_param``) or a to_sql-capable expression.
Bound values for the dynamic statement are supplied via ``params``.
"""

from typing import TYPE_CHECKING, Any, List, Optional, Sequence, Tuple, Union

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdExecuteStatementExpression(BaseExpression):
    """EXECUTE STATEMENT sql [WITH {AUTONOMOUS | COMMON} TRANSACTION]
    [WITH CALLER PRIVILEGES] [(params)]."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        sql: Union[str, Any],
        transaction: Optional[str] = None,
        caller_privileges: bool = False,
        params: Optional[Sequence[Any]] = None,
    ):
        super().__init__(dialect)
        self._sql: Union[str, Any] = sql
        self._transaction: Optional[str] = transaction
        self._caller_privileges: bool = caller_privileges
        self._params: List[Any] = list(params) if params else []

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_execute_statement(self)


__all__ = ["FirebirdExecuteStatementExpression"]
