# src/rhosocial/activerecord/backend/impl/firebird/expression/ddl/role.py
"""Firebird ROLE statement expressions.

Roles group privileges for convenient grant management.  ``CREATE ROLE`` and
``DROP ROLE`` exist since early Firebird and are gated here at ``(2, 5, 0)``;
``ALTER ROLE`` (SET/DROP SYSTEM PRIVILEGES, SET/DROP AUTO ADMIN MAPPING) was
added in Firebird 3.0.  Each expression delegates SQL generation to the
dialect's ``format_*_role_statement`` methods, following the Expression-Dialect
separation pattern.
"""

from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Tuple

from rhosocial.activerecord.backend.expression.bases import BaseExpression

if TYPE_CHECKING:  # pragma: no cover
    from rhosocial.activerecord.backend.dialect import SQLDialectBase


class FirebirdRoleAlterClause(Enum):
    """ALTER ROLE clause selector (Firebird 3.0+).

    Per the Firebird 5.0 Language Reference, ``ALTER ROLE`` supports only:
    ``SET SYSTEM PRIVILEGES TO <list>``, ``DROP SYSTEM PRIVILEGES`` and
    ``{SET | DROP} AUTO ADMIN MAPPING``.
    """

    SET_SYSTEM_PRIVILEGES = "SET SYSTEM PRIVILEGES TO"
    DROP_SYSTEM_PRIVILEGES = "DROP SYSTEM PRIVILEGES"
    SET_AUTO_ADMIN_MAPPING = "SET AUTO ADMIN MAPPING"
    DROP_AUTO_ADMIN_MAPPING = "DROP AUTO ADMIN MAPPING"


class FirebirdCreateRoleExpression(BaseExpression):
    """CREATE ROLE name."""

    def __init__(self, dialect: "SQLDialectBase", role_name: str):
        super().__init__(dialect)
        self.role_name: str = role_name

    def to_sql(self) -> Tuple[str, tuple]:
        return self.dialect.format_create_role_statement(self)


class FirebirdAlterRoleExpression(BaseExpression):
    """ALTER ROLE name {SET SYSTEM PRIVILEGES TO ... | DROP SYSTEM
    PRIVILEGES | SET/DROP AUTO ADMIN MAPPING} (Firebird 3.0+)."""

    def __init__(
        self,
        dialect: "SQLDialectBase",
        role_name: str,
        clause: FirebirdRoleAlterClause = FirebirdRoleAlterClause.SET_AUTO_ADMIN_MAPPING,
        system_privileges: Optional[List[str]] = None,
    ):
        super().__init__(dialect)
        self.role_name: str = role_name
        self.clause: FirebirdRoleAlterClause = clause
        self.system_privileges: Optional[List[str]] = system_privileges

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
