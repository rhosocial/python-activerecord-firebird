# src/rhosocial/activerecord/backend/impl/firebird/expression/ddl/package.py
"""Firebird PACKAGE statement expressions.

Packages group stored procedures and functions; they were introduced in
Firebird 3.0.  A package has a header (``CREATE PACKAGE`` declaring the
prototypes) and a body (``CREATE PACKAGE BODY`` implementing them).  Each
expression delegates SQL generation to the dialect's ``format_*_package_statement``
methods, following the Expression-Dialect separation pattern.
"""

from typing import TYPE_CHECKING, Tuple

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdCreatePackageExpression(BaseExpression):
    """CREATE PACKAGE name AS <declarations>."""

    def __init__(self, dialect: "SQLDialectBase", package_name: str, body: str = ""):
        super().__init__(dialect)
        self.package_name: str = package_name
        self.body: str = body

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_create_package_statement(self)


class FirebirdCreatePackageBodyExpression(BaseExpression):
    """CREATE PACKAGE BODY name AS <implementations>."""

    def __init__(self, dialect: "SQLDialectBase", package_name: str, body: str = ""):
        super().__init__(dialect)
        self.package_name: str = package_name
        self.body: str = body

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_create_package_body_statement(self)


class FirebirdDropPackageExpression(BaseExpression):
    """DROP PACKAGE [BODY] name."""

    def __init__(self, dialect: "SQLDialectBase", package_name: str, body: bool = False):
        super().__init__(dialect)
        self.package_name: str = package_name
        self.body: bool = body

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_drop_package_statement(self)


__all__ = [
    "FirebirdCreatePackageExpression",
    "FirebirdCreatePackageBodyExpression",
    "FirebirdDropPackageExpression",
]
