# src/rhosocial/activerecord/backend/impl/firebird/expression/ddl/exception.py
"""Firebird EXCEPTION statement expressions.

An EXCEPTION is a user-defined error message that can be raised from PSQL
with ``EXCEPTION name`` and handled with ``WHEN ... THEN ...``.  Each
expression delegates SQL generation to the dialect's ``format_*_exception_statement``
method, following the Expression-Dialect separation pattern.
"""

from typing import TYPE_CHECKING, Tuple

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdCreateExceptionExpression(BaseExpression):
    """CREATE EXCEPTION name 'message'."""

    def __init__(self, dialect: "SQLDialectBase", exception_name: str, message: str):
        super().__init__(dialect)
        self.exception_name: str = exception_name
        self.message: str = message

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_create_exception_statement(self)


class FirebirdAlterExceptionExpression(BaseExpression):
    """ALTER EXCEPTION name 'message'."""

    def __init__(self, dialect: "SQLDialectBase", exception_name: str, message: str):
        super().__init__(dialect)
        self.exception_name: str = exception_name
        self.message: str = message

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_alter_exception_statement(self)


class FirebirdDropExceptionExpression(BaseExpression):
    """DROP EXCEPTION name."""

    def __init__(self, dialect: "SQLDialectBase", exception_name: str):
        super().__init__(dialect)
        self.exception_name: str = exception_name

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_drop_exception_statement(self)


__all__ = [
    "FirebirdCreateExceptionExpression",
    "FirebirdAlterExceptionExpression",
    "FirebirdDropExceptionExpression",
]
