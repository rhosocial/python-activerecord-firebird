# src/rhosocial/activerecord/backend/impl/firebird/expression/database.py
"""Firebird CREATE / DROP DATABASE expressions.

Database creation and removal are operational DDL statements with a Firebird-
specific option set (PAGE_SIZE, DEFAULT CHARACTER SET, COLLATION, DIALECT,
FORCE WRITE, SQL SECURITY).  They are gated here at ``(2, 5, 0)``.  Each
expression delegates SQL generation to the dialect's ``format_*_database_statement``
methods, following the Expression-Dialect separation pattern.
"""

from enum import Enum
from typing import TYPE_CHECKING, Optional, Tuple, Union

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdDatabaseSecurityMode(Enum):
    """SQL SECURITY mode for a created database."""

    INVOKER = "INVOKER"
    DEFINER = "DEFINER"


class FirebirdCreateDatabaseExpression(BaseExpression):
    """CREATE DATABASE 'file' [USER 'u'] [PASSWORD 'p'] [PAGE_SIZE n]
    [DEFAULT CHARACTER SET cs] [COLLATION col] [DIALECT n] [FORCE WRITE]
    [SQL SECURITY INVOKER | DEFINER].

    ``file_path`` may be a plain file path or a configured database alias.
    """

    def __init__(
        self,
        dialect: "SQLDialectBase",
        file_path: str,
        user: Optional[str] = None,
        password: Optional[str] = None,
        page_size: Optional[int] = None,
        default_character_set: Optional[str] = None,
        collation: Optional[str] = None,
        sql_dialect: Optional[int] = None,
        force_write: bool = False,
        sql_security: Optional[Union[FirebirdDatabaseSecurityMode, str]] = None,
    ):
        super().__init__(dialect)
        self.file_path: str = file_path
        self.user: Optional[str] = user
        self.password: Optional[str] = password
        self.page_size: Optional[int] = page_size
        self.default_character_set: Optional[str] = default_character_set
        self.collation: Optional[str] = collation
        self.sql_dialect: Optional[int] = sql_dialect
        self.force_write: bool = force_write
        self.sql_security: Optional[Union[FirebirdDatabaseSecurityMode, str]] = sql_security

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_create_database_statement(self)


class FirebirdDropDatabaseExpression(BaseExpression):
    """DROP DATABASE."""

    def __init__(self, dialect: "SQLDialectBase"):
        super().__init__(dialect)

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_drop_database_statement(self)


__all__ = [
    "FirebirdDatabaseSecurityMode",
    "FirebirdCreateDatabaseExpression",
    "FirebirdDropDatabaseExpression",
]
