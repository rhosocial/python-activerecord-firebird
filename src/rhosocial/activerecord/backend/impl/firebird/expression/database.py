# src/rhosocial/activerecord/backend/impl/firebird/expression/database.py
"""Firebird CREATE / DROP DATABASE expressions.

Database creation and removal are operational DDL statements with a Firebird-
specific option set (PAGE_SIZE, DEFAULT CHARACTER SET, COLLATION, DIALECT,
FORCE WRITE, SQL SECURITY).  They are gated here at ``(2, 5, 0)``.  Each
expression delegates SQL generation to the dialect's ``format_*_database_statement``
methods, following the Expression-Dialect separation pattern.
"""

from enum import Enum
from typing import TYPE_CHECKING, Optional, Union

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdDatabaseSecurityMode(str, Enum):
    #: A member *is* the word it carries: ``__str__ = str.__str__`` keeps the
    #: artifact's spelling the bare word, because the Enum ``__str__`` that
    #: would otherwise win writes ``ClassName.MEMBER`` (§11.3).
    __str__ = str.__str__

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
        # ``sql_security`` already accepts the word as well as the member; a
        # word the enum does not name is refused here rather than at render
        # time (§6: the failure belongs to the constructor, by name).
        if sql_security is not None and not isinstance(
            sql_security, FirebirdDatabaseSecurityMode
        ):
            if isinstance(sql_security, str):
                try:
                    sql_security = FirebirdDatabaseSecurityMode(sql_security)
                except ValueError as exc:
                    raise ValueError(
                        f"unsupported SQL SECURITY mode: {sql_security!r}"
                    ) from exc
            else:
                raise TypeError(
                    f"sql_security must be a FirebirdDatabaseSecurityMode "
                    f"(or its word), got {type(sql_security).__name__}"
                )
        self.sql_security: Optional[FirebirdDatabaseSecurityMode] = sql_security

    @property
    def format_method(self) -> str:
        return "format_create_database_statement"


class FirebirdDropDatabaseExpression(BaseExpression):
    """DROP DATABASE."""

    def __init__(self, dialect: "SQLDialectBase"):
        super().__init__(dialect)

    @property
    def format_method(self) -> str:
        return "format_drop_database_statement"


__all__ = [
    "FirebirdDatabaseSecurityMode",
    "FirebirdCreateDatabaseExpression",
    "FirebirdDropDatabaseExpression",
]
