# src/rhosocial/activerecord/backend/impl/firebird/expression/ddl/role.py
"""Firebird ROLE statement expressions.

Roles group privileges for convenient grant management.  ``CREATE ROLE`` and
``DROP ROLE`` exist since early Firebird and are gated here at ``(2, 5, 0)``;
``ALTER ROLE`` (SET DEFAULT/ACTIVE/INACTIVE/AUTO_ADMIN, RENAME TO) was added
in Firebird 3.0.  Each expression delegates SQL generation to the dialect's
``format_*_role_statement`` methods, following the Expression-Dialect
separation pattern.
"""

from enum import Enum
from typing import TYPE_CHECKING, Optional, Tuple

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdRoleAlterClause(Enum):
    """ALTER ROLE clause selector (Firebird 3.0+)."""

    SET_DEFAULT = "SET DEFAULT"
    SET_ACTIVE = "SET ACTIVE"
    SET_INACTIVE = "SET INACTIVE"
    SET_AUTO_ADMIN = "SET AUTO_ADMIN"
    DROP_AUTO_ADMIN = "DROP AUTO_ADMIN"
    RENAME_TO = "RENAME TO"


class FirebirdCreateRoleExpression(BaseExpression):
    """CREATE ROLE name."""

    def __init__(self, dialect: "SQLDialectBase", role_name: str):
        super().__init__(dialect)
        self.role_name: str = role_name

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_create_role_statement(self)


class FirebirdAlterRoleExpression(BaseExpression):
    """ALTER ROLE name {SET DEFAULT | SET ACTIVE | SET INACTIVE |
    SET AUTO_ADMIN | DROP AUTO_ADMIN | RENAME TO new_name}."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        role_name: str,
        clause: FirebirdRoleAlterClause = FirebirdRoleAlterClause.SET_DEFAULT,
        new_name: Optional[str] = None,
    ):
        super().__init__(dialect)
        self.role_name: str = role_name
        self.clause: FirebirdRoleAlterClause = clause
        self.new_name: Optional[str] = new_name

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_alter_role_statement(self)


class FirebirdDropRoleExpression(BaseExpression):
    """DROP ROLE name."""

    def __init__(self, dialect: "SQLDialectBase", role_name: str):
        super().__init__(dialect)
        self.role_name: str = role_name

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_drop_role_statement(self)


__all__ = [
    "FirebirdRoleAlterClause",
    "FirebirdCreateRoleExpression",
    "FirebirdAlterRoleExpression",
    "FirebirdDropRoleExpression",
]
